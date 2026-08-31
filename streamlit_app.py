import html
import re
import time
from pathlib import Path

import streamlit as st

import core.auth as auth
import core.db as db
import core.images as images
import core.memory as memory
import core.nim as nim
import core.notes as notes
import core.pdf as pdf
import core.prompts as prompts
import core.text as txt

UPLOAD_DIR = Path(__file__).parent / "data" / "uploads"

UNFOLD_MESSAGES = 6   # keep this many most-recent messages fully unfolded
DEFAULT_PANEL_H = 620

SUBJECTS = [
    "-",
    "Deep Learning",
    "Machine Learning",
    "DBMS",
    "Computer Networks",
    "Operating Systems",
    "Data Structures",
    "Mathematics",
    "Python",
    "Web Development",
    "Other",
]

SUGGESTIONS = {
    ":blue[:material/science:] Explain supervised learning": (
        "Define supervised learning, explain its working with an example, its advantages, limitations and applications."
    ),
    ":green[:material/functions:] Bayes theorem basics": (
        "Explain Bayes' theorem with its formula, an example, and key applications in machine learning."
    ),
    ":purple[:material/network_intake:] OSI model layers": (
        "Explain the seven layers of the OSI model with the function and example protocol of each layer."
    ),
}

st.set_page_config(
    page_title="AI Study Workspace",
    page_icon=":material/school:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles():
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

    /* ---- Study Sessions sidebar redesign ---- */
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
    .st-key-sb_subject [data-baseweb="select"] { height: 34px; border-radius: 8px; }
    .st-key-sb_subject > div { margin-bottom: 0; }

    /* compact group headers */
    .sb-group { font-size: .66rem; font-weight: 700; letter-spacing: .05em;
                color: #9aa0a6; text-transform: uppercase; margin: .5rem 0 .1rem .45rem; }

    /* compact account / settings footer popover triggers */
    .st-key-sb_bottom [data-testid="stBaseButton-secondary"] { height: 32px; }

    /* blocked tooltips for ordinary rows; keep them tiny where they exist */
    [data-testid="stSidebar"] [role="tooltip"] { max-width: 180px; white-space: normal; }
    </style>"""
    )


inject_styles()


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


def auth_screen():
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


if not st.session_state.get("authenticated"):
    auth_screen()
    st.stop()

db.set_current_user(st.session_state["user_id"])
_uid = st.session_state["user_id"]

# Load this user's saved preferences. Widgets are given these as their creation
# defaults, so no manual session_state seeding is needed (and no widget/session
# policy conflicts occur). After the widgets render, current values are logged below.
_loaded_settings = db.get_user_settings(_uid)


def _d(key, default):
    return _loaded_settings.get(key, default)


model = st.session_state.get("set_model", _d("model", nim.NEMOTRON_MODELS[0]))
thinking = st.session_state.get("set_thinking", _d("thinking", True))
show_reasoning = st.session_state.get("set_show_r", _d("show_reasoning", False))
verify_answers = st.session_state.get("set_verify", _d("verify", False))
temperature = st.session_state.get("set_temp", _d("temperature", 1.0))
max_tokens = st.session_state.get("set_tokens", _d("max_tokens", 2048))
system_prompt = st.session_state.get("set_system", _d("system_prompt", prompts.ACADEMIC_SYSTEM_PROMPT))
notes_width = st.session_state.get("notes_width", _d("notes_width", 38))
notes_visible = st.session_state.get("notes_visible", _d("notes_visible", True))
panel_h = st.session_state.get("panel_h", _d("panel_h", DEFAULT_PANEL_H))


@st.cache_resource
def _client(api_key):
    return nim.build_client(api_key)


def derive_title(text):
    line = (text or "").strip().splitlines()[0]
    line = re.sub(r"[#*`_\]\[()>]", "", line)
    return (line[:60] or "New Study Session").strip()


def stream_and_answer(client, model, messages, thinking, show_reasoning, temperature, max_tokens):
    status = st.status("Thinking…", expanded=show_reasoning) if thinking else None
    holder = st.empty()
    answer_text = ""
    error = None
    answered = False
    try:
        stream = nim.stream_chat(
            client,
            model,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking=thinking,
        )
        for kind, value in nim.iter_stream(stream):
            if kind == "reasoning":
                if status and show_reasoning:
                    status.markdown(value)
            elif kind == "content":
                if status and not answered:
                    status.update(label="Answered", state="complete", expanded=False)
                    answered = True
                answer_text += value
                holder.markdown(txt.render_md_text(answer_text) + "▌")
    except Exception as exc:
        error = str(exc)
        holder.error(f"Request failed: {exc}")
    if status and not answered:
        state = "error" if error else "complete"
        status.update(label="Failed" if error else "Completed", state=state, expanded=False)
    if answer_text:
        holder.markdown(txt.render_md_text(answer_text))
    return (answer_text, error)


def run_action_llm(client, model, system_prompt, conv_id, instruction, temperature=0.4, max_tokens=2048):
    system = system_prompt
    mem_block = memory.build_memory_block(db, conv_id)
    if mem_block:
        system = system + "\n\nSTUDY SESSION MEMORY (context only):\n" + mem_block
    messages = [{"role": "system", "content": system}]
    for m in db.get_messages(conv_id, limit=12):
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": instruction})
    return nim.complete_chat(client, model, messages, temperature=temperature, max_tokens=max_tokens)


def extract_mermaid(text):
    m = re.search(r"```mermaid\s*(.*?)\s*```", text, re.S)
    return m.group(1).strip() if m else (text or "").strip()


def jump():
    target = st.session_state.pop("jump_to", None)
    if target:
        emit_scroll(target)


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


def add_note_section(conv_id, heading, kind, content):
    main_doc = db.get_or_create_main_document(conv_id)
    node_id = notes.new_node_id()
    db.upsert_section(
        main_doc["id"], node_id, len(db.get_sections(main_doc["id"])) + 1, heading, kind, content
    )
    st.session_state.viewing_doc = main_doc["id"]
    return node_id


def mark_active(node_id):
    st.session_state["notes_active"] = node_id


EXAM_DEPTHS = {
    "2": "2-3 lines, only the definition and the single most important point",
    "5": "5-6 sentences: definition, concept, working, one example",
    "10": "8-12 sentences: definition, concept, working, formula, example, advantages, limitations",
    "15": "a full answer: definition, concept, working, formula, derivation, example, advantages, limitations, applications, conclusion",
}


def render_section(conv_id, doc_id, sec, system_prompt, client, model, temperature, max_tokens):
    node = sec["node_id"]
    badge = txt.KIND_BADGE.get(sec["kind"], "T")
    color = txt.KIND_COLOR.get(sec["kind"], "gray")
    blabel = txt.KIND_LABEL.get(sec["kind"], "Note")
    heading_esc = html.escape(sec["heading"] or "")

    with st.container(border=True):
        st.markdown(f'<div id="sec-{node}"></div>', unsafe_allow_html=True)

        row = st.container(horizontal=True)
        row.markdown(
            f'<span class="nb b-{color}" title="{blabel}">{badge}</span><b>{heading_esc}</b>',
            unsafe_allow_html=True,
        )
        if row.button("", icon=":material/help:", help=f"Ask a doubt about “{heading_esc}”", key=f"askt_{node}"):
            st.session_state[f"askopen_{node}"] = not st.session_state.get(f"askopen_{node}", False)
        if row.button("", icon=":material/edit:", help="Edit this section", key=f"edtt_{node}"):
            st.session_state[f"editopen_{node}"] = not st.session_state.get(f"editopen_{node}", False)
        with st.popover("", icon=":material/more_vert:", help="More actions", key=f"mor_{node}"):
            if st.button("Explain simpler", key=f"simp_{node}"):
                with st.spinner("Simplifying…"):
                    out = run_action_llm(client, model, system_prompt, conv_id,
                                         prompts.SIMPLIFY_ACTION_PROMPT.format(content=sec["content"]))
                new_content = sec["content"] + "\n\n**In simpler terms:**\n" + out
                db.update_section_content(sec["id"], new_content)
                mark_active(node)
                st.rerun()
            if st.button("Give example", key=f"ex_{node}"):
                with st.spinner("Adding example…"):
                    out = run_action_llm(client, model, system_prompt, conv_id,
                                         prompts.EXAMPLE_ACTION_PROMPT.format(content=sec["content"]))
                db.update_section_content(sec["id"], sec["content"] + "\n\n" + out)
                mark_active(node)
                st.rerun()
            if st.button("Expand", key=f"exp_{node}"):
                with st.spinner("Expanding…"):
                    out = run_action_llm(client, model, system_prompt, conv_id,
                                         prompts.EXPAND_ACTION_PROMPT.format(content=sec["content"]))
                db.update_section_content(sec["id"], sec["content"] + "\n\n**Extended detail:**\n" + out)
                mark_active(node)
                st.rerun()
            if st.button("Summarise", key=f"sum_{node}"):
                with st.spinner("Summarising…"):
                    out = run_action_llm(client, model, system_prompt, conv_id,
                                         prompts.SUMMARIZE_ACTION_PROMPT.format(content=sec["content"]))
                db.update_section_content(sec["id"], sec["content"] + "\n\n**Summary:**\n" + out)
                mark_active(node)
                st.rerun()
            if st.button("Regenerate", key=f"regen_{node}"):
                with st.spinner("Regenerating…"):
                    out = run_action_llm(client, model, system_prompt, conv_id,
                                         prompts.REGENERATE_ACTION_PROMPT.format(content=sec["content"]))
                db.update_section_content(sec["id"], out)
                mark_active(node)
                st.rerun()
            if st.button("MCQs", key=f"mcq_{node}"):
                with st.spinner("Writing MCQs…"):
                    out = run_action_llm(client, model, system_prompt, conv_id,
                                         prompts.MCQ_ACTION_PROMPT.format(content=sec["content"]),
                                         max_tokens=max(3072, max_tokens))
                add_note_section(conv_id, f"{sec['heading']} — MCQs", "important", out)
                mark_active(node)
                st.rerun()
            if st.button("Flashcards", key=f"fc_{node}"):
                with st.spinner("Building flashcards…"):
                    out = run_action_llm(client, model, system_prompt, conv_id,
                                         prompts.FLASHCARD_ACTION_PROMPT.format(content=sec["content"]),
                                         max_tokens=max(3072, max_tokens))
                add_note_section(conv_id, f"{sec['heading']} — Flashcards", "important", out)
                mark_active(node)
                st.rerun()
            marks = st.selectbox("Exam answer", ["10", "5", "15", "2"], index=0, key=f"mk_{node}")
            if st.button("Generate exam answer", key=f"exam_{node}"):
                instruction = prompts.EXAM_ANSWER_PROMPT.format(
                    marks=marks, depth=EXAM_DEPTHS[marks], topic=sec["content"]
                )
                with st.spinner(f"Building {marks}-mark answer…"):
                    out = run_action_llm(client, model, system_prompt, conv_id, instruction,
                                         temperature=0.4, max_tokens=max(4096, max_tokens))
                add_note_section(conv_id, f"{sec['heading']} — {marks}m Answer", "important", out)
                mark_active(node)
                st.rerun()

        if sec["message_id"]:
            if row.button("", icon=":material/north_east:", help="Jump to the chat message that created this",
                          key=f"jmsg_{node}"):
                st.session_state["jump_to"] = f"msg-{sec['message_id']}"

        st.markdown(txt.render_md_text(sec["content"]))

        for img in db.get_images(conv_id, sec["id"]):
            try:
                st.image(img["url"], width="content")
            except Exception:
                st.caption("Image unavailable: " + (img["source"] or img["url"]))
            st.caption(
                (f"{img['caption']} — " if img["caption"] else "")
                + f"Source: {img['source'] or 'unknown'} ({img['kind']})"
            )
            if st.button("Remove image", key=f"rmimg_{img['id']}"):
                db.delete_image(img["id"])
                st.rerun()

        for d in db.get_doubts(conv_id, sec["id"]):
            with st.container(border=True, gap="small"):
                st.markdown(f'<div id="dbt-{d["id"]}"></div>', unsafe_allow_html=True)
                st.markdown("**Q:** " + txt.render_md_text(d["question"]))
                st.markdown("**A:** " + txt.render_md_text(d["answer"]))

        if st.session_state.get(f"askopen_{node}", False):
            q = st.text_input(
                f"Ask about “{sec['heading']}”", placeholder="Why is this true? How does it work?",
                label_visibility="collapsed", key=f"askq_{node}",
            )
            c1, c2 = st.columns([1, 1])
            if c2.button("Ask", type="primary", key=f"askgo_{node}"):
                if q:
                    with st.spinner("Answering…"):
                        answer = run_action_llm(client, model, system_prompt, conv_id,
                                                prompts.DOUBT_CONTEXT.format(section=sec["content"], question=q))
                    db.add_doubt(conv_id, sec["id"], node, q, answer)
                    st.session_state[f"askopen_{node}"] = False
                    mark_active(node)
                    st.rerun()
                else:
                    st.caption("Type a question first.")
            if c1.button("Cancel", key=f"askcn_{node}"):
                st.session_state[f"askopen_{node}"] = False

        if st.session_state.get(f"editopen_{node}", False):
            edit = st.text_area("Section text", value=sec["content"], height=160,
                                label_visibility="collapsed", key=f"eds_{node}")
            c1, c2 = st.columns([1, 1])
            if c1.button("Save", type="primary", key=f"edgo_{node}"):
                db.update_section_content(sec["id"], edit)
                st.session_state[f"editopen_{node}"] = False
                mark_active(node)
                st.rerun()
            if c2.button("Cancel", key=f"edcn_{node}"):
                st.session_state[f"editopen_{node}"] = False

        with st.popover("", icon=":material/add_photo_alternate:", help="Attach an image to this section",
                        key=f"img_{node}"):
            mode = st.radio("Source", ["Search web", "Upload", "Generate diagram"],
                            label_visibility="hidden", key=f"imgmode_{node}")
            if mode == "Search web":
                q = st.text_input("Search topic", key=f"imgq_{node}", placeholder="e.g. neural network architecture")
                if st.button("Search images", key=f"imgb_{node}"):
                    st.session_state[f"imgres_{node}"] = images.search_images(q or sec["heading"])
                for r in st.session_state.get(f"imgres_{node}", []):
                    cl, cr = st.columns([1, 4])
                    try:
                        cl.image(r["thumburl"], width="content")
                    except Exception:
                        cl.caption("—")
                    cr.markdown(f"**{r['title'][:48]}**")
                    cr.caption(f"{r['license'] or 'See page'} · {r['artist'] or ''}")
                    if cr.button("Insert", key=f"ins_{r['title'][:24]}_{node}"):
                        db.add_image(conv_id, sec["id"], r["fullurl"], r["thumburl"],
                                     source=("Wikimedia Commons · " + r["page"]),
                                     caption=(r["description"] or r["title"])[:120], kind="web")
                        st.rerun()
            elif mode == "Upload":
                uploaded = st.file_uploader("Upload image", type=["png", "jpg", "jpeg", "webp"], key=f"up_{node}")
                if uploaded and st.button("Attach", key=f"upb_{node}"):
                    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                    suffix = Path(uploaded.name).suffix or ".png"
                    target = UPLOAD_DIR / f"u{int(time.time()*1000)}{suffix}"
                    target.write_bytes(uploaded.getvalue())
                    db.add_image(conv_id, sec["id"], str(target), "", "User upload",
                                 uploaded.name[:100], "uploaded")
                    st.rerun()
            else:
                desc = st.text_input("Diagram description", key=f"dg_{node}",
                                     placeholder="e.g. forward pass, loss, backprop, weight update")
                if st.button("Generate diagram", key=f"dgb_{node}"):
                    with st.spinner("Generating diagram…"):
                        out = run_action_llm(client, model, system_prompt, conv_id,
                                             prompts.DIAGRAM_PROMPT.format(content=sec["content"]))
                    code = extract_mermaid(out)
                    if code:
                        db.add_image(conv_id, sec["id"], images.mermaid_img_url(code), "", "AI-generated (Mermaid)",
                                     (desc or sec["heading"])[:100], "generated")
                        st.rerun()
                    else:
                        st.warning("The model did not return a diagram. Try again.")


def _effective_api_key():
    saved = str(_loaded_settings.get("api_key", "")).strip()
    widget = str(st.session_state.get("set_api_key", saved)).strip()
    return widget or nim.get_api_key()


api_key = _effective_api_key()
if not api_key:
    st.info("The shared NVIDIA API key is not configured yet. Ask the administrator "
            "to set `NVIDIA_API_KEY` in the server's `.env`.")
    st.stop()

client = _client(api_key)

st.session_state.setdefault("current_conv", None)
st.session_state.setdefault("viewing_doc", None)
st.session_state.setdefault("notes_active", None)

def _session_time(ts):
    """Compact timestamp: '13:09' today, 'Mon' yesterday-ish, else '30 Aug'."""
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return ""
    now = datetime.now()
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
    t = _session_time(c["updated_at"])
    if t:
        parts.append(t)
    return " · ".join(parts)


with st.sidebar:
    # ---- FIXED HEADER ----
    with st.container(key="sb_top"):
        st.header("Study Sessions", help=None)
        with st.container(key="sb_newchat"):
            if st.button("＋  New chat", icon=":material/add_circle:", key="new_chat_top",
                         width="stretch", use_container_width=True):
                new_id = db.create_conversation(st.session_state.get("start_subject", "-"))
                st.session_state.current_conv = new_id
                st.session_state.viewing_doc = None
                st.session_state.notes_active = None
                st.rerun()
        with st.container(key="sb_search"):
            search = st.text_input("Search sessions…", placeholder="Search sessions…",
                                   label_visibility="collapsed", key="search_chats")
        with st.container(key="sb_subject"):
            st.selectbox("Subject", SUBJECTS, index=0, key="start_subject",
                         label_visibility="collapsed", help="Subject for new chat (study context).")

    # ---- SCROLLABLE SESSION LIST ----
    with st.container(key="sb_list"):
        conversations = db.list_conversations()
        if search:
            needles = search.lower().split()
            grouped_candidates = [(c, c["title"] + " " + (c["subject"] or "")) for c in conversations]
            conversations = [c for c, hay in grouped_candidates
                             if all(n in hay.lower() for n in needles)]

        if not conversations:
            st.caption(("No sessions found." if search else "No sessions yet. Start a new chat above."))
        else:
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
                    is_active = (st.session_state.current_conv == c["id"])
                    row_container = st.container(
                        key="sb_active" if is_active else f"sb_{c['id']}"
                    )
                    with row_container:
                        open_col, act_col = st.columns([6, 1], gap="small",
                                                       vertical_alignment="center")
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
                        with act_col.popover("", icon=":material/more_vert:",
                                             key=f"more_{c['id']}"):
                            if st.button("Pin" if not c["pinned"] else "Unpin",
                                         key=f"pin_{c['id']}"):
                                db.update_conversation(c["id"], pinned=not c["pinned"])
                                st.rerun()
                            if st.button("Duplicate", key=f"dup_{c['id']}"):
                                db.duplicate_conversation(c["id"])
                                st.rerun()
                            new_title = st.text_input("Rename to", value=c["title"],
                                                      key=f"rn_{c['id']}")
                            if st.button("Save rename", key=f"rns_{c['id']}"):
                                db.update_conversation(c["id"], title=new_title)
                                st.rerun()
                            if st.button("Delete", icon=":material/delete:",
                                         key=f"del_{c['id']}"):
                                if st.session_state.current_conv == c["id"]:
                                    st.session_state.current_conv = None
                                    st.session_state.viewing_doc = None
                                    st.session_state.notes_active = None
                                db.delete_conversation(c["id"])
                                st.rerun()
                        st.markdown(
                            f'<div class="sb-meta">{html.escape(_session_meta(c))}</div>',
                            unsafe_allow_html=True,
                        )

    # ---- FIXED ACCOUNT FOOTER ----
    with st.container(key="sb_bottom"):
        st.divider()
        with st.popover("Settings", icon=":material/tune:", key="settings_pop"):
            _model_ix = nim.NEMOTRON_MODELS.index(model) if model in nim.NEMOTRON_MODELS else 0
            model = st.selectbox("Model", nim.NEMOTRON_MODELS, index=_model_ix, key="set_model")
            thinking = st.checkbox("Enable reasoning (thinking)", value=thinking, key="set_thinking")
            show_reasoning = st.checkbox("Show reasoning while streaming", value=show_reasoning, key="set_show_r")
            verify_answers = st.checkbox("Verify answers (extra check, slower)", value=verify_answers, key="set_verify")
            temperature = st.slider("Temperature", 0.0, 2.0, temperature, 0.05, key="set_temp")
            max_tokens = st.slider("Max tokens", 256, 8192, max_tokens, 256, key="set_tokens")
            system_prompt = st.text_area("System prompt", value=system_prompt,
                                         height=180, key="set_system")
            st.caption("Workspace")
            st.session_state.notes_width = st.slider("Notes panel width (%)", 28, 60, notes_width, 2, key="set_nw",
                                                     help="Keep notes comfortably wide; the chat column adjusts.")
            st.session_state.notes_visible = st.checkbox("Show notes panel", value=notes_visible, key="set_nv")
            st.session_state.panel_h = st.slider("Panel height (px)", 440, 900,
                                                 panel_h, 20, key="set_ph",
                                                 help="Height of the chat and notes scroll areas.")
            st.divider()
            st.caption("API key (optional)")
            _own_key = str(_loaded_settings.get("api_key", "")).strip()
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
            st.markdown(f"**{html.escape(st.session_state.get('user_name', 'User'))}**")
            st.caption(st.session_state.get("user_email", ""))
            st.divider()
            if st.button("Logout", icon=":material/logout:", key="logout_btn"):
                logout()

    db.save_user_settings(_uid, {
        "model": model,
        "thinking": thinking,
        "show_reasoning": show_reasoning,
        "verify": verify_answers,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt,
        "notes_width": st.session_state.get("notes_width", 38),
        "notes_visible": st.session_state.get("notes_visible", True),
        "panel_h": st.session_state.get("panel_h", DEFAULT_PANEL_H),
        "api_key": str(st.session_state.get("set_api_key", "")).strip(),
    })

conv_id = st.session_state.current_conv
nw = st.session_state.notes_width if st.session_state.notes_visible else 0
PANEL_H = int(st.session_state.panel_h)

if nw > 0:
    main_w = max(22, 100 - nw - 10)
    main_c, rail_c, notes_c = st.columns([main_w, 10, nw], gap="small",
                                         vertical_alignment="top", wrap=True)
else:
    main_c = st.container()
    rail_c = None
    notes_c = None


def render_message(m):
    mid = m["id"]
    with st.chat_message(m["role"], avatar=":material/school:" if m["role"] == "assistant" else None):
        st.markdown(f'<div id="msg-{mid}"></div>', unsafe_allow_html=True)
        st.markdown(txt.render_md_text(m["content"]))


with main_c:
    if conv_id is None:
        st.title("AI Study Workspace")
        st.markdown(
            "Your AI tutor + interactive notebook for university exams.\n\n"
            "- Ask an academic question → get a strong theoretical answer.\n"
            "- Structured notes appear live as **knowledge nodes** on the right.\n"
            "- Click a node or highlight a concept to ask a contextual doubt.\n"
            "- Export everything as a professional **PDF**.\n\n"
            "Start by creating a **new chat** in the left panel."
        )
        st.stop()

    conv = db.get_conversation(conv_id)
    messages = db.get_messages(conv_id)

    st.markdown(f"## {conv['title']}")
    st.caption(
        f"{conv['subject'] or 'General'} · {len(messages)} messages"
        + (" · pinned" if conv["pinned"] else "")
    )

    md_for_topics = db.get_or_create_main_document(conv_id)
    topic_secs = db.get_sections(md_for_topics["id"])
    topics = []
    seen_topics = set()
    for s in topic_secs:
        if s["heading"] and s["heading"].lower() not in seen_topics:
            seen_topics.add(s["heading"].lower())
            topics.append((s["heading"], s["node_id"]))

    if topics:
        chosen = st.pills("Jump to topic", [t[0] for t in topics], key="topic_jump",
                          label_visibility="collapsed", selection_mode="single")
        prev = st.session_state.get("prev_topic")
        if chosen is None:
            st.session_state["prev_topic"] = None
        elif chosen != prev:
            target = next((n for h, n in topics if h == chosen), None)
            if target:
                st.session_state["jump_to"] = f"sec-{target}"
                mark_active(target)
            st.session_state["prev_topic"] = chosen

    with st.container(height=PANEL_H):
        if not messages:
            selected = st.pills("Try asking", list(SUGGESTIONS.keys()), label_visibility="collapsed")
            if selected:
                db.add_message(conv_id, "user", SUGGESTIONS[selected])
                messages = db.get_messages(conv_id)

        older = messages[:-UNFOLD_MESSAGES] if len(messages) > UNFOLD_MESSAGES else []
        recent = messages[-UNFOLD_MESSAGES:]

        if older:
            with st.expander(f"Earlier discussion · {len(older)} message{'s' if len(older) != 1 else ''}",
                             expanded=False):
                st.caption("Nothing is deleted — expand to review any past exchanges.")
                for m in older:
                    render_message(m)

        for m in recent:
            render_message(m)

        if messages and messages[-1]["role"] == "user":
            with st.chat_message("assistant", avatar=":material/school:"):
                st.markdown(f'<div id="msg-{messages[-1]["id"] + 1}"></div>', unsafe_allow_html=True)
                full_messages = memory.build_messages(db, conv_id, None, system_prompt=system_prompt)
                answer_text, error = stream_and_answer(
                    client, model, full_messages, thinking, show_reasoning, temperature, max_tokens
                )
                msg_id = None
                if answer_text and verify_answers:
                    with st.spinner("Verifying answer…"):
                        verdict = nim.complete_chat(
                            client, model,
                            [{"role": "system", "content": prompts.VERIFY_PROMPT.format(answer=answer_text)}],
                            temperature=0.0, max_tokens=600,
                        )
                    verdict = (verdict or "").strip()
                    if verdict and verdict != "VERIFIED":
                        if verdict.startswith("CORRECTIONS"):
                            verdict = verdict[len("CORRECTIONS:"):].strip()
                        answer_text = answer_text + "\n\n---\n**Verification:** " + verdict
                if answer_text:
                    msg_id = db.add_message(conv_id, "assistant", answer_text)
                elif error:
                    db.add_message(conv_id, "assistant", f"_(Request failed: {error})_")
                else:
                    db.add_message(conv_id, "assistant", "_(No response returned.)_")
                if conv["title"] == "New Study Session":
                    first = db.get_messages(conv_id, limit=2)
                    user_msg = next((m["content"] for m in first if m["role"] == "user"), "")
                    db.update_conversation(conv_id, title=derive_title(user_msg))
                if answer_text:
                    main_doc = db.get_or_create_main_document(conv_id)
                    notes.upsert_from_response(db, main_doc["id"], answer_text, message_id=msg_id)
                    memory.remember_important_concept(db, conv_id, answer_text)
                    memory.maybe_update_summary(client, model, conv_id, temperature=0.7)

    if conv_id is not None:
        prompt = st.chat_input(
            "Ask about your subject, or continue the last topic…",
            submit_mode="disable",
            key="chat_input_main",
        )
        if prompt:
            db.add_message(conv_id, "user", prompt)
            st.rerun()


if rail_c is not None and conv_id is not None:
    docs_rail = db.list_documents(conv_id)
    if docs_rail:
        v = st.session_state.viewing_doc or docs_rail[-1]["id"]
        if v in [d["id"] for d in docs_rail]:
            active = st.session_state.get("notes_active")
            secs_rail = db.get_sections(v)
            if secs_rail:
                with rail_c:
                    st.markdown(txt.rail_html(secs_rail, active), unsafe_allow_html=True)


with notes_c if notes_c is not None else main_c:
    if conv_id is None:
        st.markdown("\n\n**Live notes** will appear on the right once you start a study session.")
        if notes_c is not None:
            st.session_state["notes_active"] = None
    else:
        docs = db.list_documents(conv_id)
        if not docs:
            if notes_c is not None:
                with notes_c:
                    st.markdown("#### Notes")
                    st.caption("Live notes will appear here as you chat.")
        else:
            doc_ids = [d["id"] for d in docs]
            viewing = st.session_state.viewing_doc
            if viewing not in doc_ids:
                viewing = doc_ids[-1]
                st.session_state.viewing_doc = viewing
            doc = db.get_document(viewing)

            doc_labels = {d["id"]: f"{d['kind'].title()} v{d['version']} — {(d['title'] or '')[:22]}" for d in docs}
            try:
                index = doc_ids.index(viewing)
            except ValueError:
                index = len(doc_ids) - 1

            toolbar = st.container(horizontal=True)
            toolbar.markdown(
                f"**{doc['kind'].title()} v{doc['version']}**",
                help="Document selected in the picker below",
            )
            with toolbar.popover("", icon=":material/search:", help="Search chat, notes and doubts",
                                 key="search_pop"):
                term = st.text_input("Search", key="search_term")
                if term:
                    results = txt.search_snippets(db.search_conversation(conv_id, term), term)
                    any_result = any((results["messages"], results["sections"], results["doubts"]))
                    if not any_result:
                        st.caption("No matches.")
                    if results["messages"]:
                        st.markdown("**Chat**")
                        for r in results["messages"]:
                            who = "You" if r["role"] == "user" else "AI"
                            if st.button(f"💬 {who}: {r['snippet'][:64]}", key=f"sm_{r['id']}"):
                                st.session_state["jump_to"] = f"msg-{r['id']}"
                    if results["sections"]:
                        st.markdown("**Notes**")
                        for r in results["sections"]:
                            if st.button(f"📝 {r['snippet'][:64]}", key=f"ss_{r['id']}"):
                                st.session_state["jump_to"] = f"sec-{r['node_id']}"
                                mark_active(r["node_id"])
                    if results["doubts"]:
                        st.markdown("**Doubts**")
                        for r in results["doubts"]:
                            if st.button(f"❓ {r['snippet'][:64]}", key=f"sd_{r['id']}"):
                                st.session_state["jump_to"] = f"dbt-{r['id']}"
                                mark_active(r["node_id"] or "notes_active")

            with toolbar.popover("", icon=":material/download:", help="Export to PDF",
                                 key="export_pop"):
                scope = st.radio("Scope", ["This document", "Current chat", "Revision notes"],
                                 key="expscope")
                if st.button("Prepare PDF", key="expgen"):
                    data, name = None, None
                    if scope == "Revision notes":
                        for d in db.list_documents(conv_id):
                            if d["kind"] == "revision":
                                data, name = pdf.export_document_pdf(d), f"RevisionNotes_{d['title'][:40]}.pdf"
                                break
                        if data is None:
                            st.warning("No revision notes yet. Generate them first.")
                    elif scope == "Current chat":
                        data, name = pdf.export_chat_pdf(conv_id), f"Chat_{db.get_conversation(conv_id)['title'][:40]}.pdf"
                    else:
                        data, name = pdf.export_document_pdf(doc), f"{doc['title'][:40] or 'Notes'}.pdf"
                    if data:
                        st.session_state["pdf_buf"] = (data, name)
                if "pdf_buf" in st.session_state:
                    data, name = st.session_state["pdf_buf"]
                    st.download_button("Download PDF", data=data, file_name=name,
                                       mime="application/pdf", key="expdl", type="primary")

            if toolbar.button("", icon=":material/summarize:", help="Last-minute revision notes", key="rev"):
                main_doc = db.get_or_create_main_document(conv_id)
                secs = db.get_sections(main_doc["id"])
                notes_text = "\n\n".join(f"## {s['heading']}\n{s['content']}" for s in secs) or "No notes yet."
                with st.spinner("Generating last-minute revision notes…"):
                    out = nim.complete_chat(client, model,
                                            [{"role": "system", "content": system_prompt},
                                             {"role": "user", "content": prompts.REVISION_PROMPT.format(notes=notes_text)}],
                                            temperature=0.4, max_tokens=max(4096, max_tokens))
                new_id = db.create_document(conv_id, "revision", title=(doc["title"] or "Notes") + " — Revision")
                notes.upsert_from_response(db, new_id, out)
                st.session_state.viewing_doc = new_id
                st.rerun()

            if toolbar.button("", icon=":material/library_add:", help="New version of this document", key="nv"):
                base_title = doc["title"] or "Notes"
                new_id = db.create_document(conv_id, "main", title=base_title, base_doc_id=doc["id"], copy_sections=True)
                st.session_state.viewing_doc = new_id
                st.rerun()

            if toolbar.button("", icon=":material/file_copy:", help="Structured notes from this conversation", key="c2n"):
                transcript = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in db.get_messages(conv_id, limit=60))
                if not transcript:
                    st.warning("No conversation yet to convert.")
                else:
                    main_doc = db.get_or_create_main_document(conv_id)
                    with st.spinner("Creating structured notes from this conversation…"):
                        out = nim.complete_chat(client, model,
                                                [{"role": "system", "content": system_prompt},
                                                 {"role": "user", "content": prompts.CHAT_TO_NOTES_PROMPT.format(transcript=transcript)}],
                                                temperature=0.4, max_tokens=max(4096, max_tokens))
                    new_id = db.create_document(conv_id, "main", title=(main_doc["title"] or "Notes") + " (from chat)",
                                                base_doc_id=main_doc["id"], copy_sections=False)
                    notes.upsert_from_response(db, new_id, out)
                    st.session_state.viewing_doc = new_id
                    st.rerun()

            viewing = st.selectbox("Doc", doc_ids, index=index, format_func=lambda i: doc_labels[i],
                                   key=f"viewdoc_{conv_id}", label_visibility="collapsed")
            st.session_state.viewing_doc = viewing
            doc = db.get_document(viewing)

            sections = db.get_sections(viewing)

            with st.container(height=PANEL_H - 110):
                if not sections:
                    st.caption("This document is empty.")
                for sec in sections:
                    render_section(conv_id, viewing, sec, system_prompt, client, model,
                                   temperature, max_tokens)

            emit_rail_observer()
            jump()

# rail rendered above (between chat and notes columns) in DOM order