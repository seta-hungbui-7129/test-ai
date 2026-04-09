# AI LMS — MCQ Generator

Upload a training document, pick a Claude model, and generate 5 fresh Multiple Choice Questions per click. Questions are validated by Pydantic before display, and previously generated questions are automatically excluded from future runs to prevent repetition.

---

## Features

- **Multi-format upload** — `.txt`, `.pdf`, `.docx`
- **User-provided API key** — entered directly in the sidebar, no `.env` file needed
- **Model selector** — Haiku (fast/cheap), Sonnet (balanced), Opus (best quality)
- **Deduplication** — each new generation excludes all previously generated questions
- **Schema validation** — Pydantic ensures every MCQ has exactly 4 options, answer matches one option, and explanations are present
- **Robust parsing** — 3 JSON extraction strategies with 3 retry attempts per generation

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Streamlit)                     │
│  file_uploader → selectbox → text_input → button → markdown()   │
└──────────────────────────────┬──────────────────────────────────┘
                               │  Python function calls
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVICES LAYER                               │
│                                                                  │
│  ┌────────────────────────┐    ┌────────────────────────────────┐│
│  │   document_loader.py  │    │       mcq_generator.py         ││
│  │  extract_text()       │    │  build_user_prompt()           ││
│  │   ├─ _extract_txt()    │    │  generate_mcqs()              ││
│  │   ├─ _extract_pdf()    │    │   └─ _call_api()               ││
│  │   └─ _extract_docx()   │    │      └─ _extract_json_block()  ││
│  │                        │    │      └─ _extract_json_anywhere()││
│  │  load_document()       │    │                                ││
│  │  (Streamlit wrapper)   │    │  SYSTEM_PROMPT = Claude schema  ││
│  └────────────────────────┘    └────────────────────────────────┘│
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                          models.py                            ││
│  │  MCQ (BaseModel)      — validates 1 question                 ││
│  │  MCQList (BaseModel)  — validates exactly 5 questions        ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────┬──────────────────────────────────┘
                               │  HTTPS (Anthropic SDK)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL API                                 │
│                Anthropic Claude Messages API                      │
│             User-selectable: Haiku / Sonnet / Opus                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
ai-lms/
├── app.py                  Streamlit UI entry point
├── requirements.txt         Python dependencies
├── README.md                This file
├── SPEC.md                  Technical specification
├── .gitignore               Excludes .env, __pycache__, venv
│
└── services/
    ├── __init__.py          Package marker
    ├── models.py            Pydantic schemas (MCQ, MCQList)
    ├── document_loader.py   File → raw text extractor
    └── mcq_generator.py     Claude API caller + prompt builder
