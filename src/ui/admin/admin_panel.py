"""Admin panel: dashboard de estadísticas, gestión de usuarios y mensajes de contacto."""

from __future__ import annotations

import streamlit as st

from src.core.i18n import t
from src.core.sanitizer import escape_user_data as _esc
from src.database.database import (
    admin_delete_user,
    admin_reset_password,
    delete_contact_message,
    force_verify_user,
    get_all_users,
    get_contact_messages,
    get_contact_stats,
    get_user_stats,
    set_user_admin,
    toggle_user_active,
    update_contact_status,
)


def render_admin_panel() -> None:
    """Renderiza el panel de administración completo dentro de un st.dialog."""
    tab_dash, tab_users, tab_msgs = st.tabs(
        [t("admin_tab_dashboard"), t("admin_tab_users"), t("admin_tab_messages")]
    )

    with tab_dash:
        _render_dashboard()

    with tab_users:
        _render_user_management()

    with tab_msgs:
        _render_contact_messages()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def _render_dashboard() -> None:
    stats = get_user_stats()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("admin_total_users"), stats["total"])
    c2.metric(t("admin_verified"), stats["verified"])
    c3.metric(t("admin_active"), stats["active"])
    c4.metric(t("admin_admins"), stats["admins"])

    st.metric(t("admin_recent_7d"), stats["recent_7d"])

    st.markdown(
        f'<p style="color:#00F2FE;font-size:1.15rem;font-weight:700;margin:1rem 0 0.5rem;">{t("admin_recent_users")}</p>',
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
                f'<strong>@{_esc(u["username"])}</strong> — {_esc(u["first_name"])} {_esc(u["last_name"])} — '
                f'{verified_icon} — <span style="color:#94A3B8;">{date_str}</span></p>',
                unsafe_allow_html=True,
            )
    else:
        st.info(t("admin_no_users"))


# ---------------------------------------------------------------------------
# Gestión de Usuarios
# ---------------------------------------------------------------------------

def _render_user_management() -> None:
    search = st.text_input(t("admin_search_user"), placeholder=t("admin_search_placeholder"))
    users = get_all_users(search_query=search if search else None)

    if not users:
        st.info(t("admin_no_users_found"))
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
                    badges.append(t("admin_badge_admin"))
                if user["is_verified"]:
                    badges.append(t("admin_badge_verified"))
                else:
                    badges.append(t("admin_badge_pending"))
                if user["is_active"]:
                    badges.append(t("admin_badge_active"))
                else:
                    badges.append(t("admin_badge_suspended"))

                st.markdown(f"**@{username}** — {full_name}")
                st.caption(f"{user['email']} · {date_str} · {' · '.join(badges)}")

            with col_actions:
                _render_action_buttons(user, is_self)


def _render_action_buttons(user: dict, is_self: bool) -> None:
    uid = user["id"]

    b1, b2 = st.columns(2)

    with b1:
        if user["is_active"]:
            if st.button(t("admin_suspend"), key=f"deact_{uid}", disabled=is_self, use_container_width=True):
                toggle_user_active(uid, False)
                st.rerun()
        else:
            if st.button(t("admin_activate"), key=f"act_{uid}", use_container_width=True):
                toggle_user_active(uid, True)
                st.rerun()

        if not user["is_verified"]:
            if st.button(t("admin_verify"), key=f"verify_{uid}", use_container_width=True):
                force_verify_user(uid)
                st.rerun()

    with b2:
        if user["is_admin"]:
            if st.button(t("admin_demote"), key=f"demote_{uid}", disabled=is_self, use_container_width=True):
                set_user_admin(uid, False)
                st.rerun()
        else:
            if st.button(t("admin_promote"), key=f"promote_{uid}", use_container_width=True):
                set_user_admin(uid, True)
                st.rerun()

        if st.button(t("admin_delete_user"), key=f"del_{uid}", disabled=is_self, use_container_width=True):
            st.session_state[f"confirm_del_{uid}"] = True

    # Reset password expandable
    with st.expander(t("admin_reset_password"), expanded=False):
        new_pw = st.text_input(t("admin_new_password"), type="password", key=f"pw_{uid}")
        if st.button(t("admin_apply"), key=f"pw_btn_{uid}", use_container_width=True):
            if new_pw and len(new_pw) >= 4:
                ok, msg = admin_reset_password(uid, new_pw)
                if ok:
                    st.success(t(msg))
                else:
                    st.error(t(msg))
            else:
                st.warning(t("admin_min_chars"))

    # Delete confirmation
    if st.session_state.get(f"confirm_del_{uid}"):
        st.warning(t("admin_confirm_delete").replace("{username}", user['username']))
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button(t("admin_confirm"), key=f"cdel_{uid}", use_container_width=True):
                admin_delete_user(uid)
                st.session_state.pop(f"confirm_del_{uid}", None)
                st.rerun()
        with cc2:
            if st.button(t("admin_cancel"), key=f"cancel_del_{uid}", use_container_width=True):
                st.session_state.pop(f"confirm_del_{uid}", None)
                st.rerun()


