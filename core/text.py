import html
import re

_FENCE_RE = re.compile(r"```.*?```", re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_PLACEHOLDER = "\x00TEXTCORE{idx}\x00"


def _protect_code(text):
    blocks = []

    def keep(m):
        blocks.append(m.group(0))
        return _PLACEHOLDER.format(idx=len(blocks) - 1)

    text = _FENCE_RE.sub(keep, text)
    text = _INLINE_CODE_RE.sub(keep, text)
    return text, blocks


def _restore_code(text, blocks):
    for i, block in enumerate(blocks):
        text = text.replace(_PLACEHOLDER.format(idx=i), block)
    return text


def preprocess_math(text):
    """Make model output render correctly as Markdown + KaTeX.

    - Code fences/inline code are protected (never treated as math).
    - \\( ... \\)  ->  $ ... $        (inline math)
    - \\[ ... \\]  ->  $$ ... $$      (display math)
    - Unbalanced stray delimiters are left untouched so the AI's
      mathematical meaning is preserved exactly.
    """
    if not text:
        return text
    text, blocks = _protect_code(text)

    text = re.sub(
        r"\\\[\s*(.*?)\s*\\\]",
        lambda m: "$$\n" + m.group(1).strip() + "\n$$",
        text,
        flags=re.S,
    )
    text = re.sub(
        r"\\\(\s*(.*?)\s*\\\)",
        lambda m: "$" + m.group(1).strip() + "$",
        text,
        flags=re.S,
    )
    return _restore_code(text, blocks)


def render_md_text(text):
    """Markdown string with math normalised, ready for st.markdown."""
    return preprocess_math(text or "")


# Friendly one-letter node badges per section kind (keep stable / small).
KIND_BADGE = {
    "definition": "D",
    "formula": "F",
    "example": "E",
    "advantage": "A",
    "limitation": "L",
    "application": "AP",
    "important": "K",
    "text": "T",
}

KIND_LABEL = {
    "definition": "Definition",
    "formula": "Formula",
    "example": "Example",
    "advantage": "Advantage",
    "limitation": "Limitation",
    "application": "Application",
    "important": "Key concept",
    "text": "Note",
}

KIND_COLOR = {
    "definition": "blue",
    "formula": "purple",
    "example": "green",
    "advantage": "teal",
    "limitation": "orange",
    "application": "cyan",
    "important": "amber",
    "text": "gray",
}


def _snippet(text, term, width=70):
    text = " ".join((text or "").split())
    idx = text.lower().find(term.lower())
    if idx < 0:
        return text[:width]
    start = max(0, idx - 20)
    end = min(len(text), idx + width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def rail_html(sections, active=None):
    """Build the vertical node-rail navigation (pure HTML/CSS, no JS required)."""
    items = []
    for s in sections:
        badge = KIND_BADGE.get(s["kind"], "T")
        rc = KIND_COLOR.get(s["kind"], "gray")
        title = html.escape(s["heading"] or "")
        cls = " active" if active and s["node_id"] == active else ""
        items.append(
            f'<a class="rail-node{cls}" href="#sec-{s["node_id"]}" '
            f'data-target="sec-{s["node_id"]}" title="{title}">'
            f'<span class="rn rc-{rc}">{badge}</span></a>'
        )
    return f'<div class="rail-wrap"><div class="node-rail">{"".join(items)}</div></div>'


def search_snippets(results, term):
    """Add a rendered snippet to each search result row (rows are converted to dicts)."""
    results["messages"] = [dict(r) for r in results["messages"]]
    results["sections"] = [dict(r) for r in results["sections"]]
    results["doubts"] = [dict(r) for r in results["doubts"]]
    for r in results["messages"]:
        r["snippet"] = _snippet(r["content"], term)
    for r in results["sections"]:
        r["snippet"] = _snippet(r["heading"], term) + " — " + _snippet(r["content"], term, 56)
    for r in results["doubts"]:
        r["snippet"] = "Q: " + _snippet(r["question"], term, 30) + " | " + _snippet(r["answer"], term, 40)
    return results