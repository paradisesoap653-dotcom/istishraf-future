From 3d12b9f69ffe1bf83ec995cf4d79e68968b8f875 Mon Sep 17 00:00:00 2001
From: Istishraf Agent <agent@istishraf.local>
Date: Thu, 12 Nov 2026 19:09:33 +0000
Subject: [PATCH 3/3] =?UTF-8?q?feat(worker):=20=D9=85=D8=B4=D8=BA=D9=91?=
 =?UTF-8?q?=D9=84=20=D8=B9=D9=86=D8=AF=20=D8=A7=D9=84=D8=B7=D9=84=D8=A8=20?=
 =?UTF-8?q?+=20=D8=AA=D8=B4=D8=BA=D9=8A=D9=84=20=D8=A7=D9=84=D8=B7=D8=A7?=
 =?UTF-8?q?=D8=A8=D9=88=D8=B1=20=D8=B9=D9=84=D9=89=20GitHub=20Actions?=
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit

- /api/worker/tick محمي برمز مشترك (X-Worker-Token / Bearer / CRON_SECRET)
  ويسحب المهام داخل ميزانية زمنية محددة؛ معطّل افتراضيًا (503) بلا رمز.
- worker.py: --drain و --max-seconds لنمط cron/CI.
- .github/workflows/queue-worker.yml: عامل مجاني كل 5 دقائق بلا خادم.
- vercel.json: كرون يومي كشبكة أمان.
- اختبارات new: 173 ناجح على PG (1 فشل بيئي معروف).
---
 .github/workflows/queue-worker.yml            | 58 +++++++++++
 backend/app/__init__.py                       |  3 +-
 backend/app/api/__init__.py                   |  2 +
 backend/app/api/worker.py                     | 95 +++++++++++++++++++
 backend/app/config.py                         |  3 +
 backend/app/worker.py                         | 37 +++++++-
 backend/tests/test_queue_dispatch.py          | 49 ++++++++++
 vercel.json                                   |  6 ++
 ...31\205\330\263\330\252\331\202\331\204.md" | 27 ++++++
 9 files changed, 275 insertions(+), 5 deletions(-)
 create mode 100644 .github/workflows/queue-worker.yml
 create mode 100644 backend/app/api/worker.py

diff --git a/.github/workflows/queue-worker.yml b/.github/workflows/queue-worker.yml
new file mode 100644
index 0000000..6a6e740
--- /dev/null
+++ b/.github/workflows/queue-worker.yml
@@ -0,0 +1,58 @@
+# عامل المهام الطويلة على GitHub Actions — بديل مجاني لمستضيف دائم.
+#
+# كل تشغيل يسحب المهام الجاهزة من طابور Neon حتى تفرغ أو ينتهي السقف الزمني،
+# ثم يخرج. لا يحتاج أي خادم إضافي، لكن زمن بدء المهمة يصل إلى ~5 دقائق
+# (أقل مدة يدعمها جدول Actions).
+#
+# الأسرار المطلوبة في المستودع (Settings → Secrets and variables → Actions):
+#   DATABASE_URL      اتصال Neon (نفس قيمة تطبيق Vercel)
+#   LLM_API_KEY       مفتاح مزوّد النموذج
+#   LLM_BASE_URL      عنوان المزود المتوافق مع OpenAI
+#   LLM_MODEL_NAME    اسم النموذج
+#   ZEP_API_KEY       (اختياري) عند استخدام Zep Cloud
+
+name: queue-worker
+
+on:
+  schedule:
+    - cron: "*/5 * * * *"
+  workflow_dispatch:
+    inputs:
+      max_seconds:
+        description: "سقف زمني بالثواني"
+        default: "280"
+
+concurrency:
+  group: queue-worker
+  cancel-in-progress: false
+
+jobs:
+  drain:
+    runs-on: ubuntu-latest
+    timeout-minutes: 12
+    steps:
+      - uses: actions/checkout@v4
+
+      - uses: actions/setup-python@v5
+        with:
+          python-version: "3.12"
+          cache: pip
+
+      - name: تثبيت الاعتماديات
+        run: |
+          python -m pip install --upgrade pip
+          pip install -r backend/requirements.txt "psycopg[binary]" psycopg_pool
+
+      - name: سحب المهام وتنفيذها
+        working-directory: backend
+        env:
+          DATABASE_URL: ${{ secrets.DATABASE_URL }}
+          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
+          LLM_BASE_URL: ${{ secrets.LLM_BASE_URL }}
+          LLM_MODEL_NAME: ${{ secrets.LLM_MODEL_NAME }}
+          ZEP_API_KEY: ${{ secrets.ZEP_API_KEY }}
+          ISTISHRAF_UPLOAD_DIR: ${{ runner.temp }}/uploads
+          PYTHONPATH: .
+        run: |
+          BUDGET="${{ github.event.inputs.max_seconds || '280' }}"
+          python -m app.worker --drain --max-seconds "$BUDGET"
diff --git a/backend/app/__init__.py b/backend/app/__init__.py
index 812f963..a614a05 100644
--- a/backend/app/__init__.py
+++ b/backend/app/__init__.py
@@ -82,7 +82,7 @@ def create_app(config_class=Config):
         return response
     
     # 注册蓝图
