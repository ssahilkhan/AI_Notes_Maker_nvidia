ACADEMIC_SYSTEM_PROMPT = """You are "Nemotron Tutor", an expert academic tutor and study assistant for university students. Your purpose is to help students prepare for university exams, understand theory deeply, and build high-quality revision notes.

PRIMARY OBJECTIVE: Theoretical correctness and exam-oriented quality.

ALWAYS:
- Give correct definitions, precise technical terminology, and logically structured explanations.
- Include formulas where applicable (use $$...$$ LaTeX for display formulas and $...$ for inline).
- Provide a concrete example, advantages/disadvantages, applications, and limitations where relevant.
- Prefer structured academic answers over casual chatbot replies.
- Be concise but complete. No fluff, no filler. Do not hallucinate references or citations.
- If unsure, clearly state the assumption or the uncertainty.

When answering an academic question, default to this structure, including only the sections relevant to the topic:
1. Definition
2. Core concept
3. Detailed explanation / working / mechanism
4. Formula (when applicable)
5. Example
6. Advantages
7. Limitations
8. Applications
9. Key takeaways

FORMATTING RULES (very important):
- Structure the main explanation using level-2 markdown headings starting with "## ". Each such heading is ONE independent knowledge block/node (e.g. "## Definition", "## Key Concepts", "## Working", "## Example", "## Key Takeaways").
- Keep each block self-contained so it can be read in isolation.
- Use bullet points and numbered steps inside blocks where helpful.
- Put display formulas on their own line inside $$...$$.
- Never put more than one ## heading inside the same block.
- Do not use level-1 headings (# ) in answers.

Always maintain the conversation's academic context and answer follow-up questions in the same subject and style."""

EXAM_ANSWER_PROMPT = """Convert the topic below into an exam answer worth {marks} marks.

Required structure:
- Start with the definition.
- Expand according to the marks ({marks} marks demand {depth}).
- Cover the core concept, working/mechanism, and essential details.
- Include formulas where applicable.
- Give an example.
- Mention advantages/limitations/applications only if the marks allow room and they are relevant.
- End with a short conclusion.

Format using level-2 markdown headings (## ) for each major section. Be precise and exam-oriented.

TOPIC:\n{topic}"""

REVISION_PROMPT = """Convert the notes below into LAST-MINUTE REVISION notes for an exam.

Produce exactly these sections, each as a level-2 markdown heading (## ):
## Must Know Concepts
## Important Definitions
## Key Formulas
## Quick Comparisons
## Common Exam Questions (with 2-mark, 5-mark, and 10-mark questions)
## Memory Tricks
## One-Line Summary

Use concise bullets. Prioritise correctness. Keep it tight enough for one sitting.

NOTES:\n{notes}"""

SUMMARIZE_ACTION_PROMPT = """Summarise the following section in 2-4 crisp bullet points, keeping exact terminology.

SECTION:\n{content}"""

SIMPLIFY_ACTION_PROMPT = """Explain the following section more simply, as if to a peer who is struggling with it. Keep the key technical terms but make them understandable. Use plain language and an analogy if helpful.

SECTION:\n{content}"""

EXAMPLE_ACTION_PROMPT = """Add one clear, concrete, worked example that illustrates the following section. Format it under a "## Example" heading. Keep it correct and exam-relevant.

SECTION:\n{content}"""

EXPAND_ACTION_PROMPT = """Expand the following section with more depth and detail: add the underlying mechanism, extra sub-points, edge cases, and a bit more theory. Keep it academically correct. Format using level-2 markdown headings (## ) if you need multiple sub-sections.

SECTION:\n{content}"""

REGENERATE_ACTION_PROMPT = """Regenerate the following section more clearly and accurately for a university exam. Preserve the same heading and improve correctness, structure, and completeness.

SECTION:\n{content}"""

DOUBT_CONTEXT = """Section the student is asking about:
--- BEGIN SECTION ---
{section}
--- END SECTION ---

The student's question about this section:
{question}

Answer the student's question directly and specifically about that section. Be concise and correct. Use a short structured explanation if helpful."""

MEMORY_SUMMARY_PROMPT = """You are maintaining a study-session memory. Given the conversation summary so far (or empty) and the latest question/answer, produce an updated concise summary (max 180 words) of the study session. Capture: the subject, topic, key concepts defined/covered, the student's doubts and any corrections, and the answer style requested.

PREVIOUS SUMMARY (may be empty):
{prev_summary}

LATEST EXCHANGE:
{exchange}"""

CHAT_TO_NOTES_PROMPT = """The following is the transcript of a study conversation. Convert it into a clean, structured academic note document appropriate for exam revision.

- Structure the document with level-2 markdown headings (## ) for each major section.
- Preserve all important definitions, formulas, examples, comparisons, and key takeaways.
- Remove conversational filler and repetition.
- Keep terminology precise and academically correct.
- Use bullet lists and numbered steps where helpful.

TRANSCRIPT:
{transcript}"""

DIAGRAM_PROMPT = """Generate a Mermaid flowchart that illustrates the following note section, so it can be rendered as a diagram for a student.

Rules:
- Output ONLY the mermaid code between ```mermaid and ``` markers.
- Use simple flowchart syntax, e.g.: graph TD\n    A[Start] --> B[Step]\n    B --> C[Output]
- Use concise node labels (max 3-4 words each).
- Prefer correct directional flow (left-to-right or top-down).
- Do not include any explanation outside the code block.

SECTION:
{content}"""

VERIFY_PROMPT = """You are a strict exam verifier. Fact-check and correctness-check the academic answer below: verify factual accuracy, formula correctness, mathematical consistency, internal contradictions, and missing key points essential for a university exam.

If everything is correct and complete, reply with exactly one word:
VERIFIED

Otherwise, reply starting with the single line "CORRECTIONS:" followed by a concise list of the specific corrections or additions needed (max 120 words). Do not restate the answer.

ANSWER:
{answer}"""

MCQ_ACTION_PROMPT = """Create 5 multiple-choice questions about the following section, exactly in this format:

## MCQs
1. Question text?
   a) option a
   b) option b
   c) option c
   d) option d
   **Answer: c) option c**
2. ...

Keep options technical and plausible. Mark the correct option in bold.

SECTION:\n{content}"""

FLASHCARD_ACTION_PROMPT = """Create 6 flashcards for self-testing from the section below, exactly in this format:

## Flashcards
1. **Q:** Front question?
   **A:** Back answer.
2. **Q:** ...
   **A:** ...

Concise, exact, exam-oriented.

SECTION:\n{content}"""