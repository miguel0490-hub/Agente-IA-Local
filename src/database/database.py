"""
src/database/database.py — Capa de Persistencia de Datos.
Migrada a SQLAlchemy con arquitectura dual:
- PostgreSQL en producción vía DATABASE_URL
- SQLite local como fallback
"""
import json
import os
import uuid
import bcrypt
import base64
import hashlib
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from sqlalchemy import (
    create_engine,
    text,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
    inspect,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from src.core.logger import get_logger

logger = get_logger(__name__)

# Configuración Dual (PostgreSQL para Prod, SQLite para Local)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/superagente.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite:///"):
    os.makedirs("data", exist_ok=True)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

metadata = MetaData()

users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("first_name", String(255), nullable=False),
    Column("last_name", String(255), nullable=False),
    Column("email", String(255), unique=True, nullable=False),
    Column("username", String(255), unique=True, nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("encrypted_api_keys", Text),
    Column("is_verified", Integer, nullable=False, server_default=text("0")),
    Column("is_admin", Integer, nullable=False, server_default=text("0")),
    Column("is_active", Integer, nullable=False, server_default=text("1")),
    Column("created_at", DateTime, server_default=func.now()),
    Column("verification_token", Text),
    Column("verification_token_expires", DateTime),
    Column("reset_token", Text),
    Column("reset_token_expires", DateTime),
    Column("remember_token", Text),
    Column("remember_token_expires", DateTime),
)

chats_table = Table(
    "chats",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("title", Text, nullable=False),
    Column("updated_at", DateTime, server_default=func.now()),
)

messages_table = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("chat_id", Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
    Column("role", String(50), nullable=False),
    Column("content", Text),
    Column("extra_data", Text),
)


def _is_postgres() -> bool:
    return engine.dialect.name.startswith("postgresql")


def _row_to_dict(row):
    if not row:
        return None
    return dict(row._mapping)


def get_connection():
    """Abre y retorna una conexión SQLAlchemy."""
    return engine.connect()


def get_cipher():
    """Retorna un objeto Fernet inicializado con APP_SECRET_KEY."""
    from src.core.config import APP_SECRET_KEY
    if not APP_SECRET_KEY:
        raise ValueError("APP_SECRET_KEY no está configurada.")
    key_str = APP_SECRET_KEY.strip()

    # Caso ideal: clave Fernet válida (urlsafe base64 de 32 bytes)
    try:
        return Fernet(key_str.encode("utf-8"))
    except Exception:
        pass

    # Compatibilidad: si llega en otro formato, derivar una clave Fernet estable.
    logger.warning("APP_SECRET_KEY no tiene formato Fernet válido. Se derivará una clave estable por compatibilidad.")
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(key_str.encode("utf-8")).digest())
    return Fernet(derived_key)


_ADMIN_BOOTSTRAP_USERNAME = "Miguel0490"


def init_db():
    """Crea tablas y aplica migraciones mínimas compatibles con Postgres/SQLite."""
    metadata.create_all(engine)
    try:
        inspector = inspect(engine)
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "reset_token" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN reset_token TEXT"))
            if "remember_token" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN remember_token TEXT"))
            if "verification_token_expires" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN verification_token_expires TIMESTAMP"))
            if "reset_token_expires" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires TIMESTAMP"))
            if "remember_token_expires" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN remember_token_expires TIMESTAMP"))
            if "is_admin" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"))
            if "is_active" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"))
            if "created_at" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP"))

            # Auto-promote bootstrap admin
            conn.execute(
                text("UPDATE users SET is_admin = 1 WHERE username = :username AND is_admin = 0"),
                {"username": _ADMIN_BOOTSTRAP_USERNAME},
            )
    except Exception as e:
        logger.error(f"Error inicializando/migrando base de datos: {e}")
        raise


