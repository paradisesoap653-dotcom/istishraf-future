"""
عامل تنفيذ المهام الدائم لتطبيق «استشراف المستقبل».

يعمل في عملية مستقلة مستضافة (Render / Railway / Fly / VPS / Docker) ويسحب
المهام من طابور ``jobs`` في Neon، فيتحرر مسار HTTP من العمل الثقيل ولا يُقطع
عند ``maxDuration``.

التشغيل:
    python -m app.worker                     # كل أنواع المهام
    python -m app.worker --kinds graph_build # نوع واحد
    python -m app.worker --once               # مهمة واحدة ثم خروج (للاختبار)

الضمانات:
- ``FOR UPDATE SKIP LOCKED``: عاملان لا يستلمان المهمة نفسها.
- lease + نبض دوري: عامل مات تُتاح مهمته من جديد بعد انتهاء التأجير.
- fencing token: عامل فقد الـlease لا يستطيع نشر نتيجة (guard داخل المنفّذ).
- إعادة محاولة بتراجع أسّي حتى ``max_attempts``.
"""

from __future__ import annotations

import argparse
import signal
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from . import create_app
from .config import Config
from .models import job_queue, storage
from .utils.logger import get_logger

logger = get_logger("mirofish.worker")

_stop_event = threading.Event()


# --------------------------------------------------------------------------
# المنفّذون
# --------------------------------------------------------------------------

def _run_graph_build(payload: Dict[str, Any], ctx: Dict[str, Any]) -> None:
    from .api.graph import run_graph_build_task

    run_graph_build_task(
        payload["task_id"],
        payload["project_id"],
        payload.get("graph_name") or "Istishraf Graph",
        int(payload.get("chunk_size") or Config.DEFAULT_CHUNK_SIZE),
        int(payload.get("chunk_overlap") or Config.DEFAULT_CHUNK_OVERLAP),
        bool(payload.get("resume_existing_batch", False)),
        payload.get("locale"),
        guard=ctx["owns"],
    )


def _run_report_generate(payload: Dict[str, Any], ctx: Dict[str, Any]) -> None:
    from .api.report import run_report_generate_task
    from .utils.zep_lifecycle import register_graph_reader, unregister_graph_reader

    graph_id = payload["graph_id"]
    report_id = payload["report_id"]
    # قارئ مسجّل طوال التوليد (حاجز ضد حذف الشبكة) — مجموعة، فالتكرار آمن
    register_graph_reader(graph_id, report_id)
    try:
        run_report_generate_task(
            payload["task_id"],
            graph_id,
            payload["simulation_id"],
            payload.get("simulation_requirement") or "",
            report_id,
            payload.get("locale"),
            guard=ctx["owns"],
        )
    finally:
        unregister_graph_reader(graph_id, report_id)


HANDLERS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], None]] = {
    "graph_build": _run_graph_build,
    "report_generate": _run_report_generate,
}


# --------------------------------------------------------------------------
# دورة التنفيذ
# --------------------------------------------------------------------------

