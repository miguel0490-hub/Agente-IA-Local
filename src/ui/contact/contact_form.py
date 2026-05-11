"""Formulario de contacto para que los usuarios se comuniquen con el administrador."""

from __future__ import annotations

import streamlit as st

from src.database.database import create_contact_message, get_admin_emails, get_user_profile
from src.services.email_service import _send_email


def render_contact_form() -> None:
    """Renderiza el formulario de contacto dentro de un st.dialog."""
    st.markdown(
        '<p style="color:#94A3B8;font-size:0.9rem;margin-bottom:1rem;">'
        "Envía un mensaje al equipo de administración. "
        "Te responderemos lo antes posible.</p>",
        unsafe_allow_html=True,
    )

    SUBJECT_OPTIONS = [
        "Reportar un problema",
        "Sugerencia o mejora",
        "Problema con mi cuenta",
        "Consulta general",
        "Otro",
    ]

    with st.form("contact_form", clear_on_submit=True):
        subject = st.selectbox("Asunto", options=SUBJECT_OPTIONS)
        message = st.text_area(
            "Mensaje",
            placeholder="Describe tu consulta o problema con el mayor detalle posible...",
            height=150,
        )
        submitted = st.form_submit_button("Enviar mensaje", use_container_width=True)

        if submitted:
            if not message or len(message.strip()) < 10:
                st.warning("Por favor, escribe un mensaje de al menos 10 caracteres.")
            else:
                user_id = st.session_state.get("user_id")
                create_contact_message(user_id, subject, message.strip())
                _notify_admins(user_id, subject, message.strip())
                st.success("Mensaje enviado correctamente. El administrador lo revisará pronto.")


def _notify_admins(user_id: int, subject: str, message: str) -> None:
    """Envía notificación por email a todos los admins."""
    profile = get_user_profile(user_id)
    username = profile.get("username", "desconocido")
    full_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
    user_email = profile.get("email", "")

    admin_emails = get_admin_emails()
    if not admin_emails:
        return

    html = f"""
    <html>
    <body style="background-color:#0F172A;padding:40px;font-family:Arial,sans-serif;">
      <div style="background:#1E293B;border-radius:12px;padding:30px;max-width:550px;margin:0 auto;">
        <h2 style="color:#00F2FE;margin-top:0;">Nuevo mensaje de contacto</h2>
        <table style="color:#F8FAFC;font-size:15px;width:100%;border-collapse:collapse;">
          <tr><td style="padding:6px 0;color:#94A3B8;width:100px;">Usuario:</td>
              <td style="padding:6px 0;"><strong>@{username}</strong> ({full_name})</td></tr>
          <tr><td style="padding:6px 0;color:#94A3B8;">Email:</td>
              <td style="padding:6px 0;">{user_email}</td></tr>
          <tr><td style="padding:6px 0;color:#94A3B8;">Asunto:</td>
              <td style="padding:6px 0;"><strong>{subject}</strong></td></tr>
        </table>
        <div style="background:#0F172A;border-radius:8px;padding:16px;margin-top:16px;color:#F8FAFC;font-size:14px;line-height:1.6;">
          {message.replace(chr(10), '<br>')}
        </div>
        <p style="color:#64748B;font-size:12px;margin-top:24px;">
          Responde desde el Panel de Administración de SuperAgente IA Pro.
        </p>
      </div>
    </body>
    </html>
    """

    for email in admin_emails:
        _send_email(email, f"[Contacto] {subject} — @{username}", html)
