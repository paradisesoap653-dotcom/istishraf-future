"""إعدادات مشتركة للاختبارات."""

import pytest


@pytest.fixture(autouse=True)
def isolate_job_queue():
    """كل اختبار يبدأ بطابور فارغ وبلا عامل حيّ.

    بدونه تتسرّب نبضات العامل بين الاختبارات، فيتحول مسار البناء إلى الطابور
    داخل اختبارات تفترض التنفيذ المتزامن (وهو ما حدث فعليًا).
    """
    from app.models import job_queue, storage

    if storage.is_durable():
        try:
            with storage._connect() as conn:
                job_queue.ensure_schema(conn)
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM jobs")
                    cur.execute("DELETE FROM worker_heartbeats")
        except Exception:  # pragma: no cover - قاعدة غير مهيأة بعد
            pass
    yield
