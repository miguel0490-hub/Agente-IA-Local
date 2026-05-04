import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def send_verification_email(to_email: str, first_name: str, token: str) -> bool:
    """Envía el correo de verificación con estilo Total Dark Premium."""
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        print("Faltan credenciales SMTP en el archivo .env. No se pudo enviar el correo de verificación.")
        return False

    # URL base de la aplicación. Asumimos localhost:8501 si no hay dominio configurado.
    base_url = os.getenv("APP_URL", "http://localhost:8501")
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

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg['Subject'] = "⚡ Activa tu cuenta en SuperAgente IA Pro"
    msg.attach(MIMEText(html_content, 'html'))

    try:
        # Usa starttls si el puerto es distinto de 465, de lo contrario SSL
        port = int(smtp_port)
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port)
        else:
            server = smtplib.SMTP(smtp_server, port)
            server.starttls()
            
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        return False

def send_password_reset_email(to_email: str, first_name: str, token: str) -> bool:
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        print("Faltan credenciales SMTP en el archivo .env.")
        return False

    base_url = os.getenv("APP_URL", "http://localhost:8501")
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

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg['Subject'] = "⚡ Recuperación de Contraseña"
    msg.attach(MIMEText(html_content, 'html'))

    try:
        port = int(smtp_port)
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port)
        else:
            server = smtplib.SMTP(smtp_server, port)
            server.starttls()
            
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error al enviar correo de reseteo: {e}")
        return False
