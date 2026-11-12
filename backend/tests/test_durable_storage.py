"""
اختبارات التخزين الدائم على PostgreSQL (Neon).

تُشغَّل فقط عند ضبط TEST_DATABASE_URL على قاعدة اختبار قابلة للتخلص منها:

    TEST_DATABASE_URL=postgresql://postgres@/istishraf_test?host=/tmp&port=55432 \
    PYTHONPATH=backend python -m pytest backend/tests/test_durable_storage.py -q

الاختبارات تحاكي «cold start»: تحذف مجلد الرفع المحلي بالكامل ثم تتأكد أن
البيانات ما زالت تُقرأ من Postgres.
"""

import os
import shutil
import tempfile

import pytest

TEST_DATABASE_URL = (os.environ.get("TEST_DATABASE_URL") or "").strip()

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL غير مضبوط: اختبارات PostgreSQL متخطاة",
)

os.environ.setdefault("ISTISHRAF_UPLOAD_DIR", tempfile.mkdtemp(prefix="istishraf-pg-tests-"))
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import Config  # noqa: E402
from app.models import storage  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Config.DATABASE_URL = TEST_DATABASE_URL
    from app.models.user import UserStore

    UserStore.init_db()  # ينشئ جداول المستخدمين والملكية إن لم تكن موجودة
    with storage._connect() as conn:
        storage._ensure_schema(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM stored_files")
            cur.execute("DELETE FROM resource_owners")
            cur.execute("DELETE FROM users")
    yield


@pytest.fixture()
def upload_root(tmp_path, monkeypatch):
    """مجلد رفع نظيف + جلسة تخزين دائمة جديدة."""
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path), raising=False)
    monkeypatch.setattr(storage, "_schema_ready", True, raising=False)
    return tmp_path


def cold_start(upload_root):
    """امحُ القرص المحلي كما يحدث عند نسخة serverless جديدة."""
    for entry in os.listdir(upload_root):
        target = os.path.join(str(upload_root), entry)
        shutil.rmtree(target, ignore_errors=True) if os.path.isdir(target) else os.remove(target)


def test_text_survives_cold_start(upload_root):
    path = os.path.join(str(upload_root), "projects", "proj_1", "extracted_text.txt")
    storage.write_text(path, "نص المشروع")

    cold_start(upload_root)

    assert storage.read_text(path) == "نص المشروع"


def test_binary_upload_survives_cold_start(upload_root):
    path = os.path.join(str(upload_root), "projects", "proj_1", "files", "doc.pdf")
    storage.write_bytes(path, b"%PDF-1.7 fake")

    cold_start(upload_root)

    assert storage.read_bytes(path) == b"%PDF-1.7 fake"
    assert storage.size(path) == len(b"%PDF-1.7 fake")


def test_listing_comes_from_database_after_cold_start(upload_root):
    base = os.path.join(str(upload_root), "projects")
    storage.write_text(os.path.join(base, "proj_a", "project.json"), "{}")
    storage.write_text(os.path.join(base, "proj_b", "project.json"), "{}")

    cold_start(upload_root)

    assert storage.listdir(base) == ["proj_a", "proj_b"]


def test_delete_removes_persisted_copy(upload_root):
    path = os.path.join(str(upload_root), "projects", "proj_x", "project.json")
    storage.write_text(path, "{}")
    storage.rmtree(os.path.join(str(upload_root), "projects", "proj_x"))

    cold_start(upload_root)

    assert not storage.exists(path)


def test_project_manager_is_durable(upload_root):
    from app.models.project import ProjectManager

    project = ProjectManager.create_project(name="مشروع دائم")
    ProjectManager.save_extracted_text(project.project_id, "محتويات المستند")

    # امسح نسخة هذا المشروع من القرص المحلي فقط (محاكاة نسخة جديدة)
    shutil.rmtree(ProjectManager._get_project_dir(project.project_id), ignore_errors=True)

    restored = ProjectManager.get_project(project.project_id)
    assert restored is not None
    assert restored.name == "مشروع دائم"
    assert ProjectManager.get_extracted_text(project.project_id) == "محتويات المستند"
    assert project.project_id in [p.project_id for p in ProjectManager.list_projects(limit=None)]


def test_task_manager_restores_after_cold_start(upload_root):
    from app.models.task import TaskManager, TaskStatus

    manager = TaskManager()
    task_id = manager.create_task("graph_build", metadata={"project_id": "proj_1"})
    manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=40, message="قيد البناء")

    # محاكاة نسخة جديدة: لا شيء في الذاكرة ولا على القرص
    manager._tasks.clear()
    os.remove(manager._task_file(task_id))

    restored = TaskManager().get_task(task_id)
    assert restored is not None
    assert restored.status == TaskStatus.PROCESSING
    assert restored.progress == 40


def test_simulation_state_is_durable(upload_root):
    from app.services.simulation_manager import SimulationManager, SimulationStatus

    manager = SimulationManager()
    state = manager.create_simulation(project_id="proj_1", graph_id="graph_1")
    manager._save_simulation_state(state)

    manager._simulations.clear()
    shutil.rmtree(manager._get_simulation_dir(state.simulation_id), ignore_errors=True)

    restored = SimulationManager().get_simulation(state.simulation_id)
    assert restored is not None
    assert restored.project_id == "proj_1"
    assert restored.status in (SimulationStatus.CREATED, SimulationStatus.PREPARING)


def test_users_and_ownership_are_durable(upload_root):
    from app.models.user import UserStore

    user = UserStore.create_user(name="سارة", email="sara@example.com", password="secret123")
    UserStore.assign_owner("project", "proj_owned", user["id"])

    cold_start(upload_root)

    assert UserStore.count_users() == 1
    found = UserStore.get_user_by_id(user["id"])
    assert found["email"] == "sara@example.com"
    assert UserStore.get_owner_id("project", "proj_owned") == user["id"]
    assert UserStore.authenticate(email="sara@example.com", password="secret123") is not None


def test_ownership_isolates_users(upload_root):
    from app.models.user import UserStore

    first = UserStore.create_user(name="أول", email="a@example.com", password="secret123")
    second = UserStore.create_user(name="ثاني", email="b@example.com", password="secret123")
    UserStore.assign_owner("project", "proj_first", first["id"])

    assert UserStore.can_access("project", "proj_first", first) is True
    assert UserStore.can_access("project", "proj_first", second) is False
    assert UserStore.can_access("project", "proj_first", None) is False


def test_health_reports_durable_storage(upload_root):
    info = storage.storage_info()
    assert info["durable"] is True
    assert info["backend"] == "postgres"
    assert storage.check_connection() is True


def test_report_manager_is_durable(upload_root):
    from app.services.report_agent import ReportManager, Report, ReportSection, ReportStatus

    report = Report(
        report_id="report_durable_1",
        simulation_id="sim_durable_1",
        graph_id="graph_1",
        simulation_requirement="اختبار",
        status=ReportStatus.COMPLETED,
        markdown_content="# تقرير دائم",
    )
    ReportManager.save_report(report)
    ReportManager.save_section(report.report_id, 1, ReportSection(title="مقدمة", content="نص المقدمة"))

    shutil.rmtree(ReportManager._get_report_folder(report.report_id), ignore_errors=True)

    restored = ReportManager.get_report(report.report_id)
    assert restored is not None
    assert restored.markdown_content == "# تقرير دائم"
    sections = ReportManager.get_generated_sections(report.report_id)
    assert sections and sections[0]["content"].startswith("## مقدمة")
    assert any(r.report_id == report.report_id for r in ReportManager.list_reports())
