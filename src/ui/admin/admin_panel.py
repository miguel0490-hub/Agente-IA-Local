"""Admin panel: dashboard de estadísticas y gestión de usuarios."""

from __future__ import annotations

import streamlit as st

from src.database.database import (
    admin_delete_user,
    admin_reset_password,
    force_verify_user,
    get_all_users,
    get_user_stats,
    set_user_admin,
    toggle_user_active,
)


def render_admin_panel() -> None:
    """Renderiza el panel de administración completo dentro de un st.dialog."""
    tab_dash, tab_users = st.tabs(["📊 Dashboard", "👥 Gestión de Usuarios"])

    with tab_dash:
        _render_dashboard()

    with tab_users:
        _render_user_management()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def _render_dashboard() -> None:
    stats = get_user_stats()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Usuarios", stats["total"])
    c2.metric("Verificados", stats["verified"])
    c3.metric("Activos", stats["active"])
    c4.metric("Admins", stats["admins"])

    st.metric("Registros últimos 7 días", stats["recent_7d"])

    st.markdown(
        '<p style="color:#00F2FE;font-size:1.15rem;font-weight:700;margin:1rem 0 0.5rem;">Últimos usuarios registrados</p>',
        unsafe_allow_html=True,
    )
    users = get_all_users()
    recent = users[:5]
    if recent:
        for u in recent:
            created = u.get("created_at")
            date_str = created.strftime("%d/%m/%Y %H:%M") if created else "N/A"
            verified_icon = "✅" if u["is_verified"] else "❌"
            st.markdown(
                f'<p style="color:#F8FAFC;font-size:0.95rem;margin:4px 0;">'
                f'<strong>@{u["username"]}</strong> — {u["first_name"]} {u["last_name"]} — '
                f'{verified_icon} — <span style="color:#94A3B8;">{date_str}</span></p>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No hay usuarios registrados.")


# ---------------------------------------------------------------------------
# Gestión de Usuarios
# ---------------------------------------------------------------------------

def _render_user_management() -> None:
    search = st.text_input("🔍 Buscar usuario", placeholder="Nombre, email o username...")
    users = get_all_users(search_query=search if search else None)

    if not users:
        st.info("No se encontraron usuarios.")
        return

    current_user_id = st.session_state.get("user_id")

    for user in users:
        uid = user["id"]
        is_self = uid == current_user_id
        username = user["username"]
        full_name = f"{user['first_name']} {user['last_name']}"
        created = user.get("created_at")
        date_str = created.strftime("%d/%m/%Y %H:%M") if created else "N/A"

        with st.container(border=True):
            col_info, col_actions = st.columns([3, 2])

            with col_info:
                badges = []
                if user["is_admin"]:
                    badges.append("🛡️ Admin")
                if user["is_verified"]:
                    badges.append("✅ Verificado")
                else:
                    badges.append("⏳ Pendiente")
                if user["is_active"]:
                    badges.append("🟢 Activo")
                else:
                    badges.append("🔴 Suspendido")

                st.markdown(f"**@{username}** — {full_name}")
                st.caption(f"{user['email']} · {date_str} · {' · '.join(badges)}")

            with col_actions:
                _render_action_buttons(user, is_self)


def _render_action_buttons(user: dict, is_self: bool) -> None:
    uid = user["id"]

    b1, b2 = st.columns(2)

    with b1:
        if user["is_active"]:
            if st.button("⏸ Suspender", key=f"deact_{uid}", disabled=is_self, use_container_width=True):
                toggle_user_active(uid, False)
                st.rerun()
        else:
            if st.button("▶ Activar", key=f"act_{uid}", use_container_width=True):
                toggle_user_active(uid, True)
                st.rerun()

        if not user["is_verified"]:
            if st.button("✅ Verificar", key=f"verify_{uid}", use_container_width=True):
                force_verify_user(uid)
                st.rerun()

    with b2:
        if user["is_admin"]:
            if st.button("⬇ Quitar Admin", key=f"demote_{uid}", disabled=is_self, use_container_width=True):
                set_user_admin(uid, False)
                st.rerun()
        else:
            if st.button("⬆ Hacer Admin", key=f"promote_{uid}", use_container_width=True):
                set_user_admin(uid, True)
                st.rerun()

        if st.button("🗑 Eliminar", key=f"del_{uid}", disabled=is_self, use_container_width=True):
            st.session_state[f"confirm_del_{uid}"] = True

    # Reset password expandable
    with st.expander("🔑 Resetear contraseña", expanded=False):
        new_pw = st.text_input("Nueva contraseña", type="password", key=f"pw_{uid}")
        if st.button("Aplicar", key=f"pw_btn_{uid}", use_container_width=True):
            if new_pw and len(new_pw) >= 4:
                ok, msg = admin_reset_password(uid, new_pw)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.warning("Mínimo 4 caracteres.")

    # Delete confirmation
    if st.session_state.get(f"confirm_del_{uid}"):
        st.warning(f"¿Eliminar a @{user['username']}? Se borrarán todos sus datos.")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Confirmar", key=f"cdel_{uid}", type="primary", use_container_width=True):
                admin_delete_user(uid)
                st.session_state.pop(f"confirm_del_{uid}", None)
                st.rerun()
        with cc2:
            if st.button("Cancelar", key=f"cancel_del_{uid}", use_container_width=True):
                st.session_state.pop(f"confirm_del_{uid}", None)
                st.rerun()
