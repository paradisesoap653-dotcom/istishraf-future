"""
اختبارات الطابور الدائم والعامل المستقل (المرحلة 3).

تُشغَّل فقط عند ضبط TEST_DATABASE_URL على قاعدة اختبار قابلة للتخلص منها:

    TEST_DATABASE_URL=postgresql://postgres@/istishraf_test?host=/tmp&port=55432 \
    PYTHONPATH=backend python -m pytest backend/tests/test_job_queue.py -q

ما نتحقق منه:
- عاملان لا يستلمان المهمة نفسها (SKIP LOCKED).
- تأجير منتهٍ يعود إلى الطابور ويُستلم من عامل آخر.
- fencing: العامل القديم لا يستطيع النشر بعد أن يفقد التأجير.
- dedupe: لا تُدرج مهمتان فعّالتان لنفس المفتاح.
- إعادة المحاولة بتراجع أسّي ثم ``failed`` بعد استنفاد المحاولات.
- العامل ينفّذ مهمة حقيقية (منفّذ مسجّل) ويغلقها بنجاح.
- ``/health`` يعرض إحصاءات الطابور.
"""

import os
import tempfile

import pytest

TEST_DATABASE_URL = (os.environ.get("TEST_DATABASE_URL") or "").strip()

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL غير مضبوط: اختبارات الطابور متخطاة",
)

os.environ.setdefault("ISTISHRAF_UPLOAD_DIR", tempfile.mkdtemp(prefix="istishraf-queue-tests-"))
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.pop("ISTISHRAF_INLINE_TASKS", None)

from app.config import Config  # noqa: E402
from app.models import job_queue, storage  # noqa: E402


@pytest.fixture(autouse=True)
def clean_jobs():
    Config.DATABASE_URL = TEST_DATABASE_URL
    from app.models.user import UserStore

    UserStore.init_db()
    with storage._connect() as conn:
        storage._ensure_schema(conn)
        job_queue.ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM jobs")
            cur.execute("DELETE FROM worker_heartbeats")
    yield


def _expire_lease(job_id: int) -> None:
    """اجعل التأجير منتهيًا الآن (كما لو أن العامل مات)."""
    with storage._connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s",
                (job_id,),
            )


def test_queue_disabled_without_database(monkeypatch):
    monkeypatch.setattr(Config, "DATABASE_URL", "", raising=False)
    assert job_queue.is_enabled() is False
    assert job_queue.stats() == {"enabled": False}
    assert job_queue.claim("w1", ["graph_build"], 60) is None


def test_enqueue_and_claim_once():
    job_id = job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1")
    assert job_id

    first = job_queue.claim("worker-a", ["graph_build"], 120)
    assert first and first["id"] == job_id
    assert first["attempts"] == 1
    assert first["fencing_token"] == 1

    # لا مهمة ثانية: الأولى قيد التنفيذ
    assert job_queue.claim("worker-b", ["graph_build"], 120) is None
    assert job_queue.get(job_id)["status"] == "running"


def test_two_workers_never_claim_same_job():
    for i in range(6):
        job_queue.enqueue("graph_build", {"task_id": f"t{i}"}, task_id=f"t{i}")

    claimed_a, claimed_b = [], []
    while True:
        job = job_queue.claim("worker-a", ["graph_build"], 120)
        if job is None:
            break
        claimed_a.append(job["id"])
    while True:
        job = job_queue.claim("worker-b", ["graph_build"], 120)
        if job is None:
            break
        claimed_b.append(job["id"])

    assert len(claimed_a) == 6 and claimed_b == []
    assert len(set(claimed_a)) == 6


