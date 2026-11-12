"""
اختبارات حراسة الـAPI: منع الوصول المجهول وعزل الموارد بين المستخدمين.

تُشغَّل مع تعطيل تجاوز الاختبارات (ISTISHRAF_ENFORCE_AUTH_IN_TESTING=1)
حتى نتحقق من السلوك الحقيقي في الإنتاج.
"""

import os

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.models.project import ProjectManager  # noqa: E402
from app.models.user import UserStore, issue_auth_token  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # قاعدة مستخدمين معزولة لكل اختبار حتى تكون الأدوار حتمية
    from app.config import Config

    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path), raising=False)
    app = create_app()
    app.config["TESTING"] = True
    # لا نضبط متغيرات بيئة عامة حتى لا نؤثر على بقية الاختبارات في نفس العملية
    app.config["ENFORCE_AUTH_IN_TESTING"] = True
    return app.test_client()


def _make_user(email: str, role: str = "user") -> dict:
    try:
        return UserStore.create_user(name="مستخدم اختبار", email=email, password="secret123")
    except ValueError:
        # المستخدم موجود من تشغيل سابق لنفس قاعدة الاختبار
        user = UserStore.authenticate(email=email, password="secret123")
        assert user, "تعذر إنشاء أو تحميل مستخدم الاختبار"
        return user


def _make_non_admin_user(email: str) -> dict:
    """يضمن حسابًا بدور مستخدم عادي (أول حساب في قاعدة فارغة يصبح مديرًا)."""
    if UserStore.count_users() == 0:
        _make_user("guard-admin-placeholder@example.com")
    return _make_user(email)


def _auth_headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {issue_auth_token(user)}"}


def test_anonymous_mutating_request_is_rejected(client):
    response = client.post("/api/graph/build", json={"project_id": "proj_whatever"})
    assert response.status_code == 401
    assert response.get_json()["code"] == "auth_required"


def test_anonymous_project_listing_is_rejected(client):
    response = client.get("/api/graph/project/list")
    assert response.status_code == 401


def test_demo_graph_stays_public_for_reads(client):
    response = client.get("/api/graph/data/graph_demo_ar_001")
    # المطلوب: ألا تحجب الحراسة قراءة العرض التجريبي (401). وجود الملف
    # نفسه أو غيابه شأن مسار البيانات لا شأن المصادقة.
    assert response.status_code != 401


def test_demo_resources_are_not_public_for_writes(client):
    response = client.post("/api/graph/build", json={"project_id": "proj_demo_ar_001"})
    assert response.status_code == 401


def test_config_status_does_not_grant_management_to_anonymous(client):
    payload = client.get("/api/config/status").get_json()["data"]
    assert payload["can_manage"] is False
    assert payload["llm_base_url"] == ""


def test_config_update_rejects_anonymous_even_with_empty_database(client):
    response = client.post("/api/config/update", json={})
    assert response.status_code == 401


def test_config_update_rejects_non_admin(client):
    user = _make_non_admin_user("guard-user@example.com")
    response = client.post("/api/config/update", json={"llm_base_url": "https://evil.example"}, headers=_auth_headers(user))
    assert response.status_code == 403


def test_config_update_allows_admin_without_count_users_dependency(client, monkeypatch):
    admin_email = "guard-admin@example.com"
    monkeypatch.setenv("ADMIN_EMAIL", admin_email)
    user = _make_user(admin_email)
    response = client.post("/api/config/update", json={}, headers=_auth_headers(user))
    assert response.status_code == 200


def test_user_cannot_read_another_users_project(client):
    owner = _make_user("guard-owner@example.com")
    stranger = _make_user("guard-stranger@example.com")
    project = ProjectManager.create_project(name="مشروع اختبار العزل")
    UserStore.assign_owner("project", project.project_id, owner["id"])

    denied = client.get(f"/api/graph/project/{project.project_id}", headers=_auth_headers(stranger))
    assert denied.status_code == 404

    allowed = client.get(f"/api/graph/project/{project.project_id}", headers=_auth_headers(owner))
    assert allowed.status_code == 200


def test_admin_can_read_any_project(client, monkeypatch):
    admin_email = "guard-admin2@example.com"
    monkeypatch.setenv("ADMIN_EMAIL", admin_email)
    owner = _make_user("guard-owner2@example.com")
    project = ProjectManager.create_project(name="مشروع اختبار إدارة")
    UserStore.assign_owner("project", project.project_id, owner["id"])
    admin = _make_user(admin_email)

    response = client.get(f"/api/graph/project/{project.project_id}", headers=_auth_headers(admin))
    assert response.status_code == 200


def test_health_reports_enforced_auth(client):
    payload = client.get("/health").get_json()
    assert payload["status"] == "ok"
    assert payload["auth_enforced"] is True