-    from .api import graph_bp, simulation_bp, report_bp
+    from .api import graph_bp, simulation_bp, report_bp, worker_bp
     from .api.auth import auth_bp
     from .models.user import UserStore, get_current_user
     from .utils.demo_seed import seed_arabic_demo_if_missing
@@ -106,6 +106,7 @@ def create_app(config_class=Config):
     app.register_blueprint(graph_bp, url_prefix='/api/graph')
     app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
     app.register_blueprint(report_bp, url_prefix='/api/report')
+    app.register_blueprint(worker_bp, url_prefix='/api')
     
     # 健康检查
     @app.route('/health')
diff --git a/backend/app/api/__init__.py b/backend/app/api/__init__.py
index 1f88fa2..1c74a54 100644
--- a/backend/app/api/__init__.py
+++ b/backend/app/api/__init__.py
@@ -5,12 +5,14 @@ API路由模块
 from flask import Blueprint
 
 graph_bp = Blueprint('graph', __name__)
+worker_bp = Blueprint('worker', __name__)
 simulation_bp = Blueprint('simulation', __name__)
 report_bp = Blueprint('report', __name__)
 
 from . import graph  # noqa: E402, F401
 from . import simulation  # noqa: E402, F401
 from . import report  # noqa: E402, F401
+from . import worker as worker_api  # noqa: E402, F401
 
 from .guards import install_api_guards  # noqa: E402
 
diff --git a/backend/app/api/worker.py b/backend/app/api/worker.py
new file mode 100644
index 0000000..be64e18
--- /dev/null
+++ b/backend/app/api/worker.py
@@ -0,0 +1,95 @@
+"""مسار تشغيل العامل عند الطلب (نمط cron على منصات بلا عمليات دائمة).
+
+سبب وجوده: Vercel لا يشغّل عمليات مستمرة. بدل استضافة عامل، يمكن لمنصة
+جدولة (Vercel Cron، GitHub Actions، cron خارجي) أن تنادي هذا المسار فيسحب
+مهمة أو أكثر وينفّذها داخل ميزانية زمنية محددة.
+
+الحماية: رمز مشترك في الترويسة (``X-Worker-Token`` أو ``Authorization``)،
+ويُقبل أيضًا ``CRON_SECRET`` الذي يضيفه Vercel تلقائيًا. لا يُستخدم حساب
+مستخدم ولا جلسة — وهذا هو المسار الوحيد في الـAPI الذي يعمل هكذا، ولذلك
+رمزه إلزامي: إن لم يُضبط الرمز يُعطَّل المسار بالكامل (503).
+"""
+
+from __future__ import annotations
+
+import hmac
+import threading
+
+from flask import current_app, jsonify, request
+
+from . import worker_bp
+from ..config import Config
+from ..models import job_queue
+from ..utils.logger import get_logger
+
+logger = get_logger('mirofish.worker.api')
+
+_tick_lock = threading.Lock()
+
+
+def _provided_token() -> str:
+    token = (request.headers.get('X-Worker-Token') or '').strip()
+    if token:
+        return token
+    auth = (request.headers.get('Authorization') or '').strip()
+    if auth.lower().startswith('bearer '):
+        return auth[7:].strip()
+    return ''
+
+
+def _authorized() -> tuple:
+    expected = (Config.WORKER_TOKEN or '').strip()
+    if not expected:
+        return False, "tick_disabled"
+    provided = _provided_token()
+    if not provided or not hmac.compare_digest(provided, expected):
+        return False, "unauthorized"
+    return True, ""
+
+
+@worker_bp.route('/worker/tick', methods=['GET', 'POST'])
+def worker_tick():
+    ok, reason = _authorized()
+    if not ok:
+        if reason == "tick_disabled":
+            return jsonify({
+                "success": False,
+                "error": "مسار العامل معطّل: اضبط ISTISHRAF_WORKER_TOKEN أو CRON_SECRET",
+            }), 503
+        return jsonify({"success": False, "error": "رمز العامل غير صحيح"}), 401
+
+    if not job_queue.is_enabled():
+        return jsonify({
+            "success": False,
+            "error": "العامل يحتاج قاعدة بيانات دائمة (DATABASE_URL)",
+        }), 503
+
+    try:
+        budget = float(request.args.get('budget') or Config.WORKER_TICK_BUDGET)
+    except (TypeError, ValueError):
+        budget = Config.WORKER_TICK_BUDGET
+    # هامش أمان أقل من maxDuration للدالة
+    budget = max(5.0, min(budget, 280.0))
+
+    if not _tick_lock.acquire(blocking=False):
+        return jsonify({
+            "success": True,
+            "data": {"skipped": True, "reason": "tick_already_running"},
+        })
+
+    from ..worker import run_forever
+
+    try:
+        run_forever(
+            app=current_app._get_current_object(),
+            drain=True,
+            max_seconds=budget,
+            poll_seconds=0.5,
+        )
+    except Exception as exc:  # noqa: BLE001
+        logger.error("فشل تشغيل العامل عند الطلب: %s", exc)
+        return jsonify({"success": False, "error": str(exc)}), 500
+    finally:
+        _tick_lock.release()
+
+    return jsonify({"success": True, "data": {"budget": budget, "queue": job_queue.stats()}})
diff --git a/backend/app/config.py b/backend/app/config.py
index f7734ba..2afccca 100644
--- a/backend/app/config.py
+++ b/backend/app/config.py
@@ -53,6 +53,9 @@ class Config:
     # ISTISHRAF_INLINE_TASKS=1 يعيد السلوك القديم (تنفيذ داخل الطلب).
     INLINE_LONG_TASKS = os.environ.get('ISTISHRAF_INLINE_TASKS', '').lower() in ('1', 'true', 'yes')
     JOB_LEASE_SECONDS = int(os.environ.get('ISTISHRAF_JOB_LEASE_SECONDS', '600'))
