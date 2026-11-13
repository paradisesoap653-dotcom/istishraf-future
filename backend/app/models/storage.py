"""
طبقة التخزين لتطبيق «استشراف المستقبل».

المشكلة التي تحلّها: كان كل شيء (الحسابات، المشاريع، الملفات المرفوعة،
المهام، المحاكاة) يُخزَّن في ``/tmp`` على serverless، وهو نظام ملفات مؤقت
يُفقد مع كل cold start أو إعادة نشر. النتيجة: مشاريع المستخدم تختفي،
والحسابات تُفقد، والنظام يتصرّف كأنه بلا مستخدمين.

الحل: **مرآة دائمة**. الملفات تُكتب على القرص المحلي (كي تعمل المكتبات التي
تحتاج مسارات حقيقية: pandas وpypdf وopenpyxl...) وتُنسخ في الوقت نفسه إلى
جدول ``stored_files`` في PostgreSQL (Neon). وعند القراءة، إن لم يكن الملف
موجودًا محليًا (نسخة جديدة أو عامل آخر)، يُجلَب من Postgres ويُعاد إنشاؤه
محليًا ثم يُقرأ.

بهذا لا تتغير توقيعات الدوال ولا مسارات HTTP، لكن المحتوى يعيش.

المتغير المطلوب: ``DATABASE_URL``. عند غيابه تبقى الطبقة محلية بالكامل
(سلوك التطوير)، ويعلن ``/health`` أن التخزين غير دائم.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import threading
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger("mirofish.storage")

_schema_ready = False
_schema_lock = threading.Lock()
_pool = None
_pool_lock = threading.Lock()

_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS stored_files (
        path TEXT PRIMARY KEY,
        content BYTEA NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS stored_files_path_prefix
        ON stored_files (path text_pattern_ops)
    """,
)


# --------------------------------------------------------------------------
# الاتصال
# --------------------------------------------------------------------------

def database_url() -> str:
    from ..config import Config

    return (getattr(Config, "DATABASE_URL", "") or "").strip()


def is_durable() -> bool:
    """هل التخزين الدائم مفعّل؟"""
    return bool(database_url())


def _pool_instance():
    """مجمّع اتصالات واحد لكل نسخة.

    على serverless كل طلب يفتح اتصالًا جديدًا إلى Neon = زمن TLS إضافي في
    كل عملية تخزين. المجمّع يجعل الاتصال يُعاد استخدامه داخل النسخة نفسها.
    """
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            from psycopg_pool import ConnectionPool

            _pool = ConnectionPool(
                conninfo=database_url(),
                min_size=1,
                max_size=4,
                timeout=10,
                kwargs={"autocommit": True},
                open=True,
            )
    return _pool


def _connect():
    """سياق اتصال من المجمّع: ``with _connect() as conn:``"""
    return _pool_instance().connection()


def _close_pool_at_exit() -> None:
    global _pool
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
        _pool = None


atexit.register(_close_pool_at_exit)


def reset_pool() -> None:
    """يُستخدم في الاختبارات وبعد تغيير DATABASE_URL."""
    global _pool, _schema_ready
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                pass
        _pool = None
        _schema_ready = False


def _ensure_schema(conn) -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        with conn.cursor() as cur:
            for statement in _SCHEMA_SQL:
                cur.execute(statement)
        _schema_ready = True


def check_connection() -> bool:
    """فحص اتصال حقيقي (يستخدمه /health)."""
    if not is_durable():
        return False
    try:
        with _connect() as conn:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1
    except Exception as exc:  # pragma: no cover - يعتمد على الشبكة
        logger.warning(f"Postgres health check failed: {exc}")
        return False


# --------------------------------------------------------------------------
# مفاتيح المسارات
# --------------------------------------------------------------------------

def _root() -> str:
    from ..config import Config

    return os.path.abspath(Config.UPLOAD_FOLDER)


def _key(path: str) -> str:
    """مفتاح نسبي ثابت داخل مجلد الرفع."""
    absolute = os.path.abspath(path)
    try:
        relative = os.path.relpath(absolute, _root())
    except ValueError:  # pragma: no cover - أحجام أقراص مختلفة
        relative = os.path.basename(absolute)
    return relative.replace(os.sep, "/")


def _local(path: str) -> str:
    return os.path.abspath(path)


# --------------------------------------------------------------------------
# عمليات Postgres
# --------------------------------------------------------------------------

def _pg_put(key: str, content: bytes) -> None:
    if not is_durable():
        return
    try:
        with _connect() as conn:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO stored_files (path, content, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (path) DO UPDATE
                        SET content = EXCLUDED.content, updated_at = now()
                    """,
                    (key, content),
                )
    except Exception as exc:
        logger.error(f"الكتابة في Postgres فشلت للمسار {key}: {exc}")


def _pg_get(key: str) -> Optional[bytes]:
    if not is_durable():
        return None
    try:
        with _connect() as conn:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT content FROM stored_files WHERE path = %s", (key,))
                row = cur.fetchone()
                return bytes(row[0]) if row else None
    except Exception as exc:
        logger.error(f"القراءة من Postgres فشلت للمسار {key}: {exc}")
        return None


def _pg_exists(key: str) -> bool:
    if not is_durable():
        return False
    try:
        with _connect() as conn:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM stored_files WHERE path = %s OR path LIKE %s LIMIT 1",
                    (key, f"{key.rstrip('/')}/%"),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def _pg_listdir(key: str) -> List[str]:
    if not is_durable():
        return []
    prefix = key.rstrip("/") + "/" if key else ""
    try:
        with _connect() as conn:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT split_part(substr(path, %s), '/', 1) AS name
                    FROM stored_files
                    WHERE path LIKE %s
                    """,
                    (len(prefix) + 1, prefix + "%"),
                )
                return sorted({row[0] for row in cur.fetchall() if row[0]})
    except Exception as exc:
        logger.error(f"قراءة قائمة المجلد من Postgres فشلت للمسار {key}: {exc}")
        return []


