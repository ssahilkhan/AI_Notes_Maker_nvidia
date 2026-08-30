import re
import uuid


def detect_kind(heading, content=""):
    h = heading.lower()
    c = content.lower()
    if "definition" in h or "define" in h:
        return "definition"
    if "formula" in h or "equation" in h or "mathematical" in h:
        return "formula"
    if "example" in h or "illustration" in h:
        return "example"
    if "advantage" in h or "benefit" in h:
        return "advantage"
    if "limitation" in h or "disadvantage" in h or "drawback" in h or "restriction" in h:
        return "limitation"
    if "application" in h or "use case" in h or "use-cases" in h:
        return "application"
    if ("takeaway" in h or "important" in h or "key point" in h or "must know" in h
            or "memory trick" in h or "conclusion" in h or "summary" in h):
        return "important"
    if re.search(r"\$\$", content):
        return "formula"
    return "text"


def parse_response(text):
    sections = []
    lines = text.splitlines()
    current_heading = ""
    current_lines = []
    seen_h2 = False

    def flush():
        buf = "\n".join(current_lines).strip()
        if not buf:
            return
        sections.append({"heading": current_heading, "content": buf, "kind": detect_kind(current_heading, buf)})

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("## "):
            flush()
            current_heading = line[3:].strip()
            current_lines = []
            seen_h2 = True
        elif line.startswith("# "):
            continue
        else:
            current_lines.append(line)
    flush()

    if not seen_h2:
        joined = text.strip()
        if joined:
            sections.append({"heading": "Notes", "content": joined, "kind": detect_kind("", joined)})
    return sections


def upsert_from_response(db, doc_id, text, message_id=None):
    sections = parse_response(text)
    existing = db.get_sections(doc_id)
    by_heading = {}
    for s in existing:
        by_heading.setdefault(s["heading"].strip().lower(), s)

    for i, sec in enumerate(sections):
        key = (sec["heading"] or "Notes").strip().lower()
        match = by_heading.get(key)
        if match:
            node_id = match["node_id"]
            position = match["position"]
        else:
            position = len(existing) + 1
            node_id = f"n{str(uuid.uuid4())[:12]}"
            existing.append(None)
        db.upsert_section(doc_id, node_id, position, sec["heading"] or "Notes", sec["kind"], sec["content"], message_id=message_id)
    return sections


def new_node_id():
    return f"n{str(uuid.uuid4())[:12]}"