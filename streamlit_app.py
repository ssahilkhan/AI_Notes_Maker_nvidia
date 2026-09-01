import pathlib

import streamlit as st

import core.db as db
import core.nim as nim
import core.prompts as prompts
import ui.canvas as canvas
import ui.chat as chat
import ui.layout as layout
import ui.notes as notes
import ui.search as search
import ui.sidebar as sidebar
from ui.context import ctx

UPLOAD_DIR = pathlib.Path(__file__).parent / "data" / "uploads"
ctx.upload_dir = UPLOAD_DIR

layout.configure_page()
layout.inject_styles()


# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------

if not st.session_state.get("authenticated"):
    layout.render_auth_screen()
    st.stop()

db.set_current_user(st.session_state["user_id"])
_uid = st.session_state["user_id"]

# Load this user's saved preferences. Widgets are given these as their creation
# defaults, so no manual session_state seeding is needed (and no widget/session
# policy conflicts occur). After the widgets render, current values are logged
# back into ctx by the settings footer.
_loaded_settings = db.get_user_settings(_uid)


def _d(key, default):
    return _loaded_settings.get(key, default)


ctx.model = st.session_state.get("set_model", _d("model", nim.NEMOTRON_MODELS[0]))
ctx.thinking = st.session_state.get("set_thinking", _d("thinking", True))
ctx.show_reasoning = st.session_state.get("set_show_r", _d("show_reasoning", False))
ctx.verify_answers = st.session_state.get("set_verify", _d("verify", False))
ctx.temperature = st.session_state.get("set_temp", _d("temperature", 1.0))
ctx.max_tokens = st.session_state.get("set_tokens", _d("max_tokens", 2048))
ctx.system_prompt = st.session_state.get("set_system", _d("system_prompt", prompts.ACADEMIC_SYSTEM_PROMPT))
ctx.notes_width = st.session_state.get("notes_width", _d("notes_width", 38))
ctx.notes_visible = st.session_state.get("notes_visible", _d("notes_visible", True))
ctx.panel_h = st.session_state.get("panel_h", _d("panel_h", 620))


@st.cache_resource
def _client(api_key):
    return nim.build_client(api_key)


def _effective_api_key():
    saved = str(_loaded_settings.get("api_key", "")).strip()
    widget = str(st.session_state.get("set_api_key", saved)).strip()
    return widget or nim.get_api_key()


api_key = _effective_api_key()
if not api_key:
    st.info("The shared NVIDIA API key is not configured yet. Ask the administrator "
            "to set `NVIDIA_API_KEY` in the server's `.env`.")
    st.stop()

ctx.client = _client(api_key)

st.session_state.setdefault("current_conv", None)
st.session_state.setdefault("viewing_doc", None)
st.session_state.setdefault("notes_active", None)


# ---------------------------------------------------------------------------
# Layout: sidebar (fixed header + scrollable sessions + account footer),
# then the working columns (chat | rail | notes).
# ---------------------------------------------------------------------------

sidebar.render_sidebar(_uid, _loaded_settings)

conv_id = st.session_state.current_conv
ctx.panel_h = int(st.session_state.get("panel_h", 620))

main_c, rail_c, notes_c, canvas_c = layout.render_columns()

_canvas_mode = st.session_state.get("canvas_mode")

with main_c:
    search.render_global_search(conv_id)
    if _canvas_mode != "full":
        chat.render_chat_main(ctx, conv_id)

if _canvas_mode in ("full", "split"):
    with canvas_c:
        canvas.render_canvas(conv_id)
else:
    notes.render_rail(rail_c, conv_id)
    notes.render_notes_panel(conv_id, notes_c, main_c)