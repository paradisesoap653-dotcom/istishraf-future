"""
طابور مهام دائم على PostgreSQL.

المشكلة التي يحلّها: مسارات ``/api/graph/build`` و``/api/report/generate``
كانت تنفّذ العمل الثقيل داخل دورة الطلب (وعلى serverless تُنفّذه بشكل متزامن
تمامًا) أو في خيط داخل العملية. النتيجة: قطع الطلب بعد ``maxDuration``، ومهام
تبقى «قيد التنفيذ» إلى الأبد، وتكرار نداءات النموذج اللغوي عند إعادة المحاولة.

التصميم:
- جدول ``jobs`` في نفس قاعدة Neon، مع ``FOR UPDATE SKIP LOCKED`` لضمان ألا
  يستلم عاملان المهمة نفسها.
- **lease** بمدة محدّدة يُجدَّد بالنبض؛ عامل مات أو توقف تتاح مهمته من جديد.
- **fencing token** يزداد مع كل استلام؛ العامل القديم لا يستطيع نشر نتيجة
  بعد أن استلم غيره المهمة (نتحقق بـ``owns`` قبل أي نشر).
- ``attempts`` و``run_after`` لإعادة المحاولة بتراجع أسّي.
- ``dedupe_key`` لمنع ازدواج المهمة نفسها وهي نشطة.

العامل يعمل في عملية مستقلة (backend/app/worker.py) على أي مستضيف دائم:
Render / Railway / Fly / VPS / Docker.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Sequence

from . import storage
from ..utils.logger import get_logger

logger = get_logger("mirofish.queue")

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id BIGSERIAL PRIMARY KEY,
        kind TEXT NOT NULL,
        payload JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        run_after TIMESTAMPTZ NOT NULL DEFAULT now(),
        lease_owner TEXT,
        lease_expires_at TIMESTAMPTZ,
        fencing_token BIGINT NOT NULL DEFAULT 0,
        dedupe_key TEXT,
        task_id TEXT,
        owner_user_id BIGINT,
        last_error TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS jobs_claim_idx ON jobs (status, run_after, id)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS jobs_active_dedupe
        ON jobs (dedupe_key)
        WHERE dedupe_key IS NOT NULL AND status IN ('pending', 'running')
    """,
    """
    CREATE TABLE IF NOT EXISTS worker_heartbeats (
        worker_id TEXT PRIMARY KEY,
        kinds TEXT,
        last_seen TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
)

_schema_ready = False


def is_enabled() -> bool:
    """الطابور يحتاج قاعدة بيانات دائمة؛ بدونه نعود للسلوك القديم."""
    return storage.is_durable()


def _conn():
    conn = storage._connect()
    return conn


def ensure_schema(conn=None) -> None:
    global _schema_ready
    if _schema_ready:
        return
    if conn is None:
        with _conn() as new_conn:
            ensure_schema(new_conn)
        return
    with conn.cursor() as cur:
        for statement in _SCHEMA:
            cur.execute(statement)
    _schema_ready = True


def reset_schema_cache() -> None:
    global _schema_ready
    _schema_ready = False


# --------------------------------------------------------------------------
# إدخال المهام
# --------------------------------------------------------------------------

def enqueue(
    kind: str,
    payload: Dict[str, Any],
    *,
    task_id: Optional[str] = None,
    owner_user_id: Optional[int] = None,
    dedupe_key: Optional[str] = None,
    delay_seconds: int = 0,
    max_attempts: int = 3,
) -> Optional[int]:
    """أضف مهمة. يعيد معرّف المهمة، أو معرّف المهمة النشطة عند التكرار."""
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (kind, payload, task_id, owner_user_id, dedupe_key,
                                  max_attempts, run_after)
                VALUES (%s, %s::jsonb, %s, %s, %s, %s, now() + make_interval(secs => %s))
                ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL
                    AND status IN ('pending', 'running')
                DO NOTHING
                RETURNING id
                """,
                (
                    kind,
                    json.dumps(payload, ensure_ascii=False),
                    task_id,
                    owner_user_id,
                    dedupe_key,
                    max_attempts,
                    delay_seconds,
                ),
            )
            row = cur.fetchone()
            if row:
                return int(row[0])
            if dedupe_key:
                cur.execute(
                    """
                    SELECT id FROM jobs
                    WHERE dedupe_key = %s AND status IN ('pending', 'running')
                    ORDER BY id DESC LIMIT 1
                    """,
                    (dedupe_key,),
                )
                existing = cur.fetchone()
                if existing:
                    return int(existing[0])
    return None


