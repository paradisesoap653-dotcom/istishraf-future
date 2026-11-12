"""مسار تشغيل العامل عند الطلب (نمط cron على منصات بلا عمليات دائمة).

سبب وجوده: Vercel لا يشغّل عمليات مستمرة. بدل استضافة عامل، يمكن لمنصة
جدولة (Vercel Cron، GitHub Actions، cron خارجي) أن تنادي هذا المسار فيسحب
مهمة أو أكثر وينفّذها داخل ميزانية زمنية محددة.

الحماية: رمز مشترك في الترويسة (``X-Worker-Token`` أو ``Authorization``)،
ويُقبل أيضًا ``CRON_SECRET`` الذي يضيفه Vercel تلقائيًا. لا يُستخدم حساب
مستخدم ولا جلسة — وهذا هو المسار الوحيد في الـAPI الذي يعمل هكذا، ولذلك
رمزه إلزامي: إن لم يُضبط الرمز يُعطَّل المسار بالكامل (503).
"""

from __future__ import annotations

import hmac
import socket
import threading
import uuid

from flask import current_app, jsonify, request

from . import worker_bp
from ..config import Config
from ..models import job_queue
from ..utils.logger import get_logger

logger = get_logger('mirofish.worker.api')

_tick_lock = threading.Lock()


def _provided_token() -> str:
    token = (request.headers.get('X-Worker-Token') or '').strip()
    if token:
        return token
    auth = (request.headers.get('Authorization') or '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return ''


def _authorized() -> tuple:
    expected = (Config.WORKER_TOKEN or '').strip()
    if not expected:
        return False, "tick_disabled"
    provided = _provided_token()
    if not provided or not hmac.compare_digest(provided, expected):
        return False, "unauthorized"
    return True, ""


@worker_bp.route('/worker/tick', methods=['GET', 'POST'])
def worker_tick():
    ok, reason = _authorized()
    if not ok:
        if reason == "tick_disabled":
            return jsonify({
                "success": False,
                "error": "مسار العامل معطّل: اضبط ISTISHRAF_WORKER_TOKEN أو CRON_SECRET",
            }), 503
        return jsonify({"success": False, "error": "رمز العامل غير صحيح"}), 401

    if not job_queue.is_enabled():
        return jsonify({
            "success": False,
            "error": "العامل يحتاج قاعدة بيانات دائمة (DATABASE_URL)",
        }), 503

    try:
        budget = float(request.args.get('budget') or Config.WORKER_TICK_BUDGET)
    except (TypeError, ValueError):
        budget = Config.WORKER_TICK_BUDGET
    # هامش أمان أقل من maxDuration للدالة
    budget = max(5.0, min(budget, 280.0))

    if not _tick_lock.acquire(blocking=False):
        return jsonify({
            "success": True,
            "data": {"skipped": True, "reason": "tick_already_running"},
        })

    from ..worker import run_forever

    try:
        run_forever(
            app=current_app._get_current_object(),
            drain=True,
            max_seconds=budget,
            poll_seconds=0.5,
            # عامل موقوت: نبضته لا تُحوّل طلبات المستخدمين إلى الطابور
            persistent=False,
            worker_id=f"tick-{socket.gethostname()}-{uuid.uuid4().hex[:6]}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("فشل تشغيل العامل عند الطلب: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        _tick_lock.release()

    return jsonify({"success": True, "data": {"budget": budget, "queue": job_queue.stats()}})
