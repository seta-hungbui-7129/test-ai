# AI LMS - MCQ Generator

## 1. Concept & Vision

A minimal Learning Management System backend that lets candidates upload training material documents and generate 5 fresh Multiple Choice Questions per click. The focus is on clean AI integration, not UI polish — the architecture should show how Python bridges document ingestion, LLM prompting, and structured output parsing.

## 2. Design Language

- **Aesthetic**: Developer-first, no design framework. Streamlit native.
- **Colors**: Streamlit defaults.
- **Typography**: Streamlit defaults.
- **No custom CSS needed.**

## 3. Layout

```
┌─────────────────────────────────────────────────┐
│  st.title("AI MCQ Generator")                    │
│                                                   │
│  [Upload: PDF/TXT/DOCX]  ──▶  sidebar            │
│  [Generate Button]        ──▶  main area         │
│  [5 MCQ Cards]            ──▶  main area         │
└─────────────────────────────────────────────────┘
```

## 4. Features & Interactions

### Upload
- Accept `.pdf`, `.txt`, `.docx` files via `st.file_uploader`
- Extract raw text and store in session state
- Display word/character count after upload
- Error if no file uploaded on Generate click

### Generate
- `st.button("Generate 5 MCQs")` triggers API call
- Each click replaces previous questions (no append)
- Loading spinner during API call
- Error toast if API fails

### MCQ Display
- 5 numbered cards with:
  - Question text
  - 4 options labeled A/B/C/D
  - Correct answer highlighted in green
- Expander per question to reveal/hide answer

## 5. Component Inventory

| Component | States |
|-----------|--------|
| File uploader | empty, file selected, processing |
| Generate button | idle, loading (spinner), disabled (no doc) |
| MCQ card | question visible, answer hidden, answer revealed |

## 6. Technical Approach

- **Framework**: Streamlit (Python)
- **AI**: Anthropic Claude API (`anthropic` SDK) with user-selectable model (Haiku, Sonnet, Opus)
- **Parsing**: Pydantic v2 models for MCQ schema validation
- **Documents**: `PyPDF2` for PDF, `python-docx` for DOCX, built-in for TXT
- **Prompt strategy**: Structured JSON schema instruction in system prompt so Claude outputs parsable JSON

### API Design

```
POST /mcq/generate
  Input:  raw_text (str), num_questions (int = 5)
  Output: List[MCQ]       # Pydantic-validated

MCQ:
  question: str
  options: List[str]   # always 4
  answer:   str         # must match one of options
  explanation: str
```

### Data Flow

```
Upload file
  → document_loader.extract_text()     # raw string
  → mcq_generator.generate_mcqs(text)   # API call
      → build_prompt(text, num)
      → anthropic.messages.create()
      → parse_response(raw_json)
      → Pydantic validation
  → app.py receives List[MCQ]
  → Streamlit renders cards
```
