"""Global unified search (Phase 5): chat + notes + doubts across all sessions.

Rendered as a popover at the top of the working area. Selecting a result
switches to that conversation and jumps to the matching excerpt.
"""

import html
import streamlit as st

import core.db as db
import core.text as txt
from ui.context import mark_active


def _jump(conv_id, target, node_id=None):
    st.session_state["current_conv"] = conv_id
    st.session_state["viewing_doc"] = None
    if node_id:
        mark_active(node_id)
    st.session_state["jump_to"] = target


def render_global_search(conv_id):
    """Render the search popover. ``conv_id`` is the currently open session."""
    with st.popover("Search everything (Ctrl+K)", icon=":material/search:",
                    key="global_search"):
        st.caption("Search chat + notes + doubts across all your study sessions.")
        term = st.text_input(
            "Search everything", key="global_search_term",
            placeholder="e.g. gradient descent", label_visibility="collapsed",
        )
        term = (term or "").strip()
        if not term:
            return
        results = db.search_user_contents(term)
        found = any(r["messages"] or r["sections"] or r["doubts"] for r in results)
        if not found:
            st.caption("No matches across your sessions.")
            return
        for res in results:
            c = res["conversation"]
            with st.container(border=True):
                st.markdown(f"**{html.escape(c['title'] or 'Untitled session')}**")
                for m in res["messages"]:
                    who = "You" if m["role"] == "user" else "AI"
                    if st.button(f"💬 {who}: {txt.glimpse(m['content'], term, 60)}",
                                 key=f"gsm_{c['id']}_{m['id']}"):
                        _jump(c["id"], f"msg-{m['id']}")
                for s in res["sections"]:
                    label = txt.glimpse(s["heading"] or s["content"], term, 60)
                    if st.button(f"📝 {label}", key=f"gss_{c['id']}_{s['id']}"):
                        _jump(c["id"], f"sec-{s['node_id']}", node_id=s["node_id"])
                for d in res["doubts"]:
                    label = "Q: " + txt.glimpse(d["question"], term, 50)
                    if st.button(f"❓ {label}", key=f"gsd_{c['id']}_{d['id']}"):
                        _jump(c["id"], f"dbt-{d['id']}", node_id=d["node_id"] or "notes_active")