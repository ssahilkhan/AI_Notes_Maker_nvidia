import io
import re
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

import core.db as db


def _style_sheet():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "NDocTitle", parent=styles["Title"], fontSize=22, spaceAfter=6, alignment=TA_CENTER
        )
    )
    styles.add(ParagraphStyle("NDocSub", parent=styles["Normal"], alignment=TA_CENTER, textColor=colors.grey))
    styles.add(
        ParagraphStyle(
            "NHeading",
            parent=styles["Heading2"],
            fontSize=14,
            spaceBefore=14,
            spaceAfter=6,
            textColor=colors.HexColor("#1f3b1f"),
        )
    )
    styles.add(
        ParagraphStyle(
            "NBody", parent=styles["Normal"], fontSize=10.5, leading=15, spaceAfter=6, alignment=TA_LEFT
        )
    )
    styles.add(
        ParagraphStyle(
            "NFormula",
            parent=styles["Normal"],
            fontSize=11.5,
            leading=16,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=8,
            fontName="Courier-Bold",
            textColor=colors.HexColor("#224422"),
        )
    )
    styles.add(
        ParagraphStyle(
            "NCaption",
            parent=styles["Normal"],
            fontSize=8.5,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=10,
        )
    )
    return styles


def _markdown_to_flow(md_text, styles):
    flow = []
    for raw in md_text.split("\n\n"):
        block = raw.strip()
        if not block:
            continue
        if block.startswith("$"):
            block = block.strip("$").strip()
            flow.append(Paragraph(escape(block), styles["NFormula"]))
            continue
        block = escape(block)
        for bullet_re in (r"^\s*[-*]\s+", r"^\s*\d+\.\s+", r"^\s*\+"):
            if re.search(bullet_re, block, flags=re.M):
                block = re.sub(r"(?:^|\n)\s*\d+\.\s+", "\n• ", block)
                block = re.sub(r"(?:^|\n)\s*[-*+]\s+", "\n• ", block)
                break
        flow.append(Paragraph(block.replace("\n", "<br/>"), styles["NBody"]))
    return flow


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _add_page_numbers(canvas, _doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def export_document_pdf(doc, include_doubts=True) -> bytes:
    styles = _style_sheet()
    buf = io.BytesIO()
    doc_builder = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=doc["title"] or "Exam Notes",
    )

    story = []
    title = doc["title"] or "Exam Notes"
    story.append(Paragraph(escape(title), styles["NDocTitle"]))
    conv = db.get_conversation(doc["conversation_id"])
    sub = (conv["subject"] if conv and conv["subject"] not in ("", "-") else "") or ""
    story.append(Paragraph(escape(sub) + (" &mdash; " if sub else "") + str(datetime.now().strftime("%d %b %Y")), styles["NDocSub"]))
    story.append(Spacer(1, 8 * mm))

    sections = db.get_sections(doc["id"])
    if not sections:
        story.append(Paragraph("No notes yet.", styles["NBody"]))

    for sec in sections:
        heading = sec["heading"] or "Notes"
        story.append(Paragraph(escape(heading), styles["NHeading"]))
        story.extend(_markdown_to_flow(sec["content"], styles))

        for image in db.get_images(doc["conversation_id"], sec["id"]):
            try:
                img_bytes = download_bytes(image["url"])
                img_bytes.seek(0)
                img = RLImage(img_bytes, width=110 * mm, height=90 * mm)
                img.hAlign = "CENTER"
                story.append(Spacer(1, 4))
                story.append(img)
                caption = image["caption"] or image["source"] or ""
                if caption:
                    story.append(Paragraph(escape(f"{caption} (source: {image['source']})"), styles["NCaption"]))
                else:
                    story.append(Paragraph(escape(f"Source: {image['source'] or image['url']}"), styles["NCaption"]))
            except Exception:
                story.append(Paragraph(f"[Image unavailable: {escape(image['source'] or image['url'])}]", styles["NCaption"]))

        doubts = db.get_doubts(doc["conversation_id"], sec["id"]) if include_doubts else []
        for d in doubts:
            story.append(
                Paragraph(f"<b>Doubts &rarr;</b> <i>{escape(d['question'])}</i>", styles["NBody"])
            )
            story.extend(_markdown_to_flow(d["answer"], styles))

    all_doubts = db.get_doubts(doc["conversation_id"], None) if include_doubts else []
    if all_doubts and not sections:
        story.append(PageBreak())
        story.append(Paragraph("Doubts &amp; Clarifications", styles["NHeading"]))
        for d in all_doubts:
            story.append(Paragraph(f"<b>{escape(d['question'])}</b>", styles["NBody"]))
            story.extend(_markdown_to_flow(d["answer"], styles))

    doc_builder.build(story, onFirstPage=_add_page_numbers, onLaterPages=_add_page_numbers)
    return buf.getvalue()


def export_chat_pdf(conv_id) -> bytes:
    styles = _style_sheet()
    buf = io.BytesIO()
    conv = db.get_conversation(conv_id)
    title = (conv["title"] if conv else "Chat") + " — Conversation"
    doc_builder = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=title,
    )
    story = [Paragraph(escape(title), styles["NDocTitle"]), Spacer(1, 6 * mm)]
    for m in db.get_messages(conv_id):
        who = "User" if m["role"] == "user" else "Tutor"
        story.append(Paragraph(f"<b>{who}:</b>", styles["NBody"]))
        story.extend(_markdown_to_flow(m["content"], styles))
    doc_builder.build(story, onFirstPage=_add_page_numbers, onLaterPages=_add_page_numbers)
    return buf.getvalue()


def download_bytes(url):
    import os

    if os.path.exists(url):
        with open(url, "rb") as f:
            return io.BytesIO(f.read())

    import core.images as images

    idx = url.rfind("/")
    ext = ".img"
    if idx != -1 and "." in url[idx:]:
        ext = url[idx:]
    ext = ext.split("\n")[0][:12] or ".img"
    return io.BytesIO(images.fetch_image_bytes(url))