```

---

## Data Flow (Step by Step)

### 1. User enters API key + uploads file

The sidebar accepts an API key (stored in `st.session_state.api_key`) and a file upload. On receiving a file:

```
UploadedFile.getvalue()  →  extract_text(bytes, filename)  →  raw string
```

`extract_text()` dispatches by file extension:
- `.txt`  →  decode with UTF-8 / latin-1 / cp1252 fallback
- `.pdf`  →  PyPDF2 `PdfReader`, extract text per page
- `.docx` →  python-docx `Document`, collect non-empty paragraphs

Stats (word count, char count) are computed and stored in session state.

### 2. User clicks "Generate 5 MCQs"

`app.py` calls `generate_mcqs()` with the stored text, API key, selected model, and all previously generated questions:

```python
mcqs = generate_mcqs(
    source_text       = st.session_state.document_text,
    api_key           = st.session_state.api_key,
    model             = st.session_state.model,
    exclude_questions = st.session_state.mcqs,   # deduplication
)
```

### 3. Prompt is built

`build_user_prompt()` wraps the training material in a user message. If `exclude_questions` is provided (not empty on subsequent clicks), previously generated questions are appended as a "DO NOT REPEAT" block.

The system prompt instructs Claude to return ONLY a JSON object matching this schema:

```json
{
  "questions": [
    {
      "question": "<text>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "answer": "<exact text of the correct option — must match one of options>",
      "explanation": "<1-2 sentences>"
    }
  ]
}
```

Rules enforced in the prompt:
- Exactly 5 questions, each with exactly 4 distinct options
- Questions must cover **different topics** — no repeats even in rephrasing
- Answer must be phrased **identically** in both `answer` and one `options` entry
- Never output anything except the JSON object

### 4. API call with temperature

```python
client.messages.create(
    model      = model,           # e.g. "claude-haiku-4-5"
    max_tokens = 2048,
    temperature = 0.8,            # 0 = deterministic, 1 = max randomness
    system     = SYSTEM_PROMPT,
    messages   = [{"role": "user", "content": build_user_prompt(...)}],
)
```

`temperature=0.8` balances variety with quality. Lower (0.3–0.5) gives more consistent output; higher (0.9–1.0) gives more creative but potentially worse questions.

### 5. JSON parsing with 3 strategies + 3 retries

Claude may return the JSON wrapped in markdown fences (` ```json ... ``` `) or with extra text. Three extraction strategies are tried in order:

```
Strategy 1: raw response           → json.loads()
Strategy 2: strip_fences()         → json.loads()   (removes ```json / ```)
Strategy 3: scan_anywhere()        → find first balanced { or [ → json.loads()
```

If all three fail, the attempt increments (up to 3 total). On the 3rd failure, a `ValueError` is raised and shown in the UI.

### 6. Pydantic validation

`MCQList.model_validate(data)` enforces:
- `questions` is a list of exactly 5 items
- Each `MCQ` has `question` (≥5 chars), `options` (exactly 4), `answer` (must match one option), `explanation` (≥10 chars)

If validation fails, the parsing loop retries with a fresh API call.

### 7. Rendered in Streamlit

`app.py` receives `List[MCQ]` and renders each as an HTML card:
- Question in red bold
- Options A/B/C/D
- Correct answer highlighted green
- Explanation in italic gray

---

## Session State

| Key | Type | Purpose |
|-----|------|---------|
| `api_key` | `str` | Anthropic API key entered in sidebar |
| `model` | `str` | Selected Claude model slug |
| `document_text` | `str` | Extracted text from uploaded file |
| `word_count` | `int` | Word count of document |
| `char_count` | `int` | Character count of document |
| `uploaded` | `bool` | Whether a file has been loaded |
| `mcqs` | `list[MCQ]` | Currently displayed questions |

`mcqs` is also passed as `exclude_questions` on every generation call — this prevents the model from repeating questions across clicks.

---

## Models Available

| Model | Description | Use Case |
|-------|-------------|----------|
| `claude-haiku-4-5` | Fastest, cheapest | Default — fine for MCQ generation |
| `claude-3-5-haiku-latest` | Stable older haiku | Budget, consistent output |
| `claude-sonnet-4-20250514` | Balanced quality/cost | Better reasoning for complex material |
| `claude-opus-4-20250514` | Best quality | Long or technical documents |

Changing the model clears any existing MCQs (since output may differ).

---

## Styling

Custom CSS is injected via `st.markdown(unsafe_allow_html=True)`. Cards use CSS custom properties for theming:

```css
:root {
    --mcq-bg: rgba(128, 128, 128, 0.05);
    --mcq-border: rgba(128, 128, 128, 0.2);
    --mcq-question-color: #ff4b4b;
    --mcq-correct: #2e7d32;
    --mcq-explanation: rgba(128, 128, 128, 0.7);
}
```

Theme-aware (works in both light and dark Streamlit themes).

---

## Setup

```bash
# 1. Clone the repository
git clone git@github.com:seta-hungbui-7129/test-ai.git
cd test-ai

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run — the API key is entered directly in the app's sidebar
streamlit run app.py
```

No `.env` file is required. Get your API key at [console.anthropic.com](https://console.anthropic.com).

---

## Key Design Decisions

### Separation of concerns
`services/` contains zero Streamlit imports. `mcq_generator.py` and `document_loader.py` can be unit-tested or reused in a different frontend (FastAPI, CLI, etc.) without modification.

### Pydantic as a guard rail
LLM output is untrusted. Pydantic validation catches:
- Wrong number of questions
- Answer not matching any option
- Missing or too-short fields

Combined with retry logic, this makes the pipeline resilient to model non-determinism.

### Deduplication via prompt injection
Instead of post-processing, previously generated questions are fed back into the prompt as a "DO NOT REPEAT" block. This is more reliable than string-matching because it leverages the model's own understanding of question similarity.

---

## Extending

| Goal | How |
|------|-----|
| Add more file types | Add a new extractor in `document_loader.py`, update `extract_text()` dispatch |
| Change number of questions | Pass `num=N` to `generate_mcqs()` (also update `MCQList` min/max) |
| Lower variety | Reduce `temperature` in `_call_api()` |
| Save MCQs to DB | Add `save_mcqs(mcqs)` in `services/mcq_storage.py` |
| Export to CSV/QuizML | Add `export_mcqs(mcqs, format)` in `services/export.py` |
| Add user accounts | Integrate Streamlit auth or wrap with FastAPI + auth middleware |
