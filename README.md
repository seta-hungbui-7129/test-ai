# AI LMS — MCQ Generator

A minimal Learning Management System that uses AI to generate Multiple Choice Questions from uploaded training documents.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Streamlit)                     │
│   st.file_uploader  →  st.button("Generate")  →  st.markdown()  │
└──────────────────────────┬────────────────────────────────────────┘
                           │  Python function calls
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      SERVICES LAYER                               │
│                                                                  │
│  ┌─────────────────────┐     ┌────────────────────────────────┐  │
│  │  document_loader.py  │     │        mcq_generator.py        │  │
│  │  ───────────────────│     │  ────────────────────────────── │  │
│  │  extract_text()      │     │  build_prompt()                │  │
│  │  ├─ _extract_txt()   │     │  generate_mcqs()               │  │
│  │  ├─ _extract_pdf()   │     │  └─ _call_api()                 │  │
│  │  └─ _extract_docx()  │     │     └─ _extract_json_block()    │  │
│  │                      │     │                                │  │
│  │  load_document()     │     │  SYSTEM PROMPT = Claude        │  │
│  │  (Streamlit wrapper) │     │  instructions + JSON schema     │  │
│  └──────────────────────┘     └────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                        models.py                             │  │
│  │  MCQ (Pydantic BaseModel)  — validates each question        │  │
│  │  MCQList                   — validates 5-question batch     │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬────────────────────────────────────────┘
                           │  HTTPS (Anthropic SDK)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    EXTERNAL API                                  │
│                   Anthropic Claude API                          │
│                   User-selectable (Haiku / Sonnet / Opus)       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
User uploads file (.txt | .pdf | .docx)
    │
    ▼
document_loader.load_document()  ── extracts raw text
    │
    ▼
mcq_generator.generate_mcqs(text, num=5)
    │
    ├── build_prompt()       ── injects training material into user message
    │                         + system prompt defines JSON schema
    │
    ├── client.messages.create()   ── HTTPS POST → Anthropic API
    │
    ├── response.content[0].text  ── raw JSON string from LLM
    │
    ├── _extract_json_block()     ── strips markdown fences if present
    │
    ├── json.loads()              ── parse JSON
    │
    └── MCQList.model_validate() ── Pydantic validation (throws if schema
    │                                doesn't match, answer not in options, etc.)
    │
    ▼
List[MCQ]  →  Streamlit renders 5 cards
```

---

## Project Structure

```
ai-lms/
├── .env.example          ← Copy to .env and add your API key
├── requirements.txt       ← pip install -r requirements.txt
├── app.py                 ← Streamlit entry point (UI)
├── SPEC.md                ← This spec
│
└── services/
    ├── __init__.py
    ├── models.py          ← Pydantic schemas (MCQ, MCQList)
    ├── document_loader.py ← file → raw text extractor
    └── mcq_generator.py   ← AI API caller + prompt builder
```

---

## Setup

```bash
# 1. Clone / navigate into the project
cd ai-lms

# 2. Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your Anthropic API key
cp .env.example .env
# Open .env and replace the placeholder with your key:
# ANTHROPIC_API_KEY=sk-ant-...

# 5. Run
streamlit run app.py
```

---

## Key Design Decisions (for your presentation)

### 1. Separation of Concerns
The app is split into `services/` and `app.py`. The `services/` folder contains **pure Python logic** with **no Streamlit imports** — this means:

- `mcq_generator.py` can be tested with `pytest` without running the UI
- `document_loader.py` works in any Python project (Flask, FastAPI, CLI)
- The UI layer (`app.py`) only orchestrates

### 2. Pydantic Validation
We use Pydantic `BaseModel` to validate the AI's JSON output. If Claude returns malformed JSON (wrong schema, answer not in options, wrong number of questions), the code catches it and retries — up to 3 times.

This is a **crucial AI engineering pattern**: never trust the model's output without schema validation.

### 3. System Prompt Engineering
The system prompt explicitly tells Claude to:
- Return **only JSON** (no markdown fences, no explanation)
- Use a **specific schema** (`{questions: [{question, options, answer, explanation}]}`)
- Rules about answer matching (answer must be identical to one option)

### 4. Session State
Streamlit's `session_state` holds:
- `document_text` — so we don't re-upload on every generate click
- `mcqs` — so generated questions persist after reruns

Each "Generate" click **replaces** (not appends) the questions — as required.

---

## API Contract

```python
# External API: Anthropic Claude Messages API
# Documented at: https://docs.anthropic.com/

client.messages.create(
    model="<user-selected model>",
    max_tokens=2048,
    system="<system prompt>",
    messages=[{"role": "user", "content": "<user prompt>"}]
)

# Response: message.content[0].text → raw JSON string
# Parsed by: MCQList.model_validate(json.loads(raw))
```

---

## Extending the System

| Extension | How |
|-----------|-----|
| Add more file types | Extend `extract_text()` in `document_loader.py` |
| Use a different LLM | Change model name + update system prompt in `mcq_generator.py` |
| Save MCQs to a database | Add `save_mcqs(mcqs)` in `services/mcq_storage.py` |
| Add user accounts | Wrap routes with auth middleware (FastAPI or Streamlit auth) |
| Export to Quiz format | Add `to_quizml()` or `to_csv()` in `services/export.py` |