import sqlite3
import json
import os
import bcrypt
from datetime import datetime
from cryptography.fernet import Fernet
from src.core.config import APP_SECRET_KEY

DB_PATH = os.path.join(os.getcwd(), "data", "database.sqlite")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Garantiza que SQLite respete los borrados en cascada definidos en el esquema.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_cipher():
    if not APP_SECRET_KEY:
        raise ValueError("APP_SECRET_KEY no está configurada. No se puede encriptar/desencriptar.")
    return Fernet(APP_SECRET_KEY.encode())

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        encrypted_api_keys TEXT,
        is_verified INTEGER DEFAULT 0,
        verification_token TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT,
        extra_data TEXT,
        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
    )
    ''')
    
    # Migraciones seguras de columnas opcionales (idempotentes)
    migrations = [
        'ALTER TABLE users ADD COLUMN reset_token TEXT',
        'ALTER TABLE users ADD COLUMN remember_token TEXT',
    ]
    for migration in migrations:
        try:
            cursor.execute(migration)
        except Exception:
            pass  # La columna ya existe — comportamiento esperado

    conn.commit()
    conn.close()

# --- Autenticación y Usuarios ---

def register_user(first_name, last_name, email, username, password):
    import uuid
    conn = get_connection()
    cursor = conn.cursor()
    
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    token = uuid.uuid4().hex
    
    try:
        cursor.execute("INSERT INTO users (first_name, last_name, email, username, password_hash, encrypted_api_keys, is_verified, verification_token) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                       (first_name, last_name, email, username, hashed, json.dumps({}), 0, token))
        conn.commit()
        user_id = cursor.lastrowid
        return True, (user_id, token)
    except sqlite3.IntegrityError as e:
        if "email" in str(e).lower():
            return False, "El correo electrónico ya está registrado."
        return False, "El nombre de usuario ya existe."
    finally:
        conn.close()

def verify_user_token(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE verification_token = ?", (token,))
    row = cursor.fetchone()
    
    if row:
        cursor.execute("UPDATE users SET is_verified = 1, verification_token = NULL WHERE id = ?", (row['id'],))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def verify_login(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash, is_verified FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        if bcrypt.checkpw(password.encode('utf-8'), row['password_hash'].encode('utf-8')):
            if row['is_verified'] == 0:
                return False, "Tu cuenta no está verificada. Por favor, revisa tu correo electrónico para activarla."
            return True, row['id']
    return False, "Usuario o contraseña incorrectos."

def update_api_keys(user_id, api_keys_dict):
    cipher = get_cipher()
    json_str = json.dumps(api_keys_dict)
    encrypted = cipher.encrypt(json_str.encode('utf-8')).decode('utf-8')

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET encrypted_api_keys = ? WHERE id = ?", (encrypted, user_id))
    conn.commit()
    conn.close()

def get_user_api_keys(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT encrypted_api_keys FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['encrypted_api_keys']:
        try:
            cipher = get_cipher()
            decrypted = cipher.decrypt(row['encrypted_api_keys'].encode('utf-8')).decode('utf-8')
            return json.loads(decrypted)
        except Exception as e:
            print(f"Error desencriptando API keys: {e}")
            return {}
    return {}

# --- Chats y Mensajes ---

def create_chat(user_id, title="Nuevo Chat"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chats (user_id, title, updated_at) VALUES (?, ?, ?)", 
                   (user_id, title, datetime.now()))
    conn.commit()
    chat_id = cursor.lastrowid
    conn.close()
    return chat_id

def delete_chat(chat_id):
    """Elimina un chat y todos sus mensajes en cascada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()

def update_chat_title(chat_id, new_title):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
        (new_title, datetime.now(), chat_id)
    )
    conn.commit()
    conn.close()

def get_user_chats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, updated_at FROM chats WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_chat_messages(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content, extra_data FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    
    messages = []
    for row in rows:
        msg = {
            "role": row['role'],
            "content": row['content']
        }
        if row['extra_data']:
            try:
                extra = json.loads(row['extra_data'])
                msg.update(extra)
            except:
                pass
        messages.append(msg)
    return messages

def save_chat_messages(chat_id, messages):
    """Reemplaza los mensajes de un chat por la nueva lista."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    
    for msg in messages:
        # Separar content y role del resto de datos
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        extra_data = {k: v for k, v in msg.items() if k not in ("role", "content")}
        extra_json = json.dumps(extra_data) if extra_data else None
        
        cursor.execute("INSERT INTO messages (chat_id, role, content, extra_data) VALUES (?, ?, ?, ?)",
                       (chat_id, role, content, extra_json))
                       
    cursor.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (datetime.now(), chat_id))
    conn.commit()
    conn.close()

# NOTA: delete_chat está definida arriba (línea ~167) con borrado en cascada correcto.
# Esta segunda definición fue eliminada para evitar la sobrescritura silenciosa.

# --- Remember Me (Token de Sesión Persistente) ---

def update_remember_token(user_id: int, token: str) -> None:
    """Persiste el token de 'Recuérdame' para el usuario dado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET remember_token = ? WHERE id = ?", (token, user_id))
    conn.commit()
    conn.close()

def clear_remember_token(user_id: int) -> None:
    """Elimina el token persistente del usuario (logout o cambio de dispositivo)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET remember_token = NULL WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def verify_remember_token(token: str) -> int | None:
    """
    Verifica el token de sesión persistente.
    Retorna el user_id si el token existe y es válido, None en caso contrario.
    """
    if not token:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE remember_token = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    return row['id'] if row else None

# Inicializar DB al importar
init_db()

def generate_password_reset_token(email):
    import uuid
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT first_name FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, None, None
        
    token = uuid.uuid4().hex
    cursor.execute("UPDATE users SET reset_token = ? WHERE email = ?", (token, email))
    conn.commit()
    conn.close()
    return True, row['first_name'], token

def verify_reset_token(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email FROM users WHERE reset_token = ?", (token,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return True, row['id']
    return False, None

def update_password_with_token(token, new_password):
    success, user_id = verify_reset_token(token)
    if not success:
        return False, "Token inválido o expirado."
        
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ?, reset_token = NULL WHERE id = ?", (hashed, user_id))
    conn.commit()
    conn.close()
    return True, "Contraseña actualizada con éxito."
