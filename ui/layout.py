"""Page configuration, CSS injection, auth screen and app-level JS helpers."""

import html

import streamlit as st

import core.auth as auth
import core.db as db
from ui.context import ctx


def configure_page():
    st.set_page_config(
        page_title="AI Study Workspace",
        page_icon=":material/school:",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_styles():
    if ctx.upload_dir is None:
        from pathlib import Path

        ctx.upload_dir = Path(__file__).resolve().parent.parent / "data" / "uploads"
    st.html(
        """<style>
    .block-container { max-width: 100%; padding-right: 1.4rem; padding-left: 1.4rem; padding-bottom: 3rem; }
    html, body, [data-testid="stAppViewContainer"] { background: #fafaf7; }
    .katex { font-size: 1.04em; }
    table { border-collapse: collapse; }
    td, th { border: 1px solid #e2e5e9; padding: .3rem .55rem; }
    pre { background: #f2f3f5; border-radius: 6px; padding: .6rem .8rem; line-height: 1.5; }
    :focus-visible { outline: 2px solid #2563eb; outline-offset: 1px; border-radius: 4px; }

    /* node badge */
    .nb { display: inline-flex; align-items: center; justify-content: center; min-width: 1.45rem;
          height: 1.45rem; padding: 0 .28rem; border-radius: 6px; font-size: .7rem; font-weight: 700;
          color: #fff; margin-right: .5rem; vertical-align: middle; }
    .b-blue   { background: #3b82f6; } .b-purple { background: #8b5cf6; }
    .b-green  { background: #16a34a; } .b-teal   { background: #0d9488; }
    .b-orange { background: #ea580c; } .b-cyan   { background: #0891b2; }
    .b-amber  { background: #d97706; } .b-gray   { background: #6b7280; }

    /* node rail */
    .rail-wrap { min-height: 74vh; }
    .node-rail { position: sticky; top: 4.5rem; display: flex; flex-direction: column;
                 align-items: center; gap: .4rem; padding: .4rem .15rem; }
    .rail-node { display: block; width: 2.1rem; text-align: center; padding: .32rem 0;
                 border-radius: .45rem; border: 1px solid transparent; text-decoration: none;
                 transition: background .12s ease, border-color .12s ease; }
    .rn { display: inline-block; font-size: .68rem; font-weight: 700; color: #4b5563;
          width: 1.4rem; line-height: 1.4rem; border-radius: 5px; }
    .rail-node:hover { border-color: #d3d8df; background: #fff; }
    .rail-node.active { border-color: #3b82f6; background: #eef4ff; }
    .rail-node.active .rn { color: #1d4ed8; }
    .rc-blue   { color: #2563eb; } .rc-purple { color: #7c3aed; }
    .rc-green  { color: #15803d; } .rc-teal   { color: #0f766e; }
    .rc-orange { color: #c2410c; } .rc-cyan   { color: #0e7490; }
    .rc-amber  { color: #b45309; } .rc-gray   { color: #6b7280; }
    @media (max-width: 900px) {
        .rail-wrap { min-height: 0; }
        .node-rail { flex-direction: row; flex-wrap: wrap; position: static; }
    }

    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 8px; }
    [data-testid="stChatMessage"] { padding-top: .35rem; padding-bottom: .35rem; }
    .stSectionFoot { display: none; }

    /* ---- Study Sessions sidebar redesigned ---- */
    /* Sidebar body is a fixed column: pinned header + pinned account footer
       wrap an independently scrollable session list. Streamlit nests the
       sidebar content in inline wrappers (no stable classes), so the whole
       chain is coerced into one flex column sized to the viewport. */
    [data-testid="stSidebarContent"] { display: flex !important; flex-direction: column !important;
                                       height: 100vh !important; overflow: hidden !important; }
    [data-testid="stSidebarContent"] > :last-child { display: flex !important; flex-direction: column !important;
                                                      min-height: 0 !important; height: 100% !important; }
    [data-testid="stSidebarContent"] > :last-child > div { flex: 1 1 0% !important; min-height: 0 !important;
                                                           height: auto !important; display: flex !important;
                                                           flex-direction: column !important; }
    [data-testid="stSidebarContent"] > :last-child > div > div.stVerticalBlock { min-height: 0 !important;
                                                                                height: 100% !important;
                                                                                overflow: hidden !important; }
    [data-testid="stSidebarContent"] > :last-child > div > div.stVerticalBlock > div:has(> .st-key-sb_top),
    [data-testid="stSidebarContent"] > :last-child > div > div.stVerticalBlock > div:has(> .st-key-sb_bottom) {
        flex: 0 0 auto !important; }
    [data-testid="stSidebarContent"] > :last-child > div > div.stVerticalBlock > div:has(> .st-key-sb_top) {
        padding-bottom: .2rem; background: #ffffff; }
    [data-testid="stSidebarContent"] > :last-child > div > div.stVerticalBlock > div:has(> .st-key-sb_bottom) {
        padding-top: .4rem; background: #ffffff; }
    [data-testid="stSidebarContent"] > :last-child > div > div.stVerticalBlock > div:has(> .st-key-sb_list) {
        flex: 1 1 auto !important; min-height: 0 !important; overflow-y: auto !important;
        display: flex !important; flex-direction: column !important; }
    .st-key-sb_list { flex: 0 0 auto !important; overflow: visible !important; min-height: 0 !important;
                      padding-top: .15rem; padding-right: .15rem; }

    /* session list rows */
    .st-key-sb_list [data-testid="stVerticalBlock"] { gap: .1rem; }
    .st-key-sb_list .stHorizontalBlock { flex-wrap: nowrap !important; }

    /* session rows: title button + meta line */
    .st-key-sb_list [data-testid="stVerticalBlock"] { gap: .12rem; }
    .st-key-sb_list .stButton button { height: 32px; text-align: left; padding: .2rem .55rem;
                                       font-size: .86rem; font-weight: 600; color: #1f2430;
                                       border-radius: 6px; }
    .st-key-sb_list .stButton button:hover { background: #f1f3f4; }
    .st-key-sb_active .stButton button { background: #edf2fc; color: #1d4ed8; }
    .st-key-sb_active .stButton button:hover { background: #e3ecfb; }
    .st-key-sb_active .stButton button::before { content: "● "; color: #2563eb; font-weight: 700; }
    .sb-meta { font-size: .72rem; color: #6b7280; line-height: 1.3; white-space: nowrap;
               overflow: hidden; text-overflow: ellipsis; margin: .02rem 0 .15rem .55rem; }

    /* compact ⋮ action trigger (icon-only popover button) */
    .st-key-sb_list [data-testid="stPopover"] button { min-width: 28px; height: 28px; padding: 0;
                                                       align-items: center; justify-content: center; }
    .st-key-sb_list [data-testid="stPopover"] [data-testid="stIconMaterial"] { font-size: 1.15rem; }

    /* compact new-chat, search and subject */
    .st-key-sb_newchat button { height: 32px; border-radius: 8px; }
    .st-key-sb_search input { height: 32px; border-radius: 8px; }
    .st-key-sb_search [data-testid="stButton"] button { min-width: 28px; height: 28px; padding: 0;
                                                        align-items: center; justify-content: center; }
    .st-key-sb_subject [data-baseweb="select"] { height: 34px; border-radius: 8px; }
    .st-key-sb_subject > div { margin-bottom: 0; }

    /* compact group headers */
    .sb-group { font-size: .66rem; font-weight: 700; letter-spacing: .05em;
                color: #9aa0a6; text-transform: uppercase; margin: .5rem 0 .1rem .45rem; }

    /* compact account / settings footer popover triggers */
    .st-key-sb_bottom [data-testid="stBaseButton-secondary"] { height: 32px; }

    /* blocked tooltips for ordinary rows; keep them tiny where they exist */
    [data-testid="stSidebar"] [role="tooltip"] { max-width: 180px; white-space: normal; }

    /* ---- Phase 1 polish ---- */
    .st-key-sb_list .stButton button,
    .st-key-sb_list [data-testid="stPopover"] button {
        transition: background-color .15s ease, border-color .15s ease; }
    .st-key-sb_active .stButton button {
        border-left: 3px solid #2563eb; padding-left: .45rem; }
    .st-key-sb_active .stButton button::before { content: ""; }
    .sb-group { font-size: .62rem; letter-spacing: .07em; color: #b0b6bd;
                margin: .55rem 0 .15rem .5rem; }
    .st-key-sb_bottom { border-top: 1px solid #e9ebee; }
    .st-key-sb_search input { transition: box-shadow .18s ease; }
    .st-key-sb_search:focus-within input { box-shadow: 0 0 0 2px rgba(37,99,235,.18); }
    .sb-account-row { display: flex; align-items: center; }
    .sb-avatar { display: inline-flex; align-items: center; justify-content: center;
                 width: 2.1rem; height: 2.1rem; border-radius: 50%;
                 background: #eef4ff; color: #2563eb; font-weight: 700;
                 font-size: .9rem; margin-right: .65rem; flex: 0 0 auto; }
    .sb-account-name { font-weight: 600; color: #1f2430; display: block; }
    .sb-account-email { font-size: .74rem; color: #6b7280; display: block; }
    [data-testid="stPopover"] [data-testid="stVerticalBlock"] { gap: .1rem; }

    /* ---- Phase 2: rich learning responses ---- */
    [class*="st-key-nc"] button { border: 1px dashed #2563eb; color: #2563eb;
                                  background: #f5f8ff; border-radius: 999px;
                                  padding: .05rem .6rem; font-size: .78rem;
                                  min-height: 0; height: 27px; }
    [class*="st-key-nc"] button:hover { background: #e3ecfb; }
    [data-testid="stChatMessage"] blockquote { margin: .35rem 0; padding: .45rem .8rem;
                                               background: #fbfcff; border-left: 3px solid #2563eb;
                                               border-radius: 0 6px 6px 0; }
    /* Phase 4: hidden JS->Python bridge input for canvas drag persistence */
    [class*="st-key-kn_draft"] { position: fixed; left: -9999px; top: 0;
                                 width: 1px; height: 1px; overflow: hidden; opacity: 0; }
    </style>"""
    )


# ---------------------------------------------------------------------------
# Simple local authentication (V1): username/email + password
# ---------------------------------------------------------------------------

def start_session(user):
    st.session_state["authenticated"] = True
    st.session_state["user_id"] = user["id"]
    st.session_state["user_name"] = user["name"]
    st.session_state["user_email"] = user["email"]
    db.set_current_user(user["id"])


def logout():
    db.set_current_user(None)
    st.session_state["auth_page"] = "login"
    keep = {"auth_page"}
    for key in list(st.session_state.keys()):
        if key not in keep:
            del st.session_state[key]
    st.rerun()


def render_auth_screen():
    page = st.session_state.get("auth_page", "login")
    st.markdown(
        "<div style='text-align:center; margin-top:2.5rem'>"
        "<div style='font-size:1.9rem; font-weight:700'>AI Study Workspace</div>"
        "<div style='color:#6b7280; margin-top:.25rem'>Your AI-powered study companion</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    lc, mc, rc = st.columns([1, 1.3, 1], vertical_alignment="center")
    with mc:
        if page == "login":
            email = st.text_input("Email / Username", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login", type="primary"):
                user = auth.login(email, password)
                if user is None:
                    st.error("Incorrect email or password.")
                else:
                    start_session(user)
                    st.rerun()
            if st.button("Create account"):
                st.session_state["auth_page"] = "register"
                st.rerun()
        else:
            name = st.text_input("Name", key="reg_name")
            email = st.text_input("Email / Username", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_password", help="At least 8 characters")
            confirm = st.text_input("Confirm password", type="password", key="reg_confirm")
            if st.button("Create Account", type="primary"):
                error = auth.register_error(name, email, password, confirm)
                if error:
                    st.error(error)
                else:
                    try:
                        user = auth.create_user(name, email, password)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        start_session(user)
                        st.rerun()
            if st.button("Back to login"):
                st.session_state["auth_page"] = "login"
                st.rerun()


# ---------------------------------------------------------------------------
# App-level JS helpers
# ---------------------------------------------------------------------------

def emit_scroll(target):
    js = (
        "<script>(()=>{const el=document.getElementById(" + repr(target)
        + "); if(el){el.scrollIntoView({behavior:'smooth', block:'start'});}})();</script>"
    )
    try:
        st.html(js, unsafe_allow_javascript=True)
    except Exception:
        pass


def emit_rail_observer():
    js = """
    <script>
    try {
      const nodes = {};
      document.querySelectorAll('.rail-node').forEach(n => { nodes[n.dataset.target] = n; });
      const secs = document.querySelectorAll('[id^="sec-"]');
      if (nodes && 'IntersectionObserver' in window) {
        const io = new IntersectionObserver(entries => {
          entries.forEach(e => {
            const self = nodes[e.target.id];
            if (self && e.isIntersecting) {
              document.querySelectorAll('.rail-node').forEach(x => x.classList.toggle('active', x === self));
            }
          });
        }, { rootMargin: '-15% 0px -60% 0px', threshold: [0, 0.01] });
        secs.forEach(s => io.observe(s));
      }
    } catch (err) {}
    </script>
    """
    try:
        st.html(js, unsafe_allow_javascript=True)
    except Exception:
        pass


def jump():
    target = st.session_state.pop("jump_to", None)
    if target:
        emit_scroll(target)


def render_columns():
    """Build the working columns. Returns (main_c, rail_c, notes_c, canvas_c).

    rail_c / notes_c are None when the notes panel is hidden; canvas_c is None
    unless the knowledge map is open (split: chat + map, full: map only).
    Must be called after the sidebar (settings popover) has run so that
    session_state.notes_width / notes_visible are current.
    """
    mode = st.session_state.get("canvas_mode")
    if mode == "full":
        return st.container(), None, None, st.container()
    if mode == "split":
        main_c, canvas_c = st.columns([1.15, 1], gap="small",
                                      vertical_alignment="top", wrap=True)
        return main_c, None, None, canvas_c
    nw = st.session_state.notes_width if st.session_state.notes_visible else 0
    if nw > 0:
        main_w = max(22, 100 - nw - 10)
        main_c, rail_c, notes_c = st.columns([main_w, 10, nw], gap="small",
                                             vertical_alignment="top", wrap=True)
    else:
        main_c = st.container()
        rail_c = None
        notes_c = None
    return main_c, rail_c, notes_c, None