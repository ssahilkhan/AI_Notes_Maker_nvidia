"""Shared widgets for the sidebar footer: Settings and Account popovers."""

import html

import streamlit as st

import core.db as db
import core.nim as nim
from ui import layout


def render_footer(ctx, uid, loaded_settings):
    """Render the Settings + Account popovers and persist user preferences.

    Called from the pinned sidebar footer container. Popover bodies always
    execute, so after this returns the widget values live in session_state
    and are written back into ``ctx``.
    """
    with st.container(horizontal=True):
        if st.button("🗺 Knowledge map", icon=":material/mindfulness:", key="kn_open",
                     help="Open the interactive knowledge map for the current session"):
            st.session_state["canvas_mode"] = "split"
            st.rerun()
    with st.popover("Settings", icon=":material/tune:", key="settings_pop"):
        _model_ix = nim.NEMOTRON_MODELS.index(ctx.model) if ctx.model in nim.NEMOTRON_MODELS else 0
        model = st.selectbox("Model", nim.NEMOTRON_MODELS, index=_model_ix, key="set_model")
        thinking = st.checkbox("Enable reasoning (thinking)", value=ctx.thinking, key="set_thinking")
        show_reasoning = st.checkbox("Show reasoning while streaming", value=ctx.show_reasoning,
                                     key="set_show_r")
        verify_answers = st.checkbox("Verify answers (extra check, slower)", value=ctx.verify_answers,
                                     key="set_verify")
        temperature = st.slider("Temperature", 0.0, 2.0, ctx.temperature, 0.05, key="set_temp")
        max_tokens = st.slider("Max tokens", 256, 8192, ctx.max_tokens, 256, key="set_tokens")
        system_prompt = st.text_area("System prompt", value=ctx.system_prompt, height=180,
                                     key="set_system")
        st.caption("Workspace")
        st.session_state.notes_width = st.slider(
            "Notes panel width (%)", 28, 60, ctx.notes_width, 2, key="set_nw",
            help="Keep notes comfortably wide; the chat column adjusts.")
        st.session_state.notes_visible = st.checkbox("Show notes panel", value=ctx.notes_visible,
                                                     key="set_nv")
        st.session_state.panel_h = st.slider("Panel height (px)", 440, 900, ctx.panel_h, 20,
                                             key="set_ph",
                                             help="Height of the chat and notes scroll areas.")
        st.divider()
        st.caption("API key (optional)")
        _own_key = str(loaded_settings.get("api_key", "")).strip()
        st.text_input(
            "Your NVIDIA API key",
            value=_own_key,
            placeholder="nvapi-…",
            type="password",
            key="set_api_key",
            help="Leave empty to use the shared workspace key. If you add your own key, "
                 "your responses will use it instead.",
        )
        st.caption(("Using: your own key." if _own_key else "Using: shared workspace key."))

    with st.popover("Account", icon=":material/account_circle:", key="account_pop"):
        name = st.session_state.get("user_name", "User")
        email = st.session_state.get("user_email", "")
        initial = (name[:1] or "?").upper()
        st.markdown(
            f'<div class="sb-account-row">'
            f'<span class="sb-avatar">{html.escape(initial)}</span>'
            f'<span><span class="sb-account-name">{html.escape(name)}</span>'
            f'<span class="sb-account-email">{html.escape(email)}</span></span></div>',
            unsafe_allow_html=True,
        )
        st.divider()
        if st.button("Logout", icon=":material/logout:", key="logout_btn"):
            layout.logout()

    # Reflect the just-rendered widget values back into ctx and persist them.
    ctx.model = st.session_state["set_model"]
    ctx.thinking = st.session_state["set_thinking"]
    ctx.show_reasoning = st.session_state["set_show_r"]
    ctx.verify_answers = st.session_state["set_verify"]
    ctx.temperature = st.session_state["set_temp"]
    ctx.max_tokens = st.session_state["set_tokens"]
    ctx.system_prompt = st.session_state["set_system"]
    ctx.notes_width = st.session_state.get("notes_width", 38)
    ctx.notes_visible = st.session_state.get("notes_visible", True)
    ctx.panel_h = st.session_state.get("panel_h", 620)

    db.save_user_settings(uid, {
        "model": ctx.model,
        "thinking": ctx.thinking,
        "show_reasoning": ctx.show_reasoning,
        "verify": ctx.verify_answers,
        "temperature": ctx.temperature,
        "max_tokens": ctx.max_tokens,
        "system_prompt": ctx.system_prompt,
        "notes_width": ctx.notes_width,
        "notes_visible": ctx.notes_visible,
        "panel_h": ctx.panel_h,
        "api_key": str(st.session_state.get("set_api_key", "")).strip(),
    })