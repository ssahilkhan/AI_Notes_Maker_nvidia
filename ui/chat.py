"""Main chat column: conversation header, topic pills, message history,
auto-answering and the chat input. Also hosts the shared LLM helpers used by
the notes panel (stream_and_answer / run_action_llm / extract_mermaid)."""

import re

import streamlit as st

import core.db as db
import core.images as images
import core.memory as memory
import core.nim as nim
import core.notes as notes
import core.prompts as prompts
import core.prompts_v2 as prompts_v2
import core.text as txt
from ui.context import mark_active

UNFOLD_MESSAGES = 6   # keep this many most-recent messages fully unfolded


def derive_title(text):
    line = (text or "").strip().splitlines()[0]
    line = re.sub(r"[#*`_\]\[()>]", "", line)
    return (line[:60] or "New Study Session").strip()


def stream_and_answer(ctx, messages):
    status = st.status("Thinking…", expanded=ctx.show_reasoning) if ctx.thinking else None
    holder = st.empty()
    answer_text = ""
    error = None
    answered = False
    try:
        stream = nim.stream_chat(
            ctx.client,
            ctx.model,
            messages,
            temperature=ctx.temperature,
            max_tokens=ctx.max_tokens,
            thinking=ctx.thinking,
        )
        for kind, value in nim.iter_stream(stream):
            if kind == "reasoning":
                if status and ctx.show_reasoning:
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


def run_action_llm(ctx, conv_id, instruction, temperature=0.4, max_tokens=2048):
    system = ctx.system_prompt
    mem_block = memory.build_memory_block(db, conv_id)
    if mem_block:
        system = system + "\n\nSTUDY SESSION MEMORY (context only):\n" + mem_block
    messages = [{"role": "system", "content": system}]
    for m in db.get_messages(conv_id, limit=12):
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": instruction})
    return nim.complete_chat(ctx.client, ctx.model, messages,
                             temperature=temperature, max_tokens=max_tokens)


def extract_mermaid(text):
    m = re.search(r"```mermaid\s*(.*?)\s*```", text, re.S)
    return m.group(1).strip() if m else (text or "").strip()


_SPECIAL_HEADING = re.compile(r"^###\s*(Related Concepts|Exam Tip|Key Insight)\s*$", re.IGNORECASE)
_SPECIAL_KIND = {
    "related concepts": "concepts",
    "exam tip": "exam",
    "key insight": "insight",
}


def split_rich_blocks(text):
    """Break an AI answer into renderable blocks: markdown, mermaid, and the
    special educational sections (Exam Tip / Key Insight / Related Concepts)."""
    blocks = []
    buf = []
    lines = text.splitlines()
    i = 0

    def flush():
        out = "\n".join(buf).strip()
        buf.clear()
        if out:
            blocks.append(("md", out))

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```mermaid"):
            flush()
            code = []
            i += 1
            while i < len(lines) and lines[i].strip() != "```":
                code.append(lines[i])
                i += 1
            i += 1
            blocks.append(("mermaid", "\n".join(code).strip()))
            continue
        m = _SPECIAL_HEADING.match(line.strip())
        if m:
            flush()
            kind = _SPECIAL_KIND.get(m.group(1).lower(), "md")
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("##") \
                    and not lines[i].strip().startswith("###"):
                body.append(lines[i])
                i += 1
            blocks.append((kind, "\n".join(body).strip()))
            continue
        buf.append(line)
        i += 1
    flush()
    return blocks


def render_concept_chips(concepts, conv_id=None, message_id=None):
    """Clickable [+ Concept] chips below an answer.
    A click creates a knowledge card (Phase 3) at an auto-placed grid position."""
    shown = [c for c in concepts][:8]
    if not shown:
        return
    cols = st.columns(min(len(shown), 4), gap="small")
    col_idx = 0
    for name in shown:
        with cols[col_idx % len(cols)]:
            if st.button(f"+ {name}", key=f"nc_{name.replace(' ', '_')}", type="tertiary",
                         help="Create a knowledge card for this concept"):
                _create_node_from_chip(conv_id, name, message_id)
        col_idx += 1


