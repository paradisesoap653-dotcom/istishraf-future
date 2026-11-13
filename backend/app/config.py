"""\n配置管理\n统一从项目根目录的 .env 文件加载配置\n"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')
serverless_tmp_env = '/tmp/.env'

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
elif os.path.exists(serverless_tmp_env):
    load_dotenv(serverless_tmp_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)

_IS_SERVERLESS = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
_DEFAULT_UPLOAD_DIR = '/tmp/istishraf_uploads' if _IS_SERVERLESS else os.path.join(os.path.dirname(__file__), '../uploads')


class Config:
    """Flask配置类"""
    
    IS_SERVERLESS = _IS_SERVERLESS
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    # في الاختبارات نسمح بالطلبات المجهولة افتراضيًا حتى لا تتعطل اختبارات
    # الوحدة القديمة؛ اضبط ISTISHRAF_ENFORCE_AUTH_IN_TESTING=1 لاختبار
    # الحراسة نفسها.
    ENFORCE_AUTH_IN_TESTING = os.environ.get('ISTISHRAF_ENFORCE_AUTH_IN_TESTING', '').lower() in ('1', 'true', 'yes')
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # نماذج بديلة على نفس المزوّد تُستخدم تلقائيًا عند نفاد الحصة اليومية
    # (كل نموذج على Groq له حصة يومية منفصلة، فتناوب النماذج يضاعف السعة مجانًا).
    LLM_FALLBACK_MODELS = os.environ.get('LLM_FALLBACK_MODELS', '')

    # مزوّدون بديلون (OpenAI-compatible) على شكل JSON، مثال:
    # [{"base_url":"https://api.cerebras.ai/v1","model":"gpt-oss-120b","api_key_env":"CEREBRAS_API_KEY"}]
    LLM_FALLBACK_PROVIDERS = os.environ.get('LLM_FALLBACK_PROVIDERS', '')
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # التخزين الدائم (Neon PostgreSQL). عند غيابه يعمل التطبيق بملفات محلية
    # فقط، وهو ما يعني فقدان البيانات على serverless.
    DATABASE_URL = (os.environ.get('DATABASE_URL') or '').strip()

    # المهام الطويلة: تُنفّذ في عامل مستقل عبر الطابور الدائم افتراضيًا.
    # ISTISHRAF_INLINE_TASKS=1 يعيد السلوك القديم (تنفيذ داخل الطلب).
    INLINE_LONG_TASKS = os.environ.get('ISTISHRAF_INLINE_TASKS', '').lower() in ('1', 'true', 'yes')
    JOB_LEASE_SECONDS = int(os.environ.get('ISTISHRAF_JOB_LEASE_SECONDS', '600'))
    # رمز حماية مسار /api/worker/tick (يُقبل أيضًا CRON_SECRET الذي يضيفه Vercel)
    WORKER_TOKEN = (os.environ.get('ISTISHRAF_WORKER_TOKEN') or os.environ.get('CRON_SECRET') or '').strip()
    WORKER_TICK_BUDGET = float(os.environ.get('ISTISHRAF_WORKER_TICK_BUDGET', '240'))
    JOB_POLL_SECONDS = float(os.environ.get('ISTISHRAF_JOB_POLL_SECONDS', '3'))
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.environ.get('ISTISHRAF_UPLOAD_DIR', _DEFAULT_UPLOAD_DIR)
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '3' if _IS_SERVERLESS else '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(UPLOAD_FOLDER, 'simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '2' if _IS_SERVERLESS else '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '0' if _IS_SERVERLESS else '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证必要配置"""
        errors: list[str] = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        if os.environ.get("ZEP_API_URL"):
            errors.append("ZEP_API_URL 不受支持；MiroFish 仅连接 Zep Cloud")
        if cls.DEBUG:
            import warnings
            warnings.warn("Flask DEBUG mode is enabled. Do not use in production.", RuntimeWarning)
        return errors