def cleanup_expired_tokens() -> None:
    """Purges expired remember/reset/verification tokens."""
    now = datetime.now()
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET remember_token = NULL, remember_token_expires = NULL "
                "WHERE remember_token_expires IS NOT NULL AND remember_token_expires <= :now"
            ),
            {"now": now},
        )
        conn.execute(
            text(
                "UPDATE users SET reset_token = NULL, reset_token_expires = NULL "
                "WHERE reset_token_expires IS NOT NULL AND reset_token_expires <= :now"
            ),
            {"now": now},
        )
        conn.execute(
            text(
                "UPDATE users SET verification_token = NULL, verification_token_expires = NULL "
                "WHERE verification_token_expires IS NOT NULL AND verification_token_expires <= :now"
            ),
            {"now": now},
        )


# --- Autenticación y Usuarios ---
def register_user(first_name, last_name, email, username, password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    token = uuid.uuid4().hex
    token_expires = datetime.now() + timedelta(hours=48)
    try:
        with engine.begin() as conn:
            if _is_postgres():
                user_id = conn.execute(
                    text(
                        "INSERT INTO users (first_name, last_name, email, username, password_hash, encrypted_api_keys, is_verified, verification_token, verification_token_expires) "
                        "VALUES (:first_name, :last_name, :email, :username, :password_hash, :encrypted_api_keys, :is_verified, :verification_token, :verification_token_expires) "
                        "RETURNING id"
                    ),
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "username": username,
                        "password_hash": hashed,
                        "encrypted_api_keys": json.dumps({}),
                        "is_verified": 0,
                        "verification_token": token,
                        "verification_token_expires": token_expires,
                    },
                ).scalar_one()
            else:
                conn.execute(
                    text(
                        "INSERT INTO users (first_name, last_name, email, username, password_hash, encrypted_api_keys, is_verified, verification_token, verification_token_expires) "
                        "VALUES (:first_name, :last_name, :email, :username, :password_hash, :encrypted_api_keys, :is_verified, :verification_token, :verification_token_expires)"
                    ),
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "username": username,
                        "password_hash": hashed,
                        "encrypted_api_keys": json.dumps({}),
                        "is_verified": 0,
                        "verification_token": token,
                        "verification_token_expires": token_expires,
                    },
                )
                user_id = conn.execute(
                    text("SELECT id FROM users WHERE username = :username"),
                    {"username": username},
                ).scalar_one()
        return True, (user_id, token)
    except IntegrityError as e:
        err = str(e).lower()
        if "email" in err:
            return False, "El correo electrónico ya está registrado."
        return False, "El nombre de usuario ya existe."
    except Exception as e:
        logger.error(f"Error registrando usuario '{username}': {e}")
        return False, "No se pudo completar el registro."


def verify_user_token(token):
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT id FROM users "
                "WHERE verification_token = :token "
                "AND verification_token_expires IS NOT NULL "
                "AND verification_token_expires > :now"
            ),
            {"token": token, "now": datetime.now()},
        ).fetchone()
        if row:
            conn.execute(
                text(
                    "UPDATE users SET is_verified = 1, verification_token = NULL, verification_token_expires = NULL "
                    "WHERE id = :user_id"
                ),
                {"user_id": row._mapping["id"]},
            )
            return True
    return False


def verify_login(username, password):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, password_hash, is_verified, is_active FROM users WHERE username = :username"),
            {"username": username},
        ).fetchone()
    if row:
        if bcrypt.checkpw(password.encode("utf-8"), row._mapping["password_hash"].encode("utf-8")):
            if row._mapping.get("is_active", 1) == 0:
                return False, "Tu cuenta ha sido suspendida. Contacta al administrador."
            if row._mapping["is_verified"] == 0:
                return False, "Tu cuenta no está verificada. Por favor, revisa tu correo electrónico para activarla."
            return True, row._mapping["id"]
    return False, "Usuario o contraseña incorrectos."


def get_user_profile(user_id):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT first_name, last_name, email, username FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).fetchone()
    return _row_to_dict(row) or {}


def change_user_password(user_id, old_password, new_password):
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).fetchone()
        if not row:
            return False, "Usuario no encontrado."
        if not bcrypt.checkpw(old_password.encode("utf-8"), row._mapping["password_hash"].encode("utf-8")):
            return False, "La contraseña actual es incorrecta."
        hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        conn.execute(
            text("UPDATE users SET password_hash = :password_hash WHERE id = :user_id"),
            {"password_hash": hashed, "user_id": user_id},
        )
        return True, "Contraseña actualizada con éxito."


