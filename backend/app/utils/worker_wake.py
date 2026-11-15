"""إيقاظ عامل المهام لحظة دخول مهمة إلى الطابور.

جدول GitHub Actions غير موثوق (قد يتأخر ساعات)، فبدلًا من انتظار الجدول
نُطلق تشغيلًا فوريًا عبر واجهة GitHub عند إضافة مهمة جديدة.

الإعداد (اختياري — بدونه يعمل العامل بالجدول فقط):
    GITHUB_DISPATCH_TOKEN  توكن بصلاحية Actions: write على المستودع
    GITHUB_REPO            مثل: owner/repo
    GITHUB_WORKFLOW_FILE   الافتراضي: queue-worker.yml
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict

from .logger import get_logger

logger = get_logger("mirofish.worker_wake")

_API = "https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"

# آخر محاولة إيقاظ (للتشخيص عبر /health) — كانت الأعطال صامتة تمامًا سابقًا.
_last: Dict[str, Any] = {"at": None, "ok": None, "detail": "لم تُجرَّب بعد"}


def is_configured() -> bool:
    return bool(os.environ.get("GITHUB_DISPATCH_TOKEN") and os.environ.get("GITHUB_REPO"))


def status() -> Dict[str, Any]:
    """حالة الإيقاظ للمعالجة عبر /health (بلا كشف التوكن)."""
    return {
        "configured": is_configured(),
        "has_token": bool(os.environ.get("GITHUB_DISPATCH_TOKEN")),
        "repo": (os.environ.get("GITHUB_REPO") or "").strip() or None,
        "workflow": (os.environ.get("GITHUB_WORKFLOW_FILE") or "queue-worker.yml").strip(),
        "last": dict(_last),
    }


def _record(ok: bool, detail: str) -> None:
    _last.update({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": ok,
        "detail": detail,
    })


def wake(reason: str = "") -> bool:
    """أطلق تشغيلًا فوريًا للعامل. لا يرمي استثناءات أبدًا."""
    if not is_configured():
        _record(False, "غير مهيّأ: GITHUB_DISPATCH_TOKEN أو GITHUB_REPO ناقص")
        return False
    repo = os.environ["GITHUB_REPO"].strip()
    workflow = (os.environ.get("GITHUB_WORKFLOW_FILE") or "queue-worker.yml").strip()
    token = os.environ["GITHUB_DISPATCH_TOKEN"].strip()
    url = _API.format(repo=repo, workflow=workflow)
    try:
        import httpx

        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"ref": os.environ.get("GITHUB_WORKFLOW_REF", "main"), "inputs": {}},
            timeout=10.0,
        )
        if response.status_code not in (201, 204):
            body = (response.text or "")[:200]
            logger.warning("تعذر إيقاظ العامل (%s): HTTP %s %s", reason, response.status_code, body)
            _record(False, f"HTTP {response.status_code}: {body}")
            return False
        _record(True, f"HTTP {response.status_code}")
        return True
    except Exception as exc:  # pragma: no cover - شبكة/مهلة
        logger.warning("تعذر إيقاظ العامل (%s): %s", reason, exc)
        _record(False, f"{type(exc).__name__}: {exc}"[:200])
        return False


def wake_async(reason: str = "") -> None:
    """أطلق الإيقاظ في خيط خلفي حتى لا يتأخر رد الطلب."""
    if not is_configured():
        return
    threading.Thread(target=wake, args=(reason,), daemon=True).start()