def _heartbeat_loop(job: Dict[str, Any], lease_seconds: int, done: threading.Event) -> None:
    interval = max(5, lease_seconds // 3)
    while not done.wait(interval):
        try:
            # نبضة العامل أيضًا: تنفيذ مهمة طويلة يجب ألا يُظهر العامل ميتًا
            job_queue.heartbeat_worker(job.get("worker_id") or "worker")
        except Exception:  # pragma: no cover
            pass
        if not job_queue.heartbeat(job["id"], job["fencing_token"], lease_seconds):
            logger.error(
                "فُقد تأجير المهمة %s (token=%s) — سيتوقف العامل عن متابعتها",
                job["id"],
                job["fencing_token"],
            )
            return


def execute_job(job: Dict[str, Any], lease_seconds: int) -> str:
    """نفّذ مهمة واحدة. يعيد الحالة النهائية للطابور."""
    handler = HANDLERS.get(job["kind"])
    task_id = job.get("task_id")
    done = threading.Event()
    beat = threading.Thread(
        target=_heartbeat_loop, args=(job, lease_seconds, done), daemon=True
    )
    beat.start()

    logger.info("بدء المهمة %s من النوع %s (محاولة %s/%s)", job["id"], job["kind"], job["attempts"], job["max_attempts"])
    try:
        if handler is None:
            raise RuntimeError(f"لا يوجد منفّذ مسجّل للنوع: {job['kind']}")
        handler(job["payload"], {"owns": lambda: job_queue.owns(job["id"], job["fencing_token"])})
    except Exception as exc:  # noqa: BLE001 - نريد تسجيل أي فشل وإعادة المحاولة
        state = job_queue.fail(job["id"], job["fencing_token"], f"{type(exc).__name__}: {exc}")
        logger.error("فشل المهمة %s (الحالة الجديدة: %s): %s", job["id"], state, exc)
        if state == "failed" and task_id:
            from .models.task import TaskManager, TaskStatus

            TaskManager().update_task(
                task_id,
                status=TaskStatus.FAILED,
                message="فشلت المهمة بعد كل المحاولات",
                error=str(exc),
            )
        return state
    else:
        job_queue.complete(job["id"], job["fencing_token"])
        logger.info("أُنجزت المهمة %s", job["id"])
        return "succeeded"
    finally:
        done.set()


def run_forever(
    kinds: Optional[List[str]] = None,
    lease_seconds: Optional[int] = None,
    poll_seconds: Optional[float] = None,
    once: bool = False,
    reclaim_interval: int = 60,
    max_seconds: Optional[float] = None,
    drain: bool = False,
    app=None,
) -> None:
    """حلقة العمل.

    ``once``     : مهمة واحدة ثم خروج.
    ``drain``    : امضِ في سحب المهام حتى تفرغ أو ينتهي الوقت (نمط cron/CI).
    ``max_seconds``: سقف زمني للعملية كلها — لا نبدأ مهمة جديدة بعده.
    """
    lease_seconds = lease_seconds or Config.JOB_LEASE_SECONDS
    poll_seconds = poll_seconds or Config.JOB_POLL_SECONDS

    if app is None:
        app = create_app()
    worker_id = f"{socket.gethostname()}-{threading.current_thread().name}"
    started_at = time.monotonic()
    processed = 0

    def _out_of_time() -> bool:
        return max_seconds is not None and (time.monotonic() - started_at) >= max_seconds

    with app.app_context():
        if not storage.is_durable():
            logger.error("DATABASE_URL غير مضبوط: العامل يحتاج قاعدة دائمة (Neon).")
            return
        logger.info("العامل %s بدأ العمل (kinds=%s)", worker_id, kinds or "all")

        job_queue.heartbeat_worker(worker_id, kinds)
        last_beat = time.monotonic()
        last_reclaim = 0.0
        while not _stop_event.is_set():
            if time.monotonic() - last_beat > 30:
                try:
                    job_queue.heartbeat_worker(worker_id, kinds)
                except Exception as exc:  # pragma: no cover
                    logger.error("تعذر إرسال نبضة العامل: %s", exc)
                last_beat = time.monotonic()
            now = time.monotonic()
            if now - last_reclaim > reclaim_interval:
                try:
                    freed = job_queue.reclaim_expired()
                    if freed:
                        logger.warning("أُعيد %s مهمة إلى الطابور بعد انتهاء التأجير", freed)
                except Exception as exc:  # pragma: no cover
                    logger.error("تعذر استعادة المهام المنتهية: %s", exc)
                last_reclaim = now

            if _out_of_time():
                logger.warning("انتهى السقف الزمني (%.0fث) — توقف", max_seconds)
                break

            job = job_queue.claim(worker_id, kinds, lease_seconds)
            if job is None:
                if once or drain:
                    break
                _stop_event.wait(poll_seconds)
                continue

            execute_job(job, lease_seconds)
            processed += 1
            if once:
                break

        logger.info("العامل %s توقّف بعد %s مهمة", worker_id, processed)


def _install_signal_handlers() -> None:
    def _handle(signum, _frame):
        logger.warning("إشارة %s: توقف بعد إنهاء المهمة الحالية", signum)
        _stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handle)
        except (ValueError, OSError):  # pragma: no cover
            pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="عامل مهام استشراف المستقبل")
    parser.add_argument("--kinds", default="", help="أنواع المهام مفصولة بفاصلة (افتراضي: الكل)")
    parser.add_argument("--lease", type=int, default=None, help="مدة التأجير بالثواني")
    parser.add_argument("--poll", type=float, default=None, help="فاصل الاستعلام بالثواني")
    parser.add_argument("--once", action="store_true", help="نفّذ مهمة واحدة ثم اخرج")
    parser.add_argument("--drain", action="store_true", help="اسحب المهام حتى تفرغ أو ينتهي الوقت (نمط cron)")
    parser.add_argument("--max-seconds", type=float, default=None, help="سقف زمني للعملية بالثواني")
    parser.add_argument("--purge", action="store_true", help="احذف المهام المنتهية القديمة ثم اخرج")
    args = parser.parse_args(argv)

    if args.purge:
        removed = job_queue.purge_finished()
        logger.info("حُذفت %s مهمة منتهية", removed)
        return 0

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()] or None
    _install_signal_handlers()
    run_forever(
        kinds=kinds,
        lease_seconds=args.lease,
        poll_seconds=args.poll,
        once=args.once,
        max_seconds=args.max_seconds,
        drain=args.drain,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
