"""إيقاظ العامل عند دخول مهمة — بلا شبكة في الاختبار."""

import os

from app.utils import worker_wake


def test_not_configured_returns_false(monkeypatch):
    monkeypatch.delenv("GITHUB_DISPATCH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    assert worker_wake.is_configured() is False
    assert worker_wake.wake("test") is False


def test_wake_posts_to_github(monkeypatch):
    calls = {}

    class _Resp:
        status_code = 204

    def _post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        return _Resp()

    import httpx

    monkeypatch.setattr(httpx, "post", _post)
    monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "t0ken")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")

    assert worker_wake.wake("unit") is True
    assert calls["url"] == "https://api.github.com/repos/owner/repo/actions/workflows/queue-worker.yml/dispatches"
    assert calls["headers"]["Authorization"] == "Bearer t0ken"
    assert calls["json"] == {"ref": "main", "inputs": {}}


def test_wake_failure_is_swallowed(monkeypatch):
    class _Resp:
        status_code = 401

    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "t0ken")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    assert worker_wake.wake("unit") is False
