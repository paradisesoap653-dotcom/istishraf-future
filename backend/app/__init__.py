"""
MiroFish Backend - Flask应用工厂
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request, send_from_directory, abort
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('mirofish')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 启动中...")
        logger.info("=" * 50)
    
    # 启用CORS（支持Web与Capacitor Android跨域请求及Bearer令牌）
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": "*",
                "allow_headers": ["Content-Type", "Authorization"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            }
        },
    )
    
    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册模拟进程清理函数")
    
    # 请求日志中间件（لا تُسجّل الأسرار أبدًا)
    _REDACTED_KEYS = ('key', 'password', 'token', 'secret', 'authorization')

    def _redact(payload):
        if not isinstance(payload, dict):
            return payload
        return {
            k: ('***' if any(marker in k.lower() for marker in _REDACTED_KEYS) else v)
            for k, v in payload.items()
        }

    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {_redact(request.get_json(silent=True))}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"响应: {response.status_code}")
        return response
    
    # 注册蓝图
    from .api import graph_bp, simulation_bp, report_bp, worker_bp
    from .api.auth import auth_bp
    from .models.user import UserStore, get_current_user
    from .utils.demo_seed import seed_arabic_demo_if_missing
    UserStore.init_db()
    try:
        seed_arabic_demo_if_missing()
    except Exception as seed_err:
        logger.warning(f"Demo seed skipped: {seed_err}")

    from .models import storage
    if Config.IS_SERVERLESS and not storage.is_durable():
        logger.error(
            "DATABASE_URL غير مضبوط على serverless: كل بيانات المستخدمين "
            "(الحسابات، المشاريع، الملفات، المحاكاة، التقارير) ستُفقد عند "
            "إعادة التشغيل. اضبط DATABASE_URL على Neon."
        )
    else:
        logger.info(f"التخزين الدائم: {'Postgres/Neon' if storage.is_durable() else 'محلي'}")

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(worker_bp, url_prefix='/api')
    
    # 健康检查
    @app.route('/health')
    def health():
        from .models import storage

        durable = storage.is_durable()
        payload = {
            'status': 'ok',
            'service': 'Istishraf Backend',
            'storage': 'postgres' if durable else ('ephemeral' if Config.IS_SERVERLESS else 'local-disk'),
            'durable': durable,
            'auth_enforced': True,
        }
        # حالة الطابور (بلا أسرار): عدد المهام وحالة العامل المستقل
        try:
            from .models import job_queue

            payload['queue'] = job_queue.stats()
        except Exception:  # pragma: no cover - لا يجب أن يُسقط /health
            payload['queue'] = {'enabled': False}
        # حالة سلسلة نماذج الذكاء الاصطناعي (بلا مفاتيح): أي مزوّد بديل جاهز؟
        try:
            from .utils.llm_client import describe_fallback_providers

            chain = [{'provider': 'الأساسي', 'model': Config.LLM_MODEL_NAME, 'key_present': True}]
            for name in (Config.LLM_FALLBACK_MODELS or '').split(','):
                if name.strip():
                    chain.append({'provider': 'نموذج بديل (نفس المزوّد)', 'model': name.strip(), 'key_present': True})
            chain.extend(describe_fallback_providers())
            payload['llm'] = chain
        except Exception:  # pragma: no cover
            pass
        # فحص عميق اختياري: /health?deep=1 يحاول اتصالًا حقيقيًا بقاعدة البيانات
        if request.args.get('deep') in ('1', 'true', 'yes'):
            payload['database'] = 'ok' if storage.check_connection() else 'unavailable'
            if payload['database'] != 'ok':
                payload['status'] = 'degraded'
            queue = payload.get('queue') or {}
            if queue.get('enabled') and queue.get('worker_healthy') is False:
                payload['status'] = 'degraded'
        return payload

    @app.route('/api/config/status', methods=['GET'])
    def get_config_status():
        user = get_current_user()
        # لا يُمنح حق الإدارة لغياب المستخدمين: قاعدة البيانات المؤقتة على
        # serverless تبدأ فارغة دائمًا، وكان ذلك يفتح الإدارة للزوار.
        can_manage = bool(user and user.get('role') == 'admin')
        has_llm = bool(Config.LLM_API_KEY and Config.LLM_API_KEY.strip())
        has_zep = bool(Config.ZEP_API_KEY and Config.ZEP_API_KEY.strip())
        return {
            'success': True,
            'data': {
                'configured': has_llm,
                'has_llm_key': has_llm,
                'has_zep_key': has_zep,
                'can_manage': can_manage,
                'llm_base_url': (Config.LLM_BASE_URL or 'https://api.openai.com/v1') if can_manage else '',
                'llm_model_name': (Config.LLM_MODEL_NAME or 'gpt-4o-mini') if can_manage else '',
            }
        }

    @app.route('/api/config/update', methods=['POST'])
    def update_config_settings():
        user = get_current_user()
        if not user:
            return {
                'success': False,
                'code': 'auth_required',
                'error': 'مطلوب تسجيل الدخول للوصول إلى هذه الخدمة',
            }, 401
        if user.get('role') != 'admin':
            return {
                'success': False,
                'error': 'فقط مدير النظام يملك صلاحية تعديل مفاتيح الخادم'
            }, 403
        payload = request.get_json(silent=True) or {}
        llm_key = (payload.get('llm_api_key') or '').strip()
        llm_url = (payload.get('llm_base_url') or '').strip()
        llm_model = (payload.get('llm_model_name') or '').strip()
        zep_key = (payload.get('zep_api_key') or '').strip()

        if llm_key:
            Config.LLM_API_KEY = llm_key
            os.environ['LLM_API_KEY'] = llm_key
        if llm_url:
            Config.LLM_BASE_URL = llm_url
            os.environ['LLM_BASE_URL'] = llm_url
        if llm_model:
            Config.LLM_MODEL_NAME = llm_model
            os.environ['LLM_MODEL_NAME'] = llm_model
        if zep_key:
            Config.ZEP_API_KEY = zep_key
            os.environ['ZEP_API_KEY'] = zep_key

        # على serverless لا نكتب المفاتيح على القرص: /tmp مؤقت ويقرأه أي
        # كود آخر في النسخة، والتعديل لا يُشارك بين النسخ أصلًا.
        if not Config.IS_SERVERLESS:
            env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))
            lines = [
                f"LLM_API_KEY={Config.LLM_API_KEY or ''}",
                f"LLM_BASE_URL={Config.LLM_BASE_URL or 'https://api.openai.com/v1'}",
                f"LLM_MODEL_NAME={Config.LLM_MODEL_NAME or 'gpt-4o-mini'}",
                f"ZEP_API_KEY={Config.ZEP_API_KEY or ''}",
            ]
            try:
                with open(env_path, 'w', encoding='utf-8') as env_file:
                    env_file.write('\n'.join(lines) + '\n')
            except OSError as env_err:
                logger.warning(f"Skipping .env write on read-only fs: {env_err}")

        has_llm = bool(Config.LLM_API_KEY and Config.LLM_API_KEY.strip())
        has_zep = bool(Config.ZEP_API_KEY and Config.ZEP_API_KEY.strip())
        return {
            'success': True,
            'data': {
                'configured': has_llm,
                'has_llm_key': has_llm,
                'has_zep_key': has_zep,
                'llm_base_url': Config.LLM_BASE_URL,
                'llm_model_name': Config.LLM_MODEL_NAME,
            }
        }

    # Serve compiled Vue PWA frontend from frontend/webroot on port 5001
    webroot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../frontend/webroot'))

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path: str):
        if path.startswith('api/'):
            abort(404)
        if not os.path.isdir(webroot_dir):
            return {'status': 'ok', 'service': 'MiroFish Backend (frontend build not found)'}, 200
        candidate = os.path.normpath(os.path.join(webroot_dir, path))
        if path and candidate.startswith(webroot_dir) and os.path.isfile(candidate):
            mimetype = 'application/manifest+json' if path.endswith('.webmanifest') else None
            return send_from_directory(webroot_dir, path, mimetype=mimetype)
        return send_from_directory(webroot_dir, 'index.html')
    
    if should_log_startup:
        logger.info("MiroFish Backend 启动完成")
    
    return app