# ---------------------------------------------------------------------------
# Mensajes de Contacto
# ---------------------------------------------------------------------------

_STATUS_OPTIONS = ["pending", "in_progress", "resolved"]


def _status_labels() -> dict[str, str]:
    return {
        "pending": t("admin_status_pending"),
        "in_progress": t("admin_status_in_progress"),
        "resolved": t("admin_status_resolved"),
    }


def _render_contact_messages() -> None:
    stats = get_contact_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric(t("admin_total_messages"), stats["total"])
    c2.metric(t("admin_pending_messages"), stats["pending"])
    c3.metric(t("admin_resolved_messages"), stats["resolved"])

    filter_col, _ = st.columns([1, 2])
    with filter_col:
        labels = _status_labels()
        status_filter = st.selectbox(
            t("admin_filter_status"),
            options=["all"] + _STATUS_OPTIONS,
            format_func=lambda x, _l=labels: t("admin_filter_all") if x == "all" else _l[x],
            key="contact_filter",
        )

    messages = get_contact_messages(
        status_filter=status_filter if status_filter != "all" else None
    )

    if not messages:
        st.info(t("admin_no_messages"))
        return

    for msg in messages:
        mid = msg["id"]
        created = msg.get("created_at")
        if created and isinstance(created, str):
            from datetime import datetime as _dt
            try:
                created = _dt.strptime(created, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    created = _dt.strptime(created, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    created = None
        date_str = created.strftime("%d/%m/%Y %H:%M") if created else "N/A"
        status_label = _status_labels().get(msg["status"], msg["status"])

        with st.container(border=True):
            st.markdown(
                f'<p style="color:#00F2FE;font-size:1rem;font-weight:700;margin:0 0 4px;">'
                f'{_esc(msg["subject"])}</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<p style="color:#94A3B8;font-size:0.85rem;margin:0 0 8px;">'
                f'{t("admin_contact_from")} <strong style="color:#F8FAFC;">@{_esc(msg["username"])}</strong> '
                f'({_esc(msg["first_name"])} {_esc(msg["last_name"])}) — '
                f'{_esc(msg["email"])} — {date_str} — {status_label}</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="background:#0F172A;border-radius:8px;padding:12px;'
                f'color:#F8FAFC;font-size:0.9rem;line-height:1.5;margin-bottom:8px;">'
                f'{_esc(msg["message"])}</div>',
                unsafe_allow_html=True,
            )

            if msg.get("admin_reply"):
                st.markdown(
                    f'<div style="background:#1A3A2A;border-radius:8px;padding:12px;'
                    f'color:#A7F3D0;font-size:0.9rem;line-height:1.5;margin-bottom:8px;">'
                    f'<strong>{t("admin_reply_label")}</strong><br>{_esc(msg["admin_reply"])}</div>',
                    unsafe_allow_html=True,
                )

            col_status, col_reply, col_delete = st.columns([1, 2, 1])

            with col_status:
                current_idx = _STATUS_OPTIONS.index(msg["status"]) if msg["status"] in _STATUS_OPTIONS else 0
                msg_labels = _status_labels()
                new_status = st.selectbox(
                    t("admin_status_label"),
                    options=_STATUS_OPTIONS,
                    format_func=lambda x, _l=msg_labels: _l[x],
                    index=current_idx,
                    key=f"msg_status_{mid}",
                )
                if new_status != msg["status"]:
                    if st.button(t("admin_update"), key=f"update_st_{mid}", use_container_width=True):
                        update_contact_status(mid, new_status)
                        st.rerun()

            with col_reply:
                reply = st.text_input(t("admin_reply_input"), key=f"reply_{mid}", placeholder=t("admin_reply_placeholder"))
                if st.button(t("admin_reply_button"), key=f"reply_btn_{mid}", use_container_width=True):
                    if reply and reply.strip():
                        update_contact_status(mid, "resolved", admin_reply=reply.strip())
                        st.rerun()
                    else:
                        st.warning(t("admin_reply_empty"))

            with col_delete:
                if st.button(t("admin_delete_user"), key=f"del_msg_{mid}", use_container_width=True):
                    st.session_state[f"confirm_del_msg_{mid}"] = True

                if st.session_state.get(f"confirm_del_msg_{mid}"):
                    if st.button(t("admin_confirm"), key=f"cdel_msg_{mid}", use_container_width=True):
                        delete_contact_message(mid)
                        st.session_state.pop(f"confirm_del_msg_{mid}", None)
                        st.rerun()
                    if st.button(t("admin_cancel"), key=f"cancel_del_msg_{mid}", use_container_width=True):
                        st.session_state.pop(f"confirm_del_msg_{mid}", None)
                        st.rerun()