# --------------------------------------------------------------------------
# استلام المهام وتأجيرها
# --------------------------------------------------------------------------

def reclaim_expired(conn=None) -> int:
    """أعد المهام التي انتهى تأجيرها إلى الطابور."""
    def _run(c):
        with c.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                   SET status = 'pending',
                       lease_owner = NULL,
                       lease_expires_at = NULL,
                       updated_at = now()
                 WHERE status = 'running'
                   AND lease_expires_at IS NOT NULL
                   AND lease_expires_at < now()
                """
            )
            return cur.rowcount

    if conn is not None:
        return _run(conn)
    with _conn() as new_conn:
        ensure_schema(new_conn)
        return _run(new_conn)


def claim(
    worker_id: Optional[str] = None,
    kinds: Optional[Sequence[str]] = None,
    lease_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """استلم مهمة واحدة جاهزة (ذرّيًا) أو أعِد None."""
    worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                   SET status = 'running',
                       lease_owner = %s,
                       lease_expires_at = now() + make_interval(secs => %s),
                       attempts = attempts + 1,
                       fencing_token = fencing_token + 1,
                       updated_at = now()
                 WHERE id = (
                       SELECT id FROM jobs
                        WHERE status = 'pending'
                          AND run_after <= now()
                          AND (%s::text[] IS NULL OR kind = ANY(%s::text[]))
                        ORDER BY id
                          FOR UPDATE SKIP LOCKED
                        LIMIT 1
                 )
                RETURNING id, kind, payload, attempts, max_attempts,
                          fencing_token, task_id, owner_user_id
                """,
                (worker_id, lease_seconds, list(kinds) if kinds else None, list(kinds) if kinds else None),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "kind": row[1],
        "payload": row[2] if isinstance(row[2], dict) else json.loads(row[2]),
        "attempts": int(row[3]),
        "max_attempts": int(row[4]),
        "fencing_token": int(row[5]),
        "task_id": row[6],
        "owner_user_id": int(row[7]) if row[7] is not None else None,
        "worker_id": worker_id,
    }


def heartbeat(job_id: int, fencing_token: int, lease_seconds: int = 300) -> bool:
    """جدّد التأجير. يعيد False إذا فقد العامل ملكية المهمة."""
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                   SET lease_expires_at = now() + make_interval(secs => %s),
                       updated_at = now()
                 WHERE id = %s AND status = 'running' AND fencing_token = %s
                RETURNING id
                """,
                (lease_seconds, job_id, fencing_token),
            )
            return cur.fetchone() is not None


def owns(job_id: int, fencing_token: int) -> bool:
    """هل ما زال هذا العامل هو المالك الحالي للمهمة؟ (حرس النشر)"""
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM jobs
                 WHERE id = %s AND status = 'running' AND fencing_token = %s
                """,
                (job_id, fencing_token),
            )
            return cur.fetchone() is not None


