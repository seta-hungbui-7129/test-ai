"""
MCQ Generator — calls Anthropic Claude API and returns validated MCQ objects.
"""

import json
import re
import textwrap
import traceback
from typing import List, Optional

from anthropic import Anthropic

from .models import MCQ, MCQList


def _log(*args, **kwargs):
    print("[MCQ Generator]", *args, **kwargs)


SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert educational assessment writer. Your task is to generate
    high-quality Multiple Choice Questions (MCQs) from the provided training
    material.

    Output format — you MUST return ONLY a valid JSON object with no
    preamble, explanation, or markdown code fences. The JSON must be parseable
    with json.loads().

    Schema:
    {{
      "questions": [
        {{
          "question": "<clear question text>",
          "options": ["<Option A>", "<Option B>", "<Option C>", "<Option D>"],
          "answer": "<exact text of the correct option>",
          "explanation": "<1-2 sentence explanation of why this answer is correct>"
        }}
      ]
    }}

    Rules:
    - Generate exactly {num} questions.
    - Each question must have exactly 4 distinct options (A, B, C, D).
    - CRITICAL: Questions must cover DIFFERENT topics from the material.
      Pick a unique concept, fact, or section for each question.
      Do NOT ask about the same topic twice — even rephrased.
    - Answers must be phrased identically in both the "answer" field and one
      of the four "options" — no synonyms, no trailing spaces.
    - Difficulty should be moderate: test comprehension, not trivia memorization.
    - If the source material is too short to generate {num} unique questions,
      explain the limitation in a "limitation" field instead of questions.
    - Never output anything except the JSON object.
""").strip()


def build_user_prompt(
    source_text: str,
    num: int = 5,
    exclude_questions: Optional[List[MCQ]] = None,
) -> str:
    content = textwrap.dedent(f"""
        Generate {num} Multiple Choice Questions from the following training
        material. Follow the output rules precisely.

        --- BEGIN MATERIAL ---
        {source_text}
        --- END MATERIAL ---
    """).strip()

    if exclude_questions:
        prev = "\n".join(
            f"- Q: {q.question} | Ans: {q.answer}" for q in exclude_questions
        )
        content += textwrap.dedent(f"""

        --- DO NOT REPEAT ---
        The following questions have already been generated. You MUST generate
        completely NEW questions that are DIFFERENT in topic and wording from all
        of these. Do not ask about the same concept even in a different phrasing.

        {prev}
        """).strip()

    return content


def generate_mcqs(
    source_text: str,
    num: int = 5,
    model: str = "claude-haiku-4-5",
    max_tokens: int = 2048,
    api_key: Optional[str] = None,
    exclude_questions: Optional[List[MCQ]] = None,
) -> List[MCQ]:
    if not api_key:
        raise ValueError(
            "No API key provided. Please enter your Anthropic API key in the sidebar."
        )

    _log("API key loaded:", api_key[:20] + "...")

    client = Anthropic(api_key=api_key)
    _log("Anthropic client created, model =", model)

    # Context window safety: Truncate document if it's too large
    # 200k tokens is roughly 800k chars. We cap at 600k to be safe.
    CHAR_LIMIT = 600_000
    if len(source_text) > CHAR_LIMIT:
        _log(f"Document too large ({len(source_text)} chars). Truncating to {CHAR_LIMIT}.")
        source_text = source_text[:CHAR_LIMIT] + "\n\n[DOCUMENT TRUNCATED DUE TO SIZE LIMITS]"

    for attempt in range(3):
        _log(f"--- Attempt {attempt + 1}/3 ---")
        try:
            raw = _call_api(client, source_text, num, model, max_tokens, exclude_questions)
            _log(f"API response received, length = {len(raw)} chars")
            _log(f"API raw (first 300): {raw[:300]}")
        except Exception as exc:
            _log("API call FAILED:", exc)
            traceback.print_exc()
            raise

        for strategy_name, candidate in [
            ("raw",               raw),
            ("strip_fences",      _extract_json_block(raw)),
            ("scan_anywhere",     _extract_json_anywhere(raw)),
        ]:
            if not candidate:
                _log(f"  [{strategy_name}] → empty, skipping")
                continue
            _log(f"  [{strategy_name}] → trying ({len(candidate)} chars)")
            try:
                data = json.loads(candidate)
                mcq_list = MCQList.model_validate(data)
                _log(f"  [{strategy_name}] → SUCCESS, {len(mcq_list.questions)} questions")
                return mcq_list.questions
            except Exception as exc:
                _log(f"  [{strategy_name}] → FAILED:", exc)

        if attempt == 2:
            raise ValueError(
                f"Failed to parse MCQ response after 3 attempts.\n"
                f"Raw output (first 600 chars): {raw[:600]}"
            )


def _call_api(
    client: Anthropic,
    source_text: str,
    num: int,
    model: str,
    max_tokens: int,
    exclude_questions: Optional[List[MCQ]] = None,
) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0.8,
        system=SYSTEM_PROMPT.format(num=num),
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(source_text, num, exclude_questions),
            }
        ],
    )
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    raise ValueError(f"No TextBlock found in response. Blocks: {response.content}")


def _extract_json_block(text: str) -> str:
    text = text.strip()
    for opener in ("```json", "```JSON", "```"):
        if text.startswith(opener):
            text = text[len(opener):]
            break
    if text.strip().endswith("```"):
        text = text.strip()[:-3]
    return text.strip()


def _extract_json_anywhere(text: str) -> str:
    text = text.strip()

    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)

    for i, ch in enumerate(text):
        if ch == "{":
            try:
                result = text[i:]
                json.loads(result)
                return result
            except json.JSONDecodeError:
                continue
        if ch == "[":
            try:
                result = text[i:]
                json.loads(result)
                return result
            except json.JSONDecodeError:
                continue

    return ""