def update_api_keys(user_id, api_keys_dict):
    cipher = get_cipher()
    encrypted = cipher.encrypt(json.dumps(api_keys_dict).encode("utf-8")).decode("utf-8")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET encrypted_api_keys = :encrypted WHERE id = :user_id"),
            {"encrypted": encrypted, "user_id": user_id},
        )


def get_user_api_keys(user_id):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT encrypted_api_keys FROM users WHERE id = :user_id"),
            {"user_id": user_id},
        ).fetchone()
    encrypted = row._mapping["encrypted_api_keys"] if row else None
    if encrypted:
        try:
            cipher = get_cipher()
            decrypted = cipher.decrypt(encrypted.encode("utf-8")).decode("utf-8")
            return json.loads(decrypted)
        except Exception:
            logger.error(f"Error interno desencriptando API keys para el usuario {user_id}")
            return {}
    return {}


# --- Administración ---

def is_user_admin(user_id: int) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT is_admin FROM users WHERE id = :uid"), {"uid": user_id}
        ).fetchone()
    return bool(row and row._mapping["is_admin"])


def get_all_users(search_query: str | None = None) -> list[dict]:
    sql = (
        "SELECT id, first_name, last_name, email, username, "
        "is_verified, is_admin, is_active, created_at FROM users"
    )
    params: dict = {}
    if search_query:
        like = f"%{search_query}%"
        sql += (
            " WHERE first_name LIKE :q OR last_name LIKE :q "
            "OR email LIKE :q OR username LIKE :q"
        )
        params["q"] = like
    sql += " ORDER BY id DESC"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [dict(r._mapping) for r in rows]


def get_user_stats() -> dict:
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        verified = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_verified = 1")).scalar() or 0
        active = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_active = 1")).scalar() or 0
        admins = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_admin = 1")).scalar() or 0
        week_ago = datetime.now() - timedelta(days=7)
        recent = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE created_at IS NOT NULL AND created_at >= :d"),
            {"d": week_ago},
        ).scalar() or 0
    return {
        "total": total,
        "verified": verified,
        "active": active,
        "admins": admins,
        "recent_7d": recent,
    }


def toggle_user_active(user_id: int, active: bool) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET is_active = :val WHERE id = :uid"),
            {"val": 1 if active else 0, "uid": user_id},
        )


def admin_delete_user(user_id: int) -> None:
    with engine.begin() as conn:
        chat_ids = conn.execute(
            text("SELECT id FROM chats WHERE user_id = :uid"), {"uid": user_id}
        ).fetchall()
        for row in chat_ids:
            conn.execute(text("DELETE FROM messages WHERE chat_id = :cid"), {"cid": row._mapping["id"]})
        conn.execute(text("DELETE FROM chats WHERE user_id = :uid"), {"uid": user_id})
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})


def set_user_admin(user_id: int, is_admin: bool) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET is_admin = :val WHERE id = :uid"),
            {"val": 1 if is_admin else 0, "uid": user_id},
        )


def force_verify_user(user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET is_verified = 1, verification_token = NULL, "
                "verification_token_expires = NULL WHERE id = :uid"
            ),
            {"uid": user_id},
        )


def admin_reset_password(user_id: int, new_password: str) -> tuple[bool, str]:
    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE users SET password_hash = :pw WHERE id = :uid"),
            {"pw": hashed, "uid": user_id},
        )
        if result.rowcount == 0:
            return False, "Usuario no encontrado."
    return True, "Contraseña reseteada con éxito."


# --- Chats y Mensajes ---
def create_chat(user_id, title="Nuevo Chat"):
    with engine.begin() as conn:
        if _is_postgres():
            chat_id = conn.execute(
                text(
                    "INSERT INTO chats (user_id, title, updated_at) VALUES (:user_id, :title, :updated_at) RETURNING id"
                ),
                {"user_id": user_id, "title": title, "updated_at": datetime.now()},
            ).scalar_one()
        else:
            conn.execute(
                text("INSERT INTO chats (user_id, title, updated_at) VALUES (:user_id, :title, :updated_at)"),
                {"user_id": user_id, "title": title, "updated_at": datetime.now()},
            )
            chat_id = conn.execute(
                text("SELECT id FROM chats WHERE user_id = :user_id ORDER BY id DESC LIMIT 1"),
                {"user_id": user_id},
            ).scalar_one()
    return chat_id