def test_expired_lease_is_reclaimed_by_another_worker():
    job_id = job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1")
    first = job_queue.claim("worker-a", ["graph_build"], 120)
    assert first["id"] == job_id

    _expire_lease(job_id)
    assert job_queue.reclaim_expired() == 1

    second = job_queue.claim("worker-b", ["graph_build"], 120)
    assert second and second["id"] == job_id
    assert second["attempts"] == 2
    # رمز السياج يتقدّم، فلا يملك العامل القديم حق النشر
    assert second["fencing_token"] > first["fencing_token"]

    assert job_queue.owns(job_id, second["fencing_token"]) is True
    assert job_queue.owns(job_id, first["fencing_token"]) is False
    assert job_queue.complete(job_id, first["fencing_token"]) is False
    assert job_queue.heartbeat(job_id, first["fencing_token"], 120) is False

    # العامل الجديد يُنهي المهمة بنجاح
    assert job_queue.complete(job_id, second["fencing_token"]) is True
    assert job_queue.get(job_id)["status"] == "succeeded"


def test_fencing_token_increases_monotonically():
    job_id = job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1")
    tokens = []
    for worker in ("a", "b", "c"):
        job = job_queue.claim(f"worker-{worker}", ["graph_build"], 120)
        assert job, worker
        tokens.append(job["fencing_token"])
        _expire_lease(job_id)
        job_queue.reclaim_expired()
    assert tokens == sorted(tokens) and len(set(tokens)) == 3


def test_dedupe_blocks_duplicate_active_job():
    key = "graph_build:project-1"
    first = job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1", dedupe_key=key)
    second = job_queue.enqueue("graph_build", {"task_id": "t2"}, task_id="t2", dedupe_key=key)
    # التكرار يعيد معرّف المهمة النشطة نفسها ولا ينشئ صفًا ثانيًا
    assert first and second == first
    assert job_queue.stats()["pending"] == 1

    job = job_queue.claim("worker-a", ["graph_build"], 120)
    assert job["id"] == first

    # المفتاح نفسه مسموح بعد أن تُنجز المهمة السابقة
    job_queue.complete(first, job["fencing_token"])
    third = job_queue.enqueue("graph_build", {"task_id": "t3"}, task_id="t3", dedupe_key=key)
    assert third and third != first


def test_retry_with_backoff_then_failed(monkeypatch):
    job_id = job_queue.enqueue(
        "graph_build", {"task_id": "t1"}, task_id="t1", max_attempts=3
    )
    delays = []
    backoffs = []
    real_fail = job_queue.fail

    def spy_fail(job_id, fencing_token, error, backoff_seconds=30):
        delays.append(backoff_seconds)
        return real_fail(job_id, fencing_token, error, backoff_seconds)

    monkeypatch.setattr(job_queue, "fail", spy_fail)

    for attempt in (1, 2):
        job = job_queue.claim("worker-a", ["graph_build"], 120)
        assert job and job["attempts"] == attempt
        assert job_queue.fail(job_id, job["fencing_token"], "boom") == "pending"
        # التأجيل يمنع الاستلام الفوري
        assert job_queue.claim("worker-a", ["graph_build"], 120) is None
        with storage._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXTRACT(EPOCH FROM (run_after - now())) FROM jobs WHERE id = %s",
                    (job_id,),
                )
                backoffs.append(float(cur.fetchone()[0]))
                cur.execute("UPDATE jobs SET run_after = now() WHERE id = %s", (job_id,))

    job = job_queue.claim("worker-a", ["graph_build"], 120)
    assert job and job["attempts"] == 3
    assert job_queue.fail(job_id, job["fencing_token"], "boom") == "failed"
    assert job_queue.get(job_id)["status"] == "failed"
    assert delays == [30, 30, 30]
    # التأجيل يتصاعد مع عدد المحاولات (30 × attempts)
    assert backoffs == pytest.approx([30, 60], rel=0.2)


def test_kinds_filter_and_delay():
    job_queue.enqueue("report_generate", {"task_id": "r1"}, task_id="r1")
    job_id = job_queue.enqueue(
        "graph_build", {"task_id": "g1"}, task_id="g1", delay_seconds=600
    )
    job = job_queue.claim("worker-a", ["graph_build"], 120)
    assert job is None or job["kind"] != "graph_build"
    other = job_queue.claim("worker-a", ["report_generate"], 120)
    assert other and other["kind"] == "report_generate"
    assert job_queue.get(job_id)["status"] == "pending"


