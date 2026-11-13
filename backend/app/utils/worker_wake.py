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

from .logger import get_logger

logger = get_logger("mirofish.worker_wake")

_API = "https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"


def is_configured() -> bool:
    return bool(os.environ.get("GITHUB_DISPATCH_TOKEN") and os.environ.get("GITHUB_REPO"))


def wake(reason: str = "") -> bool:
    """أطلق تشغيلًا فوريًا للعامل. لا يرمي استثناءات أبدًا."""
    if not is_configured():
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
            logger.warning("تعذر إيقاظ العامل (%s): HTTP %s", reason, response.status_code)
            return False
        return True
    except Exception as exc:  # pragma: no cover - شبكة/مهلة
        logger.warning("تعذر إيقاظ العامل (%s): %s", reason, exc)
        return False


def wake_async(reason: str = "") -> None:
    """أطلق الإيقاظ في خيط خلفي حتى لا يتأخر رد الطلب."""
    if not is_configured():
        return
    threading.Thread(target=wake, args=(reason,), daemon=True).start()
