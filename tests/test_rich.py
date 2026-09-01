"""Unit tests for Phase 2 rich-learning-response helpers (pure functions)."""

import core.notes as notes
import core.prompts_v2 as pv2
import ui.chat as chat


class TestConceptParsing:
    def test_parse_concepts_extracts_bulleted_names(self):
        text = (
            "## Definition\nSome text.\n\n"
            "### Related Concepts\n"
            "- Input Layer\n"
            "- Backpropagation\n"
            "- Activation Functions\n"
        )
        assert pv2.parse_concepts(text) == ["Input Layer", "Backpropagation", "Activation Functions"]

    def test_parse_concepts_reads_plain_lines(self):
        text = "### Related Concepts\nSoftmax\nCross-Entropy Loss\nGradient Descent"
        assert pv2.parse_concepts(text) == ["Softmax", "Cross-Entropy Loss", "Gradient Descent"]

    def test_parse_concepts_returns_empty_when_missing(self):
        assert pv2.parse_concepts("Just a normal answer.") == []
        assert pv2.parse_concepts("") == []

    def test_parse_concepts_strips_markdown_and_limits(self):
        text = "### Related Concepts\n" + "\n".join(f"- **Concept {i}**" for i in range(10))
        out = pv2.parse_concepts(text)
        assert len(out) == 7
        assert all("**" not in c for c in out)

    def test_strip_concepts_tail_removes_final_section(self):
        text = "## Definition\nBody.\n\n### Related Concepts\n- A\n- B\n"
        assert pv2.strip_concepts_tail(text) == "## Definition\nBody."

    def test_strip_concepts_tail_keeps_text_when_body_follows(self):
        text = "## A\nBody.\n### Related Concepts\n- A\n\n## More\nExtra."
        out = pv2.strip_concepts_tail(text)
        assert "More" in out
        assert out.endswith("Extra.")


class TestKindDetection:
    def test_new_kinds_detected(self):
        assert notes.detect_kind("## Architecture of transformer", "") == "flowchart"
        assert notes.detect_kind("## Comparison: CNN vs RNN", "") == "comparison"
        assert notes.detect_kind("## Step-by-step forward pass", "") == "step"
        assert notes.detect_kind("summary Table", "| a | b |\n|---|---|\n| 1 | 2 |") == "table"

    def test_old_kinds_unaffected(self):
        assert notes.detect_kind("## Definition", "") == "definition"
        assert notes.detect_kind("## Exam Tip", "### Related Concepts") == "text"


class TestRichBlocks:
    def test_split_rich_blocks_recognises_mermaid_and_tail(self):
        text = (
            "## Working\nSteps here.\n\n"
            "```mermaid\nflowchart TD\n    A --> B\n```\n\n"
            "### Related Concepts\n- A\n- B"
        )
        kinds = [k for k, _ in chat.split_rich_blocks(text)]
        assert kinds == ["md", "mermaid", "concepts"]

    def test_split_rich_blocks_recognises_exam_and_insight(self):
        text = "## Definition\nx\n\n### Exam Tip\nExpect a 5-marker.\n\n### Key Insight\nIt clicks."
        kinds = [k for k, _ in chat.split_rich_blocks(text)]
        assert kinds == ["md", "exam", "insight"]
        # exam/inisight bodies captured
        by = dict(sorted((k, b) for k, b in chat.split_rich_blocks(text)))
        assert "Expect a 5-marker." in by["exam"]
        assert by["insight"] == "It clicks."

    def test_split_rich_blocks_keeps_plain_content(self):
        blocks = chat.split_rich_blocks("Just some markdown **text**.")
        assert blocks == [("md", "Just some markdown **text**.")]