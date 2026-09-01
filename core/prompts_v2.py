"""V2 prompt templates and parsing helpers for rich learning responses.

The system prompt (core/prompts.py) now asks every answer to end with a
"### Related Concepts" tail. These helpers parse that tail into knowledge-
node names and strip it from text that feeds the notes document (so the
concepts list never lands inside a note section).
"""

import re

CONCEPT_EXTRACT_PROMPT = """From the study answer below, extract the 3-7 most important core concepts a student should build knowledge cards from.

Rules:
- One concept per line, plain text. No numbering, bullets, or markdown.
- Use the exact technical name (e.g. "Backpropagation", "Activation Function", "Convolutional Layer").
- Do not add descriptions or explanations.

ANSWER:
{answer}"""

RELATED_CONCEPTS_HEADING = re.compile(r"^###\s*related\s*concepts\s*$", re.IGNORECASE)


def parse_concepts(text):
    """Extract up to 7 concept names from the '### Related Concepts' tail.

    Returns [] when the tail is missing or empty.
    """
    if not text:
        return []
    m = re.search(r"###\s*Related Concepts\b(.*?)(?=\n##\s|\n###\s|\Z)", text, re.S | re.IGNORECASE)
    if not m:
        return []
    items = []
    for line in m.group(1).splitlines():
        line = line.strip().lstrip("-*•").strip()
        line = re.sub(r"[`*_\[\]#]", "", line).strip()
        if line and line not in items:
            items.append(line)
    return items[:7]


def strip_concepts_tail(text):
    """Remove the trailing '### Related Concepts' list from notes content.

    Only strips when the concepts section is the last section in the text
    (no further level-2 heading between it and the end).
    """
    if not text:
        return text or ""
    idx = re.search(r"###\s*Related Concepts\b", text, re.IGNORECASE)
    if not idx:
        return text
    start = idx.start()
    tail = text[start:]
    if re.search(r"\n##\s", tail):
        return text  # not the tail; more sections follow — keep everything
    return text[:start].rstrip()