+    # رمز حماية مسار /api/worker/tick (يُقبل أيضًا CRON_SECRET الذي يضيفه Vercel)
+    WORKER_TOKEN = (os.environ.get('ISTISHRAF_WORKER_TOKEN') or os.environ.get('CRON_SECRET') or '').strip()
+    WORKER_TICK_BUDGET = float(os.environ.get('ISTISHRAF_WORKER_TICK_BUDGET', '240'))
     JOB_POLL_SECONDS = float(os.environ.get('ISTISHRAF_JOB_POLL_SECONDS', '3'))
     
     # 文件上传配置
diff --git a/backend/app/worker.py b/backend/app/worker.py
index b5bef14..a82fd97 100644
--- a/backend/app/worker.py
+++ b/backend/app/worker.py
@@ -146,12 +146,27 @@ def run_forever(
     poll_seconds: Optional[float] = None,
     once: bool = False,
     reclaim_interval: int = 60,
+    max_seconds: Optional[float] = None,
+    drain: bool = False,
+    app=None,
 ) -> None:
+    """حلقة العمل.
+
+    ``once``     : مهمة واحدة ثم خروج.
+    ``drain``    : امضِ في سحب المهام حتى تفرغ أو ينتهي الوقت (نمط cron/CI).
+    ``max_seconds``: سقف زمني للعملية كلها — لا نبدأ مهمة جديدة بعده.
+    """
     lease_seconds = lease_seconds or Config.JOB_LEASE_SECONDS
     poll_seconds = poll_seconds or Config.JOB_POLL_SECONDS
 
-    app = create_app()
+    if app is None:
+        app = create_app()
     worker_id = f"{socket.gethostname()}-{threading.current_thread().name}"
+    started_at = time.monotonic()
+    processed = 0
+
+    def _out_of_time() -> bool:
+        return max_seconds is not None and (time.monotonic() - started_at) >= max_seconds
 
     with app.app_context():
         if not storage.is_durable():
