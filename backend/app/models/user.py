"""
نظام إدارة المستخدمين والصلاحيات لتطبيق «استشراف المستقبل»
يعتمد على SQLite المدمج لحفظ الحسابات وربط المشاريع والمحاكاة بكل مستخدم بشكل مستقل وآمن
"""

import os
import re
import sqlite3
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from flask import request
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from ..config import Config

_db_lock = threading.Lock()
TOKEN_MAX_AGE_SECONDS = 30 * 24 * 3600  # 30 days


class UserStore:
    """مدير قاعدة بيانات المستخدمين وملكية الموارد"""

    @staticmethod
    def _db_path() -> str:
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        return os.path.join(Config.UPLOAD_FOLDER, 'istishraf_users.db')

    @classmethod
    def _conn(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(cls._db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls) -> None:
        with _db_lock:
            with cls._conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'user',
                        daily_quota INTEGER NOT NULL DEFAULT 5,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS resource_owners (
                        resource_type TEXT NOT NULL,
                        resource_id TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (resource_type, resource_id)
                    )
                    """
                )
                conn.commit()

    @classmethod
    def count_users(cls) -> int:
        cls.init_db()
        with cls._conn() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
            return int(row["cnt"]) if row else 0

    @classmethod
    def create_user(cls, name: str, email: str, password: str) -> Dict[str, Any]:
        cls.init_db()
        clean_name = (name or "").strip()
        clean_email = (email or "").strip().lower()

        if len(clean_name) < 2:
            raise ValueError("يرجى إدخال الاسم الكامل (حرفان على الأقل)")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email):
            raise ValueError("يرجى إدخال بريد إلكتروني صحيح")
        if not password or len(password) < 6:
            raise ValueError("يجب أن تتكون كلمة المرور من 6 أحرف أو أرقام على الأقل")

        admin_email_env = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()

        with _db_lock:
            with cls._conn() as conn:
                existing = conn.execute(
                    "SELECT id FROM users WHERE email = ?", (clean_email,)
                ).fetchone()
                if existing:
                    raise ValueError("هذا البريد الإلكتروني مسجّل بالفعل، يرجى تسجيل الدخول")

                total_Row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
                is_first_user = (int(total_Row["cnt"]) == 0)
                is_admin = is_first_user or (admin_email_env and clean_email == admin_email_env)

                role = "admin" if is_admin else "user"
                quota = 999 if is_admin else int(os.environ.get("DEFAULT_USER_DAILY_QUOTA", "5"))
                now_iso = datetime.now().isoformat()
                pw_hash = generate_password_hash(password)

                cur = conn.execute(
                    """
                    INSERT INTO users (name, email, password_hash, role, daily_quota, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (clean_name, clean_email, pw_hash, role, quota, now_iso),
                )
                conn.commit()
                user_id = cur.lastrowid

        return {
            "id": user_id,
            "name": clean_name,
            "email": clean_email,
            "role": role,
            "daily_quota": quota,
            "created_at": now_iso,
        }

    @classmethod
    def authenticate(cls, email: str, password: str) -> Optional[Dict[str, Any]]:
        cls.init_db()
        clean_email = (email or "").strip().lower()
        with cls._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (clean_email,)
            ).fetchone()
            if not row:
                return None
            if not check_password_hash(row["password_hash"], password or ""):
                return None
            return {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "role": row["role"],
                "daily_quota": row["daily_quota"],
                "created_at": row["created_at"],
            }

    @classmethod
    def get_user_by_id(cls, user_id: int) -> Optional[Dict[str, Any]]:
        cls.init_db()
        with cls._conn() as conn:
            row = conn.execute(
                "SELECT id, name, email, role, daily_quota, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    @classmethod
    def list_users(cls) -> List[Dict[str, Any]]:
        cls.init_db()
        with cls._conn() as conn:
            rows = conn.execute(
                "SELECT id, name, email, role, daily_quota, created_at FROM users ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    @classmethod
    def assign_owner(cls, resource_type: str, resource_id: str, user_id: int) -> None:
        cls.init_db()
        now_iso = datetime.now().isoformat()
        with _db_lock:
            with cls._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO resource_owners (resource_type, resource_id, user_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (resource_type, resource_id, user_id, now_iso),
                )
                conn.commit()

    @classmethod
    def get_owner_id(cls, resource_type: str, resource_id: str) -> Optional[int]:
        cls.init_db()
        with cls._conn() as conn:
            row = conn.execute(
                "SELECT user_id FROM resource_owners WHERE resource_type = ? AND resource_id = ?",
                (resource_type, resource_id),
            ).fetchone()
            return int(row["user_id"]) if row else None

    @classmethod
    def count_today_usage(cls, user_id: int) -> int:
        cls.init_db()
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        with cls._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM resource_owners
                WHERE resource_type = 'project' AND user_id = ? AND created_at LIKE ?
                """,
                (user_id, f"{today_prefix}%"),
            ).fetchone()
            return int(row["cnt"]) if row else 0

    @classmethod
    def can_access(cls, resource_type: str, resource_id: str, user: Optional[Dict[str, Any]]) -> bool:
        owner_id = cls.get_owner_id(resource_type, resource_id)
        # Public / sample resources (no owner_id) are accessible to all users
        if owner_id is None:
            return True
        if not user:
            return False
        if user.get("role") == "admin":
            return True
        return int(user.get("id")) == int(owner_id)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(Config.SECRET_KEY, salt="istishraf-auth-v1")


def issue_auth_token(user: Dict[str, Any]) -> str:
    return _serializer().dumps({"uid": user["id"], "role": user["role"]})


def verify_auth_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        uid = payload.get("uid")
        if not uid:
            return None
        return UserStore.get_user_by_id(int(uid))
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None


def get_current_user() -> Optional[Dict[str, Any]]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        return verify_auth_token(token)
    return None
