# AI LMS — MCQ Generator: Technical Specification

## 1. Concept & Vision

A minimal AI-powered Learning Management System that lets users upload training documents and generate 5 fresh Multiple Choice Questions per click. Questions are validated by Pydantic, served by Anthropic Claude, and displayed in styled cards. Previously generated questions are excluded from future generations to prevent repetition.

---

## 2. UI Layout

```
┌────────────────────────────────────────────────────────┐
│  [Sidebar]                                            │
│   ┌────────────────────────────────────────────────┐  │
│   │ 🔑 API Key                                     │  │
│   │ [________________________]  password input    │  │
│   │ ─────────────────────────────────────────────  │  │
│   │ 🤖 Model                                      │  │
│   │ [Haiku 4.5 (fast & cheap) ▼]  selectbox      │  │
│   │ ─────────────────────────────────────────────  │  │
│   │ 📄 Upload Training Material                   │  │
│   │ [Choose a file .txt .pdf .docx]               │  │
│   │                                                │  │
│   │ (after upload)                                │  │
│   │ 📊 Document Stats                             │  │
│   │ Words: 1,234   Chars: 6,789                  │  │
│   │ [🔍 Text preview (first 300 chars) ▼]        │  │
│   └────────────────────────────────────────────────┘  │
│                                                        │
│  [Main Area]                                           │
│   🧠 AI MCQ Generator                                  │
│   Upload a training document → click Generate → ...     │
│   ─────────────────────────────────────────────────   │
│   [✨ Generate 5 MCQs]  [ℹ️ Enter API key first]      │
│                                                        │
│   📝 5 Questions Generated                             │
│   ┌──────────────────────────────────────────────┐    │
│   │ Q1. What is...?                              │    │
│   │ A. Option  B. Option  C. Option  D. Option  │    │
│   │ ✅ B. Correct answer                          │    │
│   │ 💡 Explanation: ...                          │    │
│   └──────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────┘
```

---

## 3. Features & Interactions

### API Key Input
- Password text input at top of sidebar
- Persists in `session_state` across reruns
- Key is passed directly to `generate_mcqs()` — not read from `.env`

### Model Selector
- Streamlit `selectbox` with 4 options: Haiku 4.5, Haiku 3.5, Sonnet 4, Opus 4
- Default: `claude-haiku-4-5`
- Changing the model clears existing MCQs (resets `session_state.mcqs = []`)

### File Upload
- Accepts `.txt`, `.pdf`, `.docx`
- On upload: extracts text, computes stats, stores in session state
- Error displayed inline if extraction fails
- Changing the file clears previous MCQs

### Generate Button
- Disabled until both API key and document are present
- On click: calls `generate_mcqs()`, stores result in `session_state.mcqs`
- Replaces previous questions (no append)
- Shows spinner during API call

### MCQ Display
- Rendered as HTML cards with custom CSS
- Each card: question, 4 options (A/B/C/D), correct answer highlighted green, explanation
- Options are compared by string equality — answer must match one option exactly

### Error Handling
- `ValueError` from `generate_mcqs` shown as red error + traceback
- All other exceptions shown as "Unexpected error" + traceback

---

## 4. Components

| Component | States |
|-----------|--------|
| API key input | empty, filled |
| Model selectbox | any of 4 options selected |
| File uploader | empty, file selected, processing, error |
| Generate button | disabled (no key/doc), disabled (no doc), enabled, clicked (spinner) |
| MCQ card | rendered for each of the 5 questions |

---

## 5. Technical Approach

### Framework
Streamlit (Python) for the UI

### AI
Anthropic Claude Messages API via the official `anthropic` SDK.
User-selectable model (Haiku, Sonnet, Opus).

### Parsing
Pydantic v2 `BaseModel` schemas for MCQ validation.

### Documents
- `.txt` → built-in bytes decode (UTF-8 / latin-1 / cp1252)
- `.pdf` → `PyPDF2` `PdfReader`
- `.docx` → `python-docx` `Document`

### Key Parameters
| Parameter | Value | Reason |
|-----------|-------|--------|
| `temperature` | `0.8` | Balances variety and quality |
| `max_tokens` | `2048` | Enough for 5 MCQs (~300–500 tokens total) |
| Retry attempts | `3` | Ensures resilience against JSON parse failures |
| JSON strategies | `3` | raw, strip fences, scan anywhere |

---

## 6. Data Models

```python
# services/models.py

class MCQ(BaseModel):
    question: str           # ≥5 chars
    options: List[str]      # exactly 4
    answer: str             # must match one of options exactly
    explanation: str        # ≥10 chars

class MCQList(BaseModel):
    questions: List[MCQ]    # exactly 5
```

Validation failure on any field raises `ValueError`, which triggers a retry (up to 3 attempts per generation).

---

## 7. API Contract

```python
# Anthropic Claude Messages API
client.messages.create(
    model      = "<user-selected model>",
    max_tokens = 2048,
    temperature = 0.8,
    system     = SYSTEM_PROMPT,
    messages   = [{"role": "user", "content": build_user_prompt(...)}],
)

# Response: message.content[n].text → raw JSON string
# Parsed by: MCQList.model_validate(json.loads(raw))
```

---

## 8. Prompt Design

### System Prompt
Defines the JSON schema and rules for question generation. Instructs Claude to return ONLY a JSON object — no markdown fences, no explanation text.

### User Prompt
Injects the training material. On subsequent clicks, appends previously generated questions as a "DO NOT REPEAT" block to prevent duplication across generations.

---

## 9. Session State Schema

```python
{
    "api_key":         str,       # Anthropic API key
    "model":           str,       # Selected model slug
    "document_text":   str,       # Extracted file text
    "word_count":      int,       # Word count
    "char_count":      int,       # Character count
    "uploaded":        bool,      # File has been loaded
    "mcqs":            list[MCQ], # Currently displayed questions
}
```

`session_state.mcqs` is passed as `exclude_questions` on every generation call to prevent repetition.

---

## 10. Error Codes

| Condition | Behaviour |
|-----------|-----------|
| No API key | Button disabled, info message shown |
| No document | Button disabled, info message shown |
| Extraction fails | Inline error toast with exception message |
| API returns non-JSON | Retry up to 3× with 3 parsing strategies |
| Pydantic validation fails | Retry up to 3× with fresh API call |
| All retries exhausted | `ValueError` displayed with raw response excerpt |
| HTTP/network error | Propagated and displayed with full traceback |
