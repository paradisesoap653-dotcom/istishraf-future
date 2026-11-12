"""
اختبارات توجيه المهام الطويلة إلى الطابور الدائم (المرحلة 3).

السؤال الذي تجيبه: هل تتحول مسارات HTTP الطويلة إلى ``202 + task_id`` بدل أن
تنفّذ العمل داخل دورة الطلب (حيث يُقطع بعد 60 ثانية على Vercel)؟

تُشغَّل فقط مع قاعدة اختبار حقيقية:

    TEST_DATABASE_URL=postgresql://postgres@/istishraf_test?host=/tmp&port=55432 \
    PYTHONPATH=backend python -m pytest backend/tests/test_queue_dispatch.py -q
"""

import os
import tempfile
from datetime import datetime
from types import SimpleNamespace

import pytest
from flask import Flask

TEST_DATABASE_URL = (os.environ.get("TEST_DATABASE_URL") or "").strip()

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL غير مضبوط: اختبارات الطابور متخطاة",
)

os.environ.setdefault("ISTISHRAF_UPLOAD_DIR", tempfile.mkdtemp(prefix="istishraf-dispatch-tests-"))
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import Config  # noqa: E402
from app.models import job_queue, storage  # noqa: E402
from app.models.project import Project, ProjectStatus  # noqa: E402
from app.api import graph as graph_api  # noqa: E402


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
    Config.INLINE_LONG_TASKS = False


def _project():
    now = datetime.now().isoformat()
    return Project(
        project_id="proj-queue",
        name="Project",
        status=ProjectStatus.ONTOLOGY_GENERATED,
        created_at=now,
        updated_at=now,
        ontology={"entity_types": [], "edge_types": []},
    )


def _json_result(result):
    if isinstance(result, tuple):
        response, status = result
    else:
        response, status = result, result.status_code
    return response.get_json(), status


def _prepare(monkeypatch, project):
    monkeypatch.setattr(graph_api.Config, "ZEP_API_KEY", "test-key")
    monkeypatch.setattr(graph_api.Config, "IS_SERVERLESS", False)
    monkeypatch.setattr(
        graph_api.ProjectManager, "get_project",
        classmethod(lambda _cls, _pid: project),
    )
    monkeypatch.setattr(
        graph_api.ProjectManager, "get_extracted_text",
        classmethod(lambda _cls, _pid: "source text"),
    )
    monkeypatch.setattr(
        graph_api.ProjectManager, "save_project",
        classmethod(lambda _cls, _p: None),
    )
    # لا نريد تشغيل نموذج لغوي حقيقي: نكتفي بأن الطابور استلم المهمة
    def _must_not_run(*_args, **_kwargs):
        raise AssertionError("يجب ألا يُنفّذ البناء داخل دورة الطلب")

    monkeypatch.setattr(graph_api, "run_graph_build_task", _must_not_run)


def _post_build():
    app = Flask(__name__)
    with app.test_request_context(
        "/api/graph/build", method="POST", json={"project_id": "proj-queue"}
    ):
        return _json_result(graph_api.build_graph())


def test_build_returns_202_and_enqueues_when_worker_is_alive(monkeypatch):
    _prepare(monkeypatch, _project())
    job_queue.heartbeat_worker("worker-a", ["graph_build"])
    assert job_queue.should_queue() is True

    body, status = _post_build()

    assert status == 202, body
    assert body["success"] is True
    assert body["data"]["queued"] is True
    task_id = body["data"]["task_id"]
    assert task_id

    job = job_queue.find_by_task(task_id)
    assert job and job["kind"] == "graph_build"
    assert job["status"] == "pending"
    payload = job["payload"]
    assert payload["project_id"] == "proj-queue"
    assert payload["task_id"] == task_id


def test_build_stays_synchronous_without_a_worker(monkeypatch):
    _prepare(monkeypatch, _project())
    calls = []
    monkeypatch.setattr(
        graph_api, "run_graph_build_task", lambda *args, **kwargs: calls.append(args)
    )
    monkeypatch.setattr(graph_api.threading, "Thread", _FakeThread)

    body, status = _post_build()

    assert status == 200, body
    assert body["data"]["queued"] is False
    assert job_queue.find_by_task(body["data"]["task_id"]) is None
    assert len(calls) == 1  # المسار القديم ما زال يعمل