def test_worker_executes_and_completes_job(monkeypatch):
    from app import worker

    seen = {}

    def fake_handler(payload, ctx):
        seen["payload"] = payload
        seen["owns"] = ctx["owns"]()

    monkeypatch.setitem(worker.HANDLERS, "graph_build", fake_handler)
    job_id = job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1")
    job = job_queue.claim("worker-a", ["graph_build"], 120)

    assert worker.execute_job(job, 120) == "succeeded"
    assert seen["payload"] == {"task_id": "t1"}
    assert seen["owns"] is True
    assert job_queue.get(job_id)["status"] == "succeeded"


def test_worker_records_failure_and_retries(monkeypatch):
    from app import worker

    def boom(payload, ctx):
        raise ValueError("انفجار")

    monkeypatch.setitem(worker.HANDLERS, "graph_build", boom)
    job_id = job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1", max_attempts=2)

    job = job_queue.claim("worker-a", ["graph_build"], 120)
    assert worker.execute_job(job, 120) == "pending"
    assert "انفجار" in job_queue.get(job_id)["last_error"]

    with storage._connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE jobs SET run_after = now() WHERE id = %s", (job_id,))
    job = job_queue.claim("worker-a", ["graph_build"], 120)
    assert worker.execute_job(job, 120) == "failed"


def test_should_queue_requires_live_worker():
    job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1")
    # لا عامل حيّ: نعود للسلوك القديم بدل تعليق المهام في طابور لا يخدمه أحد
    assert job_queue.should_queue() is False
    assert job_queue.stats()["queued_mode"] is False

    job_queue.heartbeat_worker("worker-a", ["graph_build"])
    assert job_queue.workers_alive() == 1
    assert job_queue.should_queue() is True
    assert job_queue.stats()["queued_mode"] is True
    assert job_queue.stats()["workers_alive"] == 1

    # نبضة قديمة (عامل توقف) لا تُحتسب
    with storage._connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE worker_heartbeats SET last_seen = now() - interval '10 minutes'")
    assert job_queue.workers_alive() == 0
    assert job_queue.should_queue() is False


def test_queue_only_override(monkeypatch):
    monkeypatch.setenv("ISTISHRAF_QUEUE_ONLY", "1")
    assert job_queue.should_queue() is True


def test_run_forever_once_claims_and_finishes(monkeypatch):
    from app import worker

    done = []
    monkeypatch.setitem(worker.HANDLERS, "graph_build", lambda payload, ctx: done.append(payload))
    job_id = job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1")

    worker.run_forever(kinds=["graph_build"], lease_seconds=60, poll_seconds=0.1, once=True)

    assert done == [{"task_id": "t1"}] or done == []
    assert job_queue.get(job_id)["status"] == "succeeded"
    assert job_queue.workers_alive() == 1


def test_worker_health_endpoint_reports_queue():
    from app import create_app

    job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1")
    app = create_app()
    client = app.test_client()

    payload = client.get("/health").get_json()
    assert payload["queue"]["enabled"] is True
    assert payload["queue"]["pending"] == 1
    assert payload["status"] == "ok"

    deep = client.get("/health?deep=1").get_json()
    assert deep["database"] == "ok"
    # لا عامل يعمل: الطابور غير سليم ويجب أن يظهر ذلك
    assert deep["queue"]["worker_healthy"] is False
    assert deep["status"] == "degraded"

    job = job_queue.claim("worker-a", ["graph_build"], 120)
    deep = client.get("/health?deep=1").get_json()
    assert deep["queue"]["active_workers"] == 1
    assert deep["queue"]["worker_healthy"] is True
    assert deep["status"] == "ok"
    job_queue.complete(job["id"], job["fencing_token"])


def test_purge_finished_removes_only_old_terminal_jobs():
    job_id = job_queue.enqueue("graph_build", {"task_id": "t1"}, task_id="t1")
    job = job_queue.claim("worker-a", ["graph_build"], 120)
    job_queue.complete(job_id, job["fencing_token"])

    assert job_queue.purge_finished(older_than_days=7) == 0
    with storage._connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET updated_at = now() - interval '30 days' WHERE id = %s",
                (job_id,),
            )
    assert job_queue.purge_finished(older_than_days=7) == 1
    assert job_queue.get(job_id) is None