def complete(job_id: int, fencing_token: int, result: Optional[Dict[str, Any]] = None) -> bool:
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                   SET status = 'succeeded',
                       lease_owner = NULL,
                       lease_expires_at = NULL,
                       payload = payload || %s::jsonb,
                       updated_at = now()
                 WHERE id = %s AND status = 'running' AND fencing_token = %s
                RETURNING id
                """,
                (json.dumps({"result": result or {}}, ensure_ascii=False), job_id, fencing_token),
            )
            return cur.fetchone() is not None


def fail(job_id: int, fencing_token: int, error: str, backoff_seconds: int = 30) -> str:
    """سجّل فشلًا. يعيد الحالة الجديدة: ``pending`` (إعادة محاولة) أو ``failed``."""
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT attempts, max_attempts FROM jobs WHERE id = %s AND status = 'running' AND fencing_token = %s",
                (job_id, fencing_token),
            )
            row = cur.fetchone()
            if not row:
                return "lost"
            attempts, max_attempts = int(row[0]), int(row[1])
            if attempts < max_attempts:
                cur.execute(
                    """
                    UPDATE jobs
                       SET status = 'pending',
                           lease_owner = NULL,
                           lease_expires_at = NULL,
                           last_error = %s,
                           run_after = now() + make_interval(secs => %s),
                           updated_at = now()
                     WHERE id = %s
                    """,
                    (error[:2000], backoff_seconds * attempts, job_id),
                )
                return "pending"
            cur.execute(
                """
                UPDATE jobs
                   SET status = 'failed',
                       lease_owner = NULL,
                       lease_expires_at = NULL,
                       last_error = %s,
                       updated_at = now()
                 WHERE id = %s
                """,
                (error[:2000], job_id),
            )
            return "failed"


def get(job_id: int) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, kind, status, attempts, max_attempts, task_id,
                       lease_owner, lease_expires_at, last_error, created_at, updated_at,
                       payload
                  FROM jobs WHERE id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "kind": row[1],
        "status": row[2],
        "attempts": int(row[3]),
        "max_attempts": int(row[4]),
        "task_id": row[5],
        "lease_owner": row[6],
        "lease_expires_at": row[7].isoformat() if row[7] else None,
        "last_error": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
        "payload": row[11] if isinstance(row[11], dict) else json.loads(row[11]),
    }


def find_by_task(task_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM jobs WHERE task_id = %s ORDER BY id DESC LIMIT 1",
                (task_id,),
            )
            row = cur.fetchone()
    return get(int(row[0])) if row else None


WORKER_LIVENESS_SECONDS = 120


def heartbeat_worker(worker_id: str, kinds: Optional[Sequence[str]] = None) -> None:
    """سجّل حياة العامل. يُستدعى كل دورة استعلام حتى تعرف الواجهة أن عاملاً يعمل."""
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO worker_heartbeats (worker_id, kinds, last_seen)
                VALUES (%s, %s, now())
                ON CONFLICT (worker_id) DO UPDATE
                   SET kinds = EXCLUDED.kinds, last_seen = now()
                """,
                (worker_id, ",".join(kinds) if kinds else None),
            )


def workers_alive(window_seconds: int = WORKER_LIVENESS_SECONDS) -> int:
    """عدد العمال الذين أرسلوا نبضة خلال النافذة الأخيرة."""
    if not is_enabled():
        return 0
    try:
        with _conn() as conn:
            ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM worker_heartbeats WHERE last_seen > now() - make_interval(secs => %s)",
                    (window_seconds,),
                )
                return int(cur.fetchone()[0])
    except Exception as exc:  # pragma: no cover
        logger.error(f"تعذر قراءة العمال الأحياء: {exc}")
        return 0


def should_queue() -> bool:
    """هل نوجّه المهام الطويلة إلى الطابور؟

    نفعل ذلك فقط عند وجود قاعدة دائمة **وعامل حيّ**، حتى لا تبقى المهام
    معلّقة في الطابور إذا لم يُنشر العامل بعد. ``ISTISHRAF_QUEUE_ONLY=1``
    يفرض التوجيه للطابور (للاختبار).
    """
    if not is_enabled():
        return False
    import os

    if (os.environ.get("ISTISHRAF_QUEUE_ONLY") or "").lower() in ("1", "true", "yes"):
        return True
    return workers_alive() > 0


def stats() -> Dict[str, Any]:
    """ملخص الطابور لفحص الصحة — بلا أسرار."""
    if not is_enabled():
        return {"enabled": False}
    try:
        with _conn() as conn:
            ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, COUNT(*),
                           COALESCE(MAX(EXTRACT(EPOCH FROM (now() - created_at))), 0)
                      FROM jobs
                     WHERE created_at > now() - interval '7 days'
                     GROUP BY status
                    """
                )
                rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT COUNT(*) FROM jobs
                     WHERE status = 'pending' AND created_at < now() - interval '10 minutes'
                    """
                )
                stale = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT COUNT(DISTINCT lease_owner) FROM jobs WHERE status = 'running'"
                )
                workers = int(cur.fetchone()[0])
        counts = {row[0]: int(row[1]) for row in rows}
        live = workers_alive()
        return {
            "enabled": True,
            "workers_alive": live,
            "queued_mode": live > 0,
            "pending": counts.get("pending", 0),
            "running": counts.get("running", 0),
            "succeeded": counts.get("succeeded", 0),
            "failed": counts.get("failed", 0),
            "stale_pending": stale,
            "active_workers": workers,
            "worker_healthy": live > 0 or counts.get("pending", 0) == 0,
        }
    except Exception as exc:
        logger.error(f"تعذر قراءة حالة الطابور: {exc}")
        return {"enabled": True, "error": "unavailable"}


def purge_finished(older_than_days: int = 7) -> int:
    with _conn() as conn:
        ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM jobs
                 WHERE status IN ('succeeded', 'failed', 'canceled')
                   AND updated_at < now() - make_interval(days => %s)
                """,
                (older_than_days,),
            )
            return cur.rowcount
