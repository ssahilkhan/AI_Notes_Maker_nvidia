import json

import core.db as db
import core.prompts as prompts
from core import nim

RECENT_MESSAGE_LIMIT = 12
SUMMARY_UPDATE_EVERY = 5


def build_messages(db, conv_id, user_question, *, system_prompt=None, extra_context=None):
    messages = []
    system = system_prompt or prompts.ACADEMIC_SYSTEM_PROMPT
    memory_block = build_memory_block(db, conv_id)
    if memory_block:
        system = system + "\n\nSTUDY SESSION MEMORY (context only, do not repeat it unless asked):\n" + memory_block
    if extra_context:
        system = system + "\n\nACTIVE GRAPH CONTEXT (the student selected a knowledge node — use this to focus your answer):\n" + extra_context
    messages.append({"role": "system", "content": system})

    recent = db.get_messages(conv_id, limit=RECENT_MESSAGE_LIMIT * 2)
    for m in recent[-RECENT_MESSAGE_LIMIT:]:
        messages.append({"role": m["role"], "content": m["content"]})

    if user_question:
        messages.append({"role": "user", "content": user_question})
    return messages


def build_memory_block(db, conv_id):
    parts = []
    conv = db.get_conversation(conv_id)
    if conv and conv["subject"] and conv["subject"] != "-":
        parts.append(f"Subject: {conv['subject']}")
    doc = db.get_or_create_main_document(conv_id)
    sections = db.get_sections(doc["id"])
    if sections:
        headings = " | ".join(s["heading"] for s in sections[:12])
        parts.append(f"Topics covered in notes: {headings}")
    summary = db.get_memory(conv_id, "summary")
    if summary:
        parts.append(f"Session summary: {summary}")
    concepts = db.get_memory(conv_id, "important_concepts")
    if concepts:
        parts.append(f"Important concepts: {concepts}")
    return "\n".join(parts) if parts else ""


def maybe_update_summary(client, model, conv_id, temperature=0.7, max_tokens=2048):
    count = len(db.get_messages(conv_id, limit=10000))
    if count % SUMMARY_UPDATE_EVERY != 0 or count < SUMMARY_UPDATE_EVERY:
        return
    recent = db.get_messages(conv_id, limit=SUMMARY_UPDATE_EVERY + 1)
    exchange = "\n".join(f"{m['role'].upper()}: {m['content'][:800]}" for m in recent)
    prev = db.get_memory(conv_id, "summary")
    prompt = prompts.MEMORY_SUMMARY_PROMPT.format(prev_summary=prev, exchange=exchange)
    try:
        full = nim.complete_chat(
            client,
            model,
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        db.set_memory(conv_id, "summary", full)
    except Exception:
        pass


def remember_important_concept(db, conv_id, text):
    concepts = db.get_memory(conv_id, "important_concepts")
    concept = (text or "").strip()[:120]
    if not concept:
        return
    if concepts:
        if concept not in concepts:
            combined = (concepts + " | " + concept)[:1500]
            db.set_memory(conv_id, "important_concepts", combined)
    else:
        db.set_memory(conv_id, "important_concepts", concept)


def store_json_memory(conv_id, payload):
    db.set_memory(conv_id, "study_context", json.dumps(payload, ensure_ascii=False))