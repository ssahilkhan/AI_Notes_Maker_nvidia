"""Sidebar: fixed header (new chat / search / subject), independently
scrollable session list with compact rows + context menu, and the pinned
account footer."""

import html

import streamlit as st

import core.db as db
from ui import components
from ui.context import ctx


def _session_time(ts):
    """Compact timestamp: '13:09' today, 'Mon' yesterday-ish, else '30 Aug'."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return ""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if day == today:
        return dt.strftime("%H:%M")
    if (today - day).days == 1:
        return "Yest"
    if (today - day).days < 7:
        return dt.strftime("%a")
    return dt.strftime("%d %b")


def _session_title(c):
    """Ellipsized one-line title for the session row."""
    title = (c["title"] or "New Study Session").replace("\n", " ").strip()
    if len(title) > 46:
        title = title[:43].rstrip() + "…"
    pin = "📌 " if c["pinned"] else ""
    return pin + title


def _session_meta(c):
    parts = [f"{c['message_count']} msgs", f"{c['section_count']} nodes"]
    kc = c["knowledge_count"]
    if kc:
        parts.append(f"🗺 {kc} card{'s' if kc != 1 else ''}")
    t = _session_time(c["updated_at"])
    if t:
        parts.append(t)
    return " · ".join(parts)


def _context_menu(c):
    if st.button("Pin" if not c["pinned"] else "Unpin",
                 icon=":material/push_pin:", key=f"pin_{c['id']}"):
        db.update_conversation(c["id"], pinned=not c["pinned"])
        st.rerun()
    if st.button("Duplicate", icon=":material/content_copy:", key=f"dup_{c['id']}"):
        db.duplicate_conversation(c["id"])
        st.rerun()
    st.divider()
    new_title = st.text_input("Rename to", value=c["title"], key=f"rn_{c['id']}",
                              label_visibility="collapsed", placeholder="Rename to…")
    if st.button("Save rename", icon=":material/check:", key=f"rns_{c['id']}"):
        db.update_conversation(c["id"], title=new_title)
        st.rerun()
    st.divider()
    if st.button("Delete", icon=":material/delete:", key=f"del_{c['id']}"):
        if st.session_state.current_conv == c["id"]:
            st.session_state.current_conv = None
            st.session_state.viewing_doc = None
            st.session_state.notes_active = None
        db.delete_conversation(c["id"])
        st.rerun()


def _session_row(c):
    is_active = (st.session_state.current_conv == c["id"])
    row_container = st.container(
        key="sb_active" if is_active else f"sb_{c['id']}"
    )
    with row_container:
        open_col, act_col = st.columns([6, 1], gap="small", vertical_alignment="center")
        if open_col.button(
            _session_title(c),
            key=f"sel_{c['id']}",
            width="stretch",
            type="primary" if is_active else "tertiary",
        ):
            st.session_state.current_conv = c["id"]
            st.session_state.viewing_doc = None
            st.session_state.notes_active = None
            st.session_state["prev_topic"] = None
            st.rerun()
        with act_col.popover("", icon=":material/more_vert:", key=f"more_{c['id']}"):
            _context_menu(c)
        st.markdown(
            f'<div class="sb-meta">{html.escape(_session_meta(c))}</div>',
            unsafe_allow_html=True,
        )


def _session_list(search):
    conversations = db.list_conversations()
    if search:
        needles = search.lower().split()
        conversations = [
            c for c in conversations
            if all(n in (c["title"] + " " + (c["subject"] or "")).lower() for n in needles)
        ]

    if not conversations:
        st.caption(("No sessions found." if search else "No sessions yet. Start a new chat above."))
        return

    groups = {}
    for c in conversations:
        groups.setdefault(db.group_key(c["updated_at"]), []).append(c)
    if search:
        st.markdown('<div class="sb-group">Results</div>', unsafe_allow_html=True)
    for gname, items in groups.items():
        if not search:
            st.markdown(f'<div class="sb-group">{html.escape(gname)}</div>',
                        unsafe_allow_html=True)
        for c in items:
            _session_row(c)


def render_sidebar(uid, loaded_settings):
    with st.sidebar:
        # ---- FIXED HEADER ----
        with st.container(key="sb_top"):
            st.markdown(
                '<div style="padding:.15rem 0 .3rem .15rem">'
                '<span style="font-size:1.05rem;font-weight:700;color:#1f2430">Study Workspace</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            with st.container(key="sb_newchat"):
                if st.button("＋  New chat", icon=":material/add_circle:", key="new_chat_top",
                             width="stretch", use_container_width=True):
                    new_id = db.create_conversation(st.session_state.get("start_subject", "-"))
                    st.session_state.current_conv = new_id
                    st.session_state.viewing_doc = None
                    st.session_state.notes_active = None
                    st.rerun()
            with st.container(key="sb_search"):
                sc, cc = st.columns([11, 1], gap="small", vertical_alignment="center")
                with sc:
                    search = st.text_input("Search chats…", placeholder="Search chats…",
                                           label_visibility="collapsed", key="search_chats")
                with cc:
                    if st.button("", icon=":material/close:", key="search_clr", type="tertiary",
                                 help="Clear search"):
                        st.session_state["search_chats"] = ""
                        st.rerun()
            with st.container(key="sb_subject"):
                st.selectbox("Subject", ctx.subjects, index=0, key="start_subject",
                             label_visibility="collapsed",
                             help="Subject for new chat (study context).")

        # ---- SCROLLABLE SESSION LIST ----
        with st.container(key="sb_list"):
            _session_list(search)

        # ---- FIXED ACCOUNT FOOTER ----
        with st.container(key="sb_bottom"):
            components.render_footer(ctx, uid, loaded_settings)