"""Notes panel: document toolbar (search / export / actions), the section
renderer (badges, doubts, images, edit/ask flows, LLM actions) and the node
rail between the chat and notes columns."""

import html
import time
from pathlib import Path

import streamlit as st

import core.db as db
import core.images as images
import core.nim as nim
import core.pdf as pdf
import core.prompts as prompts
import core.notes as notes
import core.text as txt
from ui import chat, layout
from ui.context import ctx, mark_active


def add_note_section(conv_id, heading, kind, content):
    main_doc = db.get_or_create_main_document(conv_id)
    node_id = notes.new_node_id()
    db.upsert_section(
        main_doc["id"], node_id, len(db.get_sections(main_doc["id"])) + 1, heading, kind, content
    )
    st.session_state.viewing_doc = main_doc["id"]
    return node_id


EXAM_DEPTHS = {
    "2": "2-3 lines, only the definition and the single most important point",
    "5": "5-6 sentences: definition, concept, working, one example",
    "10": "8-12 sentences: definition, concept, working, formula, example, advantages, limitations",
    "15": "a full answer: definition, concept, working, formula, derivation, example, advantages, limitations, applications, conclusion",
}


def render_section(conv_id, doc_id, sec):
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
        if row.button("", icon=":material/track_changes:", help="Create a knowledge card from this section",
                      key=f"kc_{node}"):
            x, y = db.next_node_position(conv_id)
            db.create_knowledge_node(
                conv_id,
                sec["heading"] or "Knowledge card",
                summary=sec["content"][:280],
                content=sec["content"],
                section_id=sec["id"],
                message_id=sec["message_id"],
                x=x,
                y=y,
            )
            st.toast(f"Added “{sec['heading'] or 'Knowledge card'}” to the knowledge map.")
            mark_active(node)
            st.rerun()
        with row.popover("", icon=":material/more_vert:", help="More actions", key=f"mor_{node}"):
            if st.button("Explain simpler", key=f"simp_{node}"):
                with st.spinner("Simplifying…"):
                    out = chat.run_action_llm(ctx, conv_id,
                                              prompts.SIMPLIFY_ACTION_PROMPT.format(content=sec["content"]))
                new_content = sec["content"] + "\n\n**In simpler terms:**\n" + out
                db.update_section_content(sec["id"], new_content)
                mark_active(node)
                st.rerun()
            if st.button("Give example", key=f"ex_{node}"):
                with st.spinner("Adding example…"):
                    out = chat.run_action_llm(ctx, conv_id,
                                              prompts.EXAMPLE_ACTION_PROMPT.format(content=sec["content"]))
                db.update_section_content(sec["id"], sec["content"] + "\n\n" + out)
                mark_active(node)
                st.rerun()
            if st.button("Expand", key=f"exp_{node}"):
                with st.spinner("Expanding…"):
                    out = chat.run_action_llm(ctx, conv_id,
                                              prompts.EXPAND_ACTION_PROMPT.format(content=sec["content"]))
                db.update_section_content(sec["id"], sec["content"] + "\n\n**Extended detail:**\n" + out)
                mark_active(node)
                st.rerun()
            if st.button("Summarise", key=f"sum_{node}"):
                with st.spinner("Summarising…"):
                    out = chat.run_action_llm(ctx, conv_id,
                                              prompts.SUMMARIZE_ACTION_PROMPT.format(content=sec["content"]))
                db.update_section_content(sec["id"], sec["content"] + "\n\n**Summary:**\n" + out)
                mark_active(node)
                st.rerun()
            if st.button("Regenerate", key=f"regen_{node}"):
                with st.spinner("Regenerating…"):
                    out = chat.run_action_llm(ctx, conv_id,
                                              prompts.REGENERATE_ACTION_PROMPT.format(content=sec["content"]))
                db.update_section_content(sec["id"], out)
                mark_active(node)
                st.rerun()
            if st.button("MCQs", key=f"mcq_{node}"):
                with st.spinner("Writing MCQs…"):
                    out = chat.run_action_llm(ctx, conv_id,
                                              prompts.MCQ_ACTION_PROMPT.format(content=sec["content"]),
                                              max_tokens=max(3072, ctx.max_tokens))
                add_note_section(conv_id, f"{sec['heading']} — MCQs", "important", out)
                mark_active(node)
                st.rerun()
            if st.button("Flashcards", key=f"fc_{node}"):
                with st.spinner("Building flashcards…"):
                    out = chat.run_action_llm(ctx, conv_id,
                                              prompts.FLASHCARD_ACTION_PROMPT.format(content=sec["content"]),
                                              max_tokens=max(3072, ctx.max_tokens))
                add_note_section(conv_id, f"{sec['heading']} — Flashcards", "important", out)
                mark_active(node)
                st.rerun()
            marks = st.selectbox("Exam answer", ["10", "5", "15", "2"], index=0, key=f"mk_{node}")
            if st.button("Generate exam answer", key=f"exam_{node}"):
                instruction = prompts.EXAM_ANSWER_PROMPT.format(
                    marks=marks, depth=EXAM_DEPTHS[marks], topic=sec["content"]
                )
                with st.spinner(f"Building {marks}-mark answer…"):
                    out = chat.run_action_llm(ctx, conv_id, instruction,
                                              temperature=0.4, max_tokens=max(4096, ctx.max_tokens))
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
                        answer = chat.run_action_llm(ctx, conv_id,
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
                    ctx.upload_dir.mkdir(parents=True, exist_ok=True)
                    suffix = Path(uploaded.name).suffix or ".png"
                    target = ctx.upload_dir / f"u{int(time.time()*1000)}{suffix}"
                    target.write_bytes(uploaded.getvalue())
                    db.add_image(conv_id, sec["id"], str(target), "", "User upload",
                                 uploaded.name[:100], "uploaded")
                    st.rerun()
            else:
                desc = st.text_input("Diagram description", key=f"dg_{node}",
                                     placeholder="e.g. forward pass, loss, backprop, weight update")
                if st.button("Generate diagram", key=f"dgb_{node}"):
                    with st.spinner("Generating diagram…"):
                        out = chat.run_action_llm(ctx, conv_id,
                                                  prompts.DIAGRAM_PROMPT.format(content=sec["content"]))
                    code = chat.extract_mermaid(out)
                    if code:
                        db.add_image(conv_id, sec["id"], images.mermaid_img_url(code), "", "AI-generated (Mermaid)",
                                     (desc or sec["heading"])[:100], "generated")
                        st.rerun()
                    else:
                        st.warning("The model did not return a diagram. Try again.")


def render_rail(rail_c, conv_id):
    """Node rail column between chat and notes (or None when hidden)."""
    if rail_c is None or conv_id is None:
        return
    docs_rail = db.list_documents(conv_id)
    if not docs_rail:
        return
    v = st.session_state.viewing_doc or docs_rail[-1]["id"]
    if v in [d["id"] for d in docs_rail]:
        active = st.session_state.get("notes_active")
        secs_rail = db.get_sections(v)
        if secs_rail:
            with rail_c:
                st.markdown(txt.rail_html(secs_rail, active), unsafe_allow_html=True)


def _search_popover(conv_id):
    with st.popover("", icon=":material/search:", help="Search chat, notes and doubts",
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


def _export_popover(conv_id, doc):
    with st.popover("", icon=":material/download:", help="Export to PDF",
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


def render_notes_panel(conv_id, notes_c, main_c):
    column = notes_c if notes_c is not None else main_c
    with column:
        if conv_id is None:
            st.markdown("\n\n**Live notes** will appear on the right once you start a study session.")
            if notes_c is not None:
                st.session_state["notes_active"] = None
            return

        docs = db.list_documents(conv_id)
        if not docs:
            if notes_c is not None:
                st.markdown("#### Notes")
                st.caption("Live notes will appear here as you chat.")
            return

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
        _search_popover(conv_id)
        _export_popover(conv_id, doc)

        if toolbar.button("", icon=":material/summarize:", help="Last-minute revision notes", key="rev"):
            main_doc = db.get_or_create_main_document(conv_id)
            secs = db.get_sections(main_doc["id"])
            notes_text = "\n\n".join(f"## {s['heading']}\n{s['content']}" for s in secs) or "No notes yet."
            with st.spinner("Generating last-minute revision notes…"):
                out = nim.complete_chat(ctx.client, ctx.model,
                                        [{"role": "system", "content": ctx.system_prompt},
                                         {"role": "user", "content": prompts.REVISION_PROMPT.format(notes=notes_text)}],
                                        temperature=0.4, max_tokens=max(4096, ctx.max_tokens))
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
                    out = nim.complete_chat(ctx.client, ctx.model,
                                            [{"role": "system", "content": ctx.system_prompt},
                                             {"role": "user", "content": prompts.CHAT_TO_NOTES_PROMPT.format(transcript=transcript)}],
                                            temperature=0.4, max_tokens=max(4096, ctx.max_tokens))
                new_id = db.create_document(conv_id, "main", title=(main_doc["title"] or "Notes") + " (from chat)",
                                            base_doc_id=main_doc["id"], copy_sections=False)
                notes.upsert_from_response(db, new_id, out)
                st.session_state.viewing_doc = new_id
                st.rerun()

        kn = db.get_conversation_nodes(conv_id)
        if kn:
            st.caption(
                f"🗺 **{len(kn)}** knowledge card{'s' if len(kn) != 1 else ''} — "
                "the interactive map arrives in the next update."
            )

        viewing = st.selectbox("Doc", doc_ids, index=index, format_func=lambda i: doc_labels[i],
                               key=f"viewdoc_{conv_id}", label_visibility="collapsed")
        st.session_state.viewing_doc = viewing
        doc = db.get_document(viewing)

        sections = db.get_sections(viewing)

        with st.container(height=ctx.panel_h - 110):
            if not sections:
                st.caption("This document is empty.")
            for sec in sections:
                render_section(conv_id, viewing, sec)

        layout.emit_rail_observer()
        layout.jump()