import os
import sqlite3
from functools import wraps

from itsdangerous import BadSignature, SignatureExpired
from werkzeug.security import check_password_hash, generate_password_hash


def ensure_admin_table(db_path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS local_admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        auth_required = os.environ.get("SAU_AUTH_REQUIRED", "0").strip().lower() in {
            "1", "true", "yes", "on"
        }
        default_username = os.environ.get("SAU_ADMIN_USER", "admin").strip() or "admin"
        default_password = os.environ.get("SAU_ADMIN_PASSWORD", "").strip()
        if auth_required and not default_password:
            raise RuntimeError("启用认证时必须设置 SAU_ADMIN_PASSWORD")
        if auth_required:
            cursor.execute(
                """
                INSERT INTO local_admins (username, password_hash, display_name)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (default_username, generate_password_hash(default_password), "Administrator"),
            )
        conn.commit()


def get_admin_by_username(db_path, username):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM local_admins WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def verify_admin(admin, password):
    return bool(admin and check_password_hash(admin["password_hash"], password))


def public_user(admin):
    return {
        "id": admin["id"],
        "username": admin["username"],
        "displayName": admin["display_name"],
    }


def create_token(serializer, admin):
    return serializer.dumps({
        "id": admin["id"],
        "username": admin["username"],
        "display_name": admin["display_name"],
    })


def parse_token(serializer, auth_header="", query_token=None, max_age=None):
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        token = query_token
    if not token:
        return None
    try:
        return serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def auth_required(parse_admin, unauthorized_response):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            admin = parse_admin()
            if not admin:
                return unauthorized_response()
            return fn(admin, *args, **kwargs)
        return wrapper
    return decorator