def delete_chat(chat_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM messages WHERE chat_id = :chat_id"), {"chat_id": chat_id})
        conn.execute(text("DELETE FROM chats WHERE id = :chat_id"), {"chat_id": chat_id})


def update_chat_title(chat_id, new_title):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE chats SET title = :title, updated_at = :updated_at WHERE id = :chat_id"),
            {"title": new_title, "updated_at": datetime.now(), "chat_id": chat_id},
        )


def get_user_chats(user_id):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, title, updated_at FROM chats WHERE user_id = :user_id ORDER BY updated_at DESC"),
            {"user_id": user_id},
        ).fetchall()
    return [dict(r._mapping) for r in rows]


def get_chat_messages(chat_id):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT role, content, extra_data FROM messages WHERE chat_id = :chat_id ORDER BY id ASC"),
            {"chat_id": chat_id},
        ).fetchall()

    messages = []
    for row in rows:
        msg = {"role": row._mapping["role"], "content": row._mapping["content"]}
        if row._mapping["extra_data"]:
            try:
                msg.update(json.loads(row._mapping["extra_data"]))
            except Exception:
                logger.error(f"Error parseando extra_data del chat {chat_id}")
        messages.append(msg)
    return messages


def save_chat_messages(chat_id, messages):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM messages WHERE chat_id = :chat_id"), {"chat_id": chat_id})
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            extra_data = {k: v for k, v in msg.items() if k not in ("role", "content")}
            extra_json = json.dumps(extra_data) if extra_data else None
            conn.execute(
                text(
                    "INSERT INTO messages (chat_id, role, content, extra_data) "
                    "VALUES (:chat_id, :role, :content, :extra_data)"
                ),
                {"chat_id": chat_id, "role": role, "content": content, "extra_data": extra_json},
            )
        conn.execute(
            text("UPDATE chats SET updated_at = :updated_at WHERE id = :chat_id"),
            {"updated_at": datetime.now(), "chat_id": chat_id},
        )


# --- Remember Me (Token de Sesión Persistente) ---
def update_remember_token(user_id: int, token: str, expires_at: datetime) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET remember_token = :token, remember_token_expires = :expires_at "
                "WHERE id = :user_id"
            ),
            {"token": token, "expires_at": expires_at, "user_id": user_id},
        )


def clear_remember_token(user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET remember_token = NULL, remember_token_expires = NULL WHERE id = :user_id"),
            {"user_id": user_id},
        )


def verify_remember_token(token: str) -> int | None:
    if not token:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id FROM users "
                "WHERE remember_token = :token "
                "AND remember_token_expires IS NOT NULL "
                "AND remember_token_expires > :now"
            ),
            {"token": token, "now": datetime.now()},
        ).fetchone()
    return row._mapping["id"] if row else None


def generate_password_reset_token(email):
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT first_name FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()
        if not row:
            return False, None, None
        token = uuid.uuid4().hex
        expires_at = datetime.now() + timedelta(hours=1)
        conn.execute(
            text("UPDATE users SET reset_token = :token, reset_token_expires = :expires_at WHERE email = :email"),
            {"token": token, "expires_at": expires_at, "email": email},
        )
        return True, row._mapping["first_name"], token


def verify_reset_token(token):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, email FROM users "
                "WHERE reset_token = :token "
                "AND reset_token_expires IS NOT NULL "
                "AND reset_token_expires > :now"
            ),
            {"token": token, "now": datetime.now()},
        ).fetchone()
    if row:
        return True, row._mapping["id"]
    return False, None


def update_password_with_token(token, new_password):
    success, user_id = verify_reset_token(token)
    if not success:
        return False, "Token inválido o expirado."

    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET password_hash = :password_hash, reset_token = NULL, reset_token_expires = NULL "
                "WHERE id = :user_id"
            ),
            {"password_hash": hashed, "user_id": user_id},
        )
    return True, "Contraseña actualizada con éxito."
