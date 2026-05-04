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
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        encrypted_api_keys TEXT
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
    
    conn.commit()
    conn.close()

# --- Autenticación y Usuarios ---

def register_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    try:
        cursor.execute("INSERT INTO users (username, password_hash, encrypted_api_keys) VALUES (?, ?, ?)", 
                       (username, hashed, json.dumps({})))
        conn.commit()
        user_id = cursor.lastrowid
        return True, user_id
    except sqlite3.IntegrityError:
        return False, "El nombre de usuario ya existe."
    finally:
        conn.close()

def verify_login(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        if bcrypt.checkpw(password.encode('utf-8'), row['password_hash'].encode('utf-8')):
            return True, row['id']
    return False, "Usuario o contraseña incorrectos."

def update_api_keys(user_id, api_keys_dict):
    cipher = get_cipher()
    # Serializar a string JSON y luego encriptar
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

def delete_chat(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()

# Inicializar DB al importar
init_db()