def _pg_delete(key: str, recursive: bool) -> None:
    if not is_durable():
        return
    try:
        with _connect() as conn:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM stored_files WHERE path = %s", (key,))
                if recursive:
                    cur.execute(
                        "DELETE FROM stored_files WHERE path LIKE %s",
                        (f"{key.rstrip('/')}/%",),
                    )
    except Exception as exc:
        logger.error(f"الحذف من Postgres فشل للمسار {key}: {exc}")


# --------------------------------------------------------------------------
# الواجهة العامة
# --------------------------------------------------------------------------

def ensure_local(path: str) -> str:
    """اجعل الملف موجودًا على القرص المحلي وأعد مساره المطلق."""
    absolute = _local(path)
    if os.path.exists(absolute):
        return absolute

    content = _pg_get(_key(path))
    if content is None:
        raise FileNotFoundError(absolute)

    os.makedirs(os.path.dirname(absolute) or ".", exist_ok=True)
    with open(absolute, "wb") as handle:
        handle.write(content)
    return absolute


def exists(path: str) -> bool:
    absolute = _local(path)
    if os.path.exists(absolute):
        return True
    return _pg_exists(_key(path))


def write_bytes(path: str, content: bytes) -> None:
    absolute = _local(path)
    os.makedirs(os.path.dirname(absolute) or ".", exist_ok=True)
    with open(absolute, "wb") as handle:
        handle.write(content)
    _pg_put(_key(path), content)


def read_bytes(path: str) -> bytes:
    absolute = ensure_local(path)
    with open(absolute, "rb") as handle:
        return handle.read()


def write_text(path: str, text: str) -> None:
    write_bytes(path, text.encode("utf-8"))


def read_text(path: str) -> Optional[str]:
    try:
        return read_bytes(path).decode("utf-8")
    except FileNotFoundError:
        return None


def write_json(path: str, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def read_json(path: str) -> Optional[Any]:
    raw = read_text(path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"ملف JSON تالف: {path}")
        return None


def save_stream(path: str, file_storage) -> int:
    """احفظ FileStorage (رفع Flask) ثم انسخه إلى Postgres. يعيد الحجم."""
    absolute = _local(path)
    os.makedirs(os.path.dirname(absolute) or ".", exist_ok=True)
    file_storage.save(absolute)
    size = os.path.getsize(absolute)
    with open(absolute, "rb") as handle:
        _pg_put(_key(path), handle.read())
    return size


def push_file(path: str) -> None:
    """انسخ ملفًا موجودًا على القرص إلى التخزين الدائم (لمكتبات تكتب بنفسها)."""
    absolute = _local(path)
    if not os.path.isfile(absolute):
        return
    try:
        with open(absolute, "rb") as handle:
            _pg_put(_key(path), handle.read())
    except OSError as exc:
        logger.error(f"تعذر نسخ الملف إلى التخزين الدائم: {path} ({exc})")


def size(path: str) -> int:
    absolute = _local(path)
    if os.path.exists(absolute):
        return os.path.getsize(absolute)
    content = _pg_get(_key(path))
    return len(content) if content is not None else 0


def listdir(path: str) -> List[str]:
    """أسماء العناصر داخل مجلد (ملفات ومجلدات) من المصدرين."""
    absolute = _local(path)
    names = set()
    if os.path.isdir(absolute):
        names.update(os.listdir(absolute))
    if is_durable():
        names.update(_pg_listdir(_key(path)))
    return sorted(names)


def list_files(path: str) -> List[str]:
    """مسارات الملفات داخل مجلد (دون مجلدات فرعية)."""
    absolute = _local(path)
    result = []
    for name in listdir(path):
        candidate = os.path.join(absolute, name)
        if os.path.isfile(candidate):
            result.append(candidate)
            continue
        if os.path.isdir(candidate):
            continue
        # موجود في Postgres فقط: نُنزّله ليعمل كملف حقيقي
        try:
            result.append(ensure_local(candidate))
        except FileNotFoundError:
            continue
    return result


def remove(path: str) -> bool:
    absolute = _local(path)
    removed = False
    if os.path.isfile(absolute):
        os.remove(absolute)
        removed = True
    _pg_delete(_key(path), recursive=False)
    return removed or is_durable()


def rmtree(path: str) -> bool:
    absolute = _local(path)
    removed = False
    if os.path.isdir(absolute):
        shutil.rmtree(absolute)
        removed = True
    _pg_delete(_key(path), recursive=True)
    return removed or is_durable()


def makedirs(path: str) -> str:
    absolute = _local(path)
    os.makedirs(absolute, exist_ok=True)
    return absolute


def isdir(path: str) -> bool:
    """هل المسار مجلد؟ يتحقق من القرص ثم من التخزين الدائم (cold start)."""
    if os.path.isdir(_local(path)):
        return True
    if is_durable():
        try:
            return bool(_pg_listdir(_key(path)))
        except Exception:  # pragma: no cover - قاعدة غير متاحة
            return False
    return False


def storage_info() -> Dict[str, Any]:
    """"ملخص حالة التخزين — يُستخدم في /health بلا أسرار."""
    return {
        "backend": "postgres" if is_durable() else "local",
        "durable": is_durable(),
        "root": _root(),
    }