@@ -179,18 +194,23 @@ def run_forever(
                     logger.error("تعذر استعادة المهام المنتهية: %s", exc)
                 last_reclaim = now
 
+            if _out_of_time():
+                logger.warning("انتهى السقف الزمني (%.0fث) — توقف", max_seconds)
+                break
+
             job = job_queue.claim(worker_id, kinds, lease_seconds)
             if job is None:
-                if once:
+                if once or drain:
                     break
                 _stop_event.wait(poll_seconds)
                 continue
 
             execute_job(job, lease_seconds)
+            processed += 1
             if once:
                 break
 
-        logger.info("العامل %s توقّف", worker_id)
+        logger.info("العامل %s توقّف بعد %s مهمة", worker_id, processed)
 
 
 def _install_signal_handlers() -> None:
@@ -211,6 +231,8 @@ def main(argv: Optional[List[str]] = None) -> int:
     parser.add_argument("--lease", type=int, default=None, help="مدة التأجير بالثواني")
     parser.add_argument("--poll", type=float, default=None, help="فاصل الاستعلام بالثواني")
     parser.add_argument("--once", action="store_true", help="نفّذ مهمة واحدة ثم اخرج")
+    parser.add_argument("--drain", action="store_true", help="اسحب المهام حتى تفرغ أو ينتهي الوقت (نمط cron)")
+    parser.add_argument("--max-seconds", type=float, default=None, help="سقف زمني للعملية بالثواني")
     parser.add_argument("--purge", action="store_true", help="احذف المهام المنتهية القديمة ثم اخرج")
     args = parser.parse_args(argv)
 
@@ -221,7 +243,14 @@ def main(argv: Optional[List[str]] = None) -> int:
 
     kinds = [k.strip() for k in args.kinds.split(",") if k.strip()] or None
     _install_signal_handlers()
-    run_forever(kinds=kinds, lease_seconds=args.lease, poll_seconds=args.poll, once=args.once)
+    run_forever(
+        kinds=kinds,
+        lease_seconds=args.lease,
+        poll_seconds=args.poll,
+        once=args.once,
+        max_seconds=args.max_seconds,
+        drain=args.drain,
+    )
     return 0
 
 
diff --git a/backend/tests/test_queue_dispatch.py b/backend/tests/test_queue_dispatch.py
index 06eee4f..fdfc035 100644
--- a/backend/tests/test_queue_dispatch.py
+++ b/backend/tests/test_queue_dispatch.py
@@ -201,3 +201,52 @@ class _FakeThread:
 
     def start(self):
         self.target(*self.args, **self.kwargs)
+
+
+# --------------------------------------------------------------------------
+# مسار العامل عند الطلب (Vercel Cron / GitHub Actions / cron خارجي)
+# --------------------------------------------------------------------------
+
+def test_worker_tick_is_disabled_without_a_token(monkeypatch):
+    from app import create_app
+
+    monkeypatch.setattr(graph_api.Config, "WORKER_TOKEN", "", raising=False)
+    client = create_app().test_client()
+
+    response = client.post("/api/worker/tick")
+    assert response.status_code == 503
+    assert "معط" in response.get_json()["error"]
+
+
+def test_worker_tick_rejects_a_wrong_token(monkeypatch):
+    from app import create_app
+
+    monkeypatch.setattr(graph_api.Config, "WORKER_TOKEN", "s3cret", raising=False)
+    client = create_app().test_client()
+
+    assert client.post("/api/worker/tick", headers={"X-Worker-Token": "nope"}).status_code == 401
+    assert client.post("/api/worker/tick").status_code == 401
+
+
+def test_worker_tick_drains_a_job_with_the_shared_secret(monkeypatch):
+    from app import create_app
+    from app import worker as worker_module
+
+    monkeypatch.setattr(graph_api.Config, "WORKER_TOKEN", "s3cret", raising=False)
+    done = []
+    monkeypatch.setitem(worker_module.HANDLERS, "graph_build", lambda payload, ctx: done.append(payload))
+
+    job_id = job_queue.enqueue("graph_build", {"task_id": "tick-1"}, task_id="tick-1")
+    client = create_app().test_client()
+
+    response = client.post(
+        "/api/worker/tick", headers={"X-Worker-Token": "s3cret"}, query_string={"budget": "10"}
+    )
+    assert response.status_code == 200, response.get_json()
+    assert response.get_json()["data"]["queue"]["pending"] == 0
+    assert job_queue.get(job_id)["status"] == "succeeded"
+    assert done == [{"task_id": "tick-1"}]
+
+    # Vercel Cron يرسل CRON_SECRET كـ Bearer
+    cron = client.get("/api/worker/tick", headers={"Authorization": "Bearer s3cret"})
+    assert cron.status_code == 200
diff --git a/vercel.json b/vercel.json
index 5b0c93c..67d8ad9 100644
--- a/vercel.json
+++ b/vercel.json
@@ -23,5 +23,11 @@
       "source": "/(.*)",
       "destination": "/index.html"
     }
