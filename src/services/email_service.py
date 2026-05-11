import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple
from dotenv import load_dotenv
from src.core.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


def _resolve_app_url() -> str:
    """
    Resuelve la URL base pública para links de verificación/reset.
    Prioridad:
    1) APP_URL (recomendado en producción)
    2) STREAMLIT_SERVER_PORT (inyectado por app.py en runtime local)
    3) Fallback histórico localhost:8501
    """
    explicit = (os.getenv("APP_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    runtime_port = (os.getenv("STREAMLIT_SERVER_PORT") or "").strip()
    if runtime_port:
        return f"http://localhost:{runtime_port}"
    return "http://localhost:8501"


def _get_smtp_config() -> Optional[Tuple[str, str, str, str, str]]:
    """Devuelve (server, port, user, password, from) o None si faltan credenciales."""
    server = os.getenv("SMTP_SERVER")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")

    if not all([server, port, user, password]):
        logger.error("Faltan credenciales SMTP en el archivo .env.")
        return None

    # SMTP_FROM permite un remitente distinto al usuario de autenticación.
    smtp_from = (os.getenv("SMTP_FROM") or "").strip() or user
    return server, port, user, password, smtp_from


def _send_email(to: str, subject: str, html_body: str) -> bool:
    """Construye el mensaje MIME y lo envía vía SMTP."""
    cfg = _get_smtp_config()
    if cfg is None:
        return False

    server_host, port_str, user, password, smtp_from = cfg

    msg = MIMEMultipart()
    msg["From"] = smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        port = int(port_str)
        if port == 465:
            srv = smtplib.SMTP_SSL(server_host, port)
        else:
            srv = smtplib.SMTP(server_host, port)
            srv.starttls()

        srv.login(user, password)
        srv.send_message(msg)
        srv.quit()
        return True
    except Exception as e:
        logger.error(f"Error al enviar correo a {to}: {e}")
        return False


def send_verification_email(to_email: str, first_name: str, token: str) -> bool:
    """Envía el correo de verificación con estilo Total Dark Premium."""
    base_url = _resolve_app_url()
    verification_link = f"{base_url}/?token={token}"

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Verifica tu cuenta Premium</title>
    </head>
    <body style="background-color: #0F172A; padding: 40px; font-family: Arial, sans-serif; margin: 0;">
        <div style="background-color: #1E293B; border-radius: 12px; padding: 30px; text-align: center; max-width: 500px; margin: 0 auto; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
            <h1 style="color: #2FF3E0; margin-bottom: 20px;">⚡ SuperAgente IA Pro</h1>
            <p style="color: #F8FAFC; font-size: 16px; line-height: 1.5; margin-bottom: 30px;">
                Hola {first_name}, gracias por registrarte. Para activar tu cuenta Premium, haz clic en el botón de abajo.
            </p>
            <a href="{verification_link}" style="background-color: #2FF3E0; color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; margin-top: 20px;">
                Activar Cuenta Premium
            </a>
            <p style="color: #64748B; font-size: 12px; margin-top: 40px;">
                Si no solicitaste esta cuenta, puedes ignorar este correo de forma segura.
            </p>
        </div>
    </body>
    </html>
    """

    return _send_email(to_email, "⚡ Activa tu cuenta en SuperAgente IA Pro", html_content)


def send_password_reset_email(to_email: str, first_name: str, token: str) -> bool:
    """Envía el correo de recuperación de contraseña."""
    base_url = _resolve_app_url()
    reset_link = f"{base_url}/?reset_token={token}"

    html_content = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="background-color: #0F172A; padding: 40px; font-family: Arial, sans-serif; margin: 0;">
        <div style="background-color: #1E293B; border-radius: 12px; padding: 30px; text-align: center; max-width: 500px; margin: 0 auto;">
            <h1 style="color: #2FF3E0; margin-bottom: 20px;">⚡ SuperAgente IA Pro</h1>
            <p style="color: #F8FAFC; font-size: 16px; line-height: 1.5; margin-bottom: 30px;">
                Hola {first_name}, hemos recibido una solicitud para restablecer tu contraseña. Haz clic en el botón de abajo para crear una nueva.
            </p>
            <a href="{reset_link}" style="background-color: #2FF3E0; color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                Restablecer Contraseña
            </a>
            <p style="color: #64748B; font-size: 12px; margin-top: 40px;">
                Si no solicitaste este cambio, puedes ignorar este correo.
            </p>
        </div>
    </body>
    </html>
    """

    return _send_email(to_email, "⚡ Recuperación de Contraseña", html_content)