def test_inline_override_disables_queue_even_with_worker(monkeypatch):
    _prepare(monkeypatch, _project())
    calls = []
    monkeypatch.setattr(
        graph_api, "run_graph_build_task", lambda *args, **kwargs: calls.append(args)
    )
    monkeypatch.setattr(graph_api.threading, "Thread", _FakeThread)
    job_queue.heartbeat_worker("worker-a", ["graph_build"])
    monkeypatch.setattr(graph_api.Config, "INLINE_LONG_TASKS", True, raising=False)

    body, status = _post_build()

    assert status == 200, body
    assert body["data"]["queued"] is False
    assert calls  # نُفّذ داخل الطلب (سلوك الطوارئ)


def test_second_build_reuses_the_queued_task_instead_of_starting_another(monkeypatch):
    _prepare(monkeypatch, _project())
    job_queue.heartbeat_worker("worker-a", ["graph_build"])

    first, status = _post_build()
    assert status == 202
    second, status2 = _post_build()

    # 200 + reused: يُعاد نفس المهمة، ولا يُنشأ عمل ثانٍ ولا نداء نموذج إضافي
    assert status2 == 200, second
    assert second["data"]["reused"] is True
    assert second["data"]["task_id"] == first["data"]["task_id"]
    assert job_queue.stats()["pending"] == 1


def test_queue_dedupe_marks_the_new_task_failed(monkeypatch):
    """لو تجاوزت المهمة حارس الحالة، فإن الطابور نفسه يمنع الازدواج."""
    from app.models.task import TaskManager

    _prepare(monkeypatch, _project())
    job_queue.heartbeat_worker("worker-a", ["graph_build"])

    first, _ = _post_build()
    assert first["data"]["task_id"]

    # مشروع «جديد» بنفس المعرف: حارس الحالة لا يرى المهمة السابقة
    monkeypatch.setattr(
        graph_api.ProjectManager, "get_project",
        classmethod(lambda _cls, _pid: _project()),
    )
    second, status2 = _post_build()

    assert status2 == 409, second
    assert second["code"] == "duplicate_active_build"
    assert second["data"]["active_task_id"] == first["data"]["task_id"]
    assert job_queue.stats()["pending"] == 1
class _FakeThread:
    """خيط وهمي: يسجّل النداء ولا ينفّذ شيئًا."""

    def __init__(self, *, target, daemon=True, args=(), kwargs=None):
        self.target = target
        self.daemon = daemon
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)


# --------------------------------------------------------------------------
# مسار العامل عند الطلب (Vercel Cron / GitHub Actions / cron خارجي)
# --------------------------------------------------------------------------

def test_worker_tick_is_disabled_without_a_token(monkeypatch):
    from app import create_app

    monkeypatch.setattr(graph_api.Config, "WORKER_TOKEN", "", raising=False)
    client = create_app().test_client()

    response = client.post("/api/worker/tick")
    assert response.status_code == 503
    assert "معط" in response.get_json()["error"]


def test_worker_tick_rejects_a_wrong_token(monkeypatch):
    from app import create_app

    monkeypatch.setattr(graph_api.Config, "WORKER_TOKEN", "s3cret", raising=False)
    client = create_app().test_client()

    assert client.post("/api/worker/tick", headers={"X-Worker-Token": "nope"}).status_code == 401
    assert client.post("/api/worker/tick").status_code == 401


def test_worker_tick_drains_a_job_with_the_shared_secret(monkeypatch):
    from app import create_app
    from app import worker as worker_module

    monkeypatch.setattr(graph_api.Config, "WORKER_TOKEN", "s3cret", raising=False)
    done = []
    monkeypatch.setitem(worker_module.HANDLERS, "graph_build", lambda payload, ctx: done.append(payload))

    job_id = job_queue.enqueue("graph_build", {"task_id": "tick-1"}, task_id="tick-1")
    client = create_app().test_client()

    response = client.post(
        "/api/worker/tick", headers={"X-Worker-Token": "s3cret"}, query_string={"budget": "10"}
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["queue"]["pending"] == 0
    # عامل موقوت: لا يُفعّل التوجيه للطابور
    assert response.get_json()["data"]["queue"]["queued_mode"] is False
    assert job_queue.get(job_id)["status"] == "succeeded"
    assert done == [{"task_id": "tick-1"}]

    # Vercel Cron يرسل CRON_SECRET كـ Bearer
    cron = client.get("/api/worker/tick", headers={"Authorization": "Bearer s3cret"})
    assert cron.status_code == 200