def _create_node_from_chip(conv_id, name, message_id):
    if not conv_id:
        return
    x, y = db.next_node_position(conv_id)
    db.create_knowledge_node(
        conv_id,
        name,
        summary="Concept extracted from the study session.",
        message_id=message_id,
        x=x,
        y=y,
    )
    st.session_state.setdefault("pending_nodes", [])
    if name not in st.session_state["pending_nodes"]:
        st.session_state["pending_nodes"].append(name)
    st.toast(f"Added “{name}” to the knowledge map.")
    st.rerun()


def render_rich(content, conv_id=None, message_id=None):
    for kind, block in split_rich_blocks(content):
        if kind == "mermaid":
            if block:
                try:
                    st.image(images.mermaid_img_url(block), width="content")
                    continue
                except Exception:
                    pass
            st.markdown(txt.render_md_text("```mermaid\n" + block + "\n```"))
        elif kind == "exam":
            st.markdown("> 🎯 **Exam Tip**\n" + "\n".join("> " + l for l in block.splitlines()))
        elif kind == "insight":
            st.markdown("> 💡 **Key Insight:** " + block)
        elif kind == "concepts":
            render_concept_chips(
                prompts_v2.parse_concepts("### Related Concepts\n" + block),
                conv_id=conv_id,
                message_id=message_id,
            )
        else:
            st.markdown(txt.render_md_text(block))


def render_message(m, conv_id=None):
    mid = m["id"]
    with st.chat_message(m["role"], avatar=":material/school:" if m["role"] == "assistant" else None):
        st.markdown(f'<div id="msg-{mid}"></div>', unsafe_allow_html=True)
        render_rich(m["content"], conv_id=conv_id, message_id=mid)


def render_chat_main(ctx, conv_id):
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

    with st.container(height=ctx.panel_h):
        if not messages:
            selected = st.pills("Try asking", list(ctx.suggestions.keys()),
                                label_visibility="collapsed")
            if selected:
                db.add_message(conv_id, "user", ctx.suggestions[selected])
                messages = db.get_messages(conv_id)

        older = messages[:-UNFOLD_MESSAGES] if len(messages) > UNFOLD_MESSAGES else []
        recent = messages[-UNFOLD_MESSAGES:]

        if older:
            with st.expander(f"Earlier discussion · {len(older)} message{'s' if len(older) != 1 else ''}",
                             expanded=False):
                st.caption("Nothing is deleted — expand to review any past exchanges.")
                for m in older:
                    render_message(m, conv_id)

        for m in recent:
            render_message(m, conv_id)

        if messages and messages[-1]["role"] == "user":
            with st.chat_message("assistant", avatar=":material/school:"):
                st.markdown(f'<div id="msg-{messages[-1]["id"] + 1}"></div>', unsafe_allow_html=True)
                full_messages = memory.build_messages(db, conv_id, None, system_prompt=ctx.system_prompt)
                answer_text, error = stream_and_answer(ctx, full_messages)
                msg_id = None
                if answer_text and ctx.verify_answers:
                    with st.spinner("Verifying answer…"):
                        verdict = nim.complete_chat(
                            ctx.client, ctx.model,
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
                    st.error(f"The AI request failed: {error}")
                    if st.button("Retry", icon=":material/refresh:", key=f"retry_{conv_id}",
                                 type="primary"):
                        st.rerun()
                else:
                    db.add_message(conv_id, "assistant", "_(No response returned.)_")
                if conv["title"] == "New Study Session":
                    first = db.get_messages(conv_id, limit=2)
                    user_msg = next((m["content"] for m in first if m["role"] == "user"), "")
                    db.update_conversation(conv_id, title=derive_title(user_msg))
                if answer_text:
                    main_doc = db.get_or_create_main_document(conv_id)
                    notes.upsert_from_response(
                        db, main_doc["id"],
                        prompts_v2.strip_concepts_tail(answer_text),
                        message_id=msg_id,
                    )
                    memory.remember_important_concept(db, conv_id, answer_text)
                    memory.maybe_update_summary(ctx.client, ctx.model, conv_id, temperature=0.7)

    if conv_id is not None:
        prompt = st.chat_input(
            "Ask about your subject, or continue the last topic…",
            submit_mode="disable",
            key="chat_input_main",
        )
        if prompt:
            db.add_message(conv_id, "user", prompt)
            st.rerun()