+  ],
+  "crons": [
+    {
+      "path": "/api/worker/tick?budget=45",
+      "schedule": "0 3 * * *"
+    }
   ]
 }
diff --git "a/\330\257\331\204\331\212\331\204-\330\252\330\264\330\272\331\212\331\204-\330\247\331\204\330\271\330\247\331\205\331\204-\330\247\331\204\331\205\330\263\330\252\331\202\331\204.md" "b/\330\257\331\204\331\212\331\204-\330\252\330\264\330\272\331\212\331\204-\330\247\331\204\330\271\330\247\331\205\331\204-\330\247\331\204\331\205\330\263\330\252\331\202\331\204.md"
index e7f324c..c789810 100644
--- "a/\330\257\331\204\331\212\331\204-\330\252\330\264\330\272\331\212\331\204-\330\247\331\204\330\271\330\247\331\205\331\204-\330\247\331\204\331\205\330\263\330\252\331\202\331\204.md"
+++ "b/\330\257\331\204\331\212\331\204-\330\252\330\264\330\272\331\212\331\204-\330\247\331\204\330\271\330\247\331\205\331\204-\330\247\331\204\331\205\330\263\330\252\331\202\331\204.md"
@@ -58,6 +58,31 @@ python -m app.worker --lease 900 --poll 5    # تأجير أطول / استعل
 python -m app.worker --purge                 # نظّف المهام المنتهية الأقدم من 7 أيام
 ```
 
+### بلا خادم: GitHub Actions (مجاني، المستودع موجود أصلًا)
+الملف `.github/workflows/queue-worker.yml` جاهز: كل 5 دقائق يشغّل
+`python -m app.worker --drain --max-seconds 280` (أو يدويًا من تبويب Actions).
+أضف الأسرار في المستودع: `DATABASE_URL`, `LLM_API_KEY`, `LLM_BASE_URL`,
+`LLM_MODEL_NAME`, و`ZEP_API_KEY` عند استخدام Zep. لا خادم ولا فاتورة،
+لكن زمن بدء المهمة قد يصل إلى ~5 دقائق.
+
+### أو: مشغّل عند الطلب (Vercel Cron / cron خارجي)
+مسار محمي بسقف زمني يسحب ما في الطابور ثم يخرج:
+
+```bash
+curl -X POST -H "X-Worker-Token: $ISTISHRAF_WORKER_TOKEN" \
+     "https://istishraf-future.vercel.app/api/worker/tick?budget=45"
+```
+
+- الرمز يُقبل أيضًا كـ`Authorization: Bearer …`، ويُقبل `CRON_SECRET` الذي
+  يضيفه Vercel تلقائيًا. إن لم يُضبط أي رمز فالمسار **معطّل (503)**.
+- `budget` يجب أن يبقى أقل من `maxDuration` للدالة. على خطة Hobby الحد 60 ثانية
+  لذلك `vercel.json` يضع `budget=45` في كرون يومي (شبكة أمان فقط، لا اعتماد
+  عليه لبناء شبكة كاملة). مع تفعيل Fluid Compute على Vercel يمكن رفع الحد إلى
+  300 ثانية و`budget` إلى 280.
+- **تنبيه:** Vercel لا يصلح عاملًا دائمًا: Hobby يسمح بكرون **مرة يوميًا** فقط.
+  المسار مفيد كشبكة أمان أو مع cron خارجي، أما العمل الطويل فمكانه عامل حقيقي
+  أو GitHub Actions.
+
 ### Docker / Render / Railway / Koyeb / Fly
 ```bash
 docker build -t istishraf .
@@ -97,6 +122,8 @@ POST /api/graph/build   →  202 Created
 | `ISTISHRAF_JOB_POLL_SECONDS` | `3` | فاصل استعلام العامل |
 | `ISTISHRAF_INLINE_TASKS` | معطّل | `1` = تنفيذ داخل الطلب (سلوك طوارئ/تشخيص) |
 | `ISTISHRAF_QUEUE_ONLY` | معطّل | `1` = افرض الطابور حتى لو لم يُرصد عامل حيّ |
+| `ISTISHRAF_WORKER_TOKEN` | فارغ | رمز حماية `/api/worker/tick` (وإلا فالمسار معطّل) |
+| `ISTISHRAF_WORKER_TICK_BUDGET` | `240` | الميزانية الافتراضية للمسار بالثواني |
 
 ---
 
-- 
2.47.3

