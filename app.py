"""
AI LMS — MCQ Generator
Streamlit UI entry point.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import streamlit as st
import traceback

from services.document_loader import load_document
from services.mcq_generator import generate_mcqs
from services.models import MCQ

st.set_page_config(
    page_title="AI MCQ Generator",
    page_icon=None,
    layout="centered",
)

st.markdown(
    """
    <style>
    :root {
        --mcq-bg: rgba(128, 128, 128, 0.05);
        --mcq-border: rgba(128, 128, 128, 0.2);
        --mcq-text: inherit;
        --mcq-question-color: #ff4b4b;
        --mcq-correct: #2e7d32;
        --mcq-explanation: rgba(128, 128, 128, 0.7);
    }
    .mcq-card {
        border: 1px solid var(--mcq-border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        background-color: var(--mcq-bg);
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: transform 0.2s ease;
    }
    .mcq-card:hover {
        border-color: var(--mcq-question-color);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .mcq-question {
        font-size: 1.15rem;
        font-weight: 700;
        margin-bottom: 1rem;
        color: var(--mcq-question-color);
        line-height: 1.4;
    }
    .option-item {
        margin: 0.5rem 0;
        font-size: 1rem;
        padding: 0.4rem 0.8rem;
        border-radius: 6px;
        background: rgba(128, 128, 128, 0.03);
    }
    .correct-answer {
        color: var(--mcq-correct);
        font-weight: 700;
        background: rgba(46, 125, 50, 0.1);
        padding: 0.4rem 0.8rem;
        border-radius: 6px;
        margin: 0.5rem 0;
        border-left: 4px solid var(--mcq-correct);
    }
    .explanation {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid var(--mcq-border);
        font-size: 0.9rem;
        color: var(--mcq-explanation);
        font-style: italic;
        line-height: 1.5;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state():
    defaults = {
        "document_text": "",
        "word_count": 0,
        "char_count": 0,
        "mcqs": [],
        "uploaded": False,
        "api_key": "",
        "model": "claude-haiku-4-5",
        "max_tokens": 2048,
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)


_init_state()


with st.sidebar:
    st.header("API Key")
    api_key_input = st.text_input(
        "Anthropic API Key",
        type="password",
        value=st.session_state.api_key,
        placeholder="sk-ant-...",
        help="Get your key at console.anthropic.com",
    )
    if api_key_input != st.session_state.api_key:
        st.session_state.api_key = api_key_input
        st.rerun()

    st.header("Model")
    model = st.selectbox(
        "Choose Claude model",
        options=[
            ("claude-haiku-4-5", "Haiku 4.5 (fast & cheap)"),
            ("claude-sonnet-4-20250514", "Sonnet 4 (balanced)"),
            ("claude-opus-4-20250514", "Opus 4 (best quality)"),
        ],
        format_func=lambda x: x[1],
        index=0,
    )
    selected_model = model[0]
    if "model" not in st.session_state or st.session_state.model != selected_model:
        st.session_state.model = selected_model
        st.session_state.mcqs = []

    st.divider()
    st.header("Max Output Tokens")
    max_tokens = st.slider(
        "Max tokens per generation",
        min_value=512,
        max_value=8192,
        value=st.session_state.max_tokens,
        step=256,
        help="Higher values allow longer / more-detailed answers. 2048 is enough for 5 MCQs.",
    )
    if max_tokens != st.session_state.max_tokens:
        st.session_state.max_tokens = max_tokens

    st.divider()
    st.header("Upload Training Material")

    uploaded_file = st.file_uploader(
        "Supported: .txt, .pdf, .docx",
        type=["txt", "pdf", "docx"],
        help="Upload your training document. The AI will read it to generate MCQs.",
    )

    if uploaded_file is not None and not st.session_state.uploaded:
        with st.spinner("Extracting text…"):
            try:
                text, words, chars = load_document(uploaded_file)
                st.session_state.document_text = text
                st.session_state.word_count = words
                st.session_state.char_count = chars
                st.session_state.uploaded = True
                st.session_state.mcqs = []
                st.success("Document loaded successfully!")
            except Exception as exc:
                st.error(f"Failed to read file: {exc}")

    if st.session_state.uploaded:
        st.divider()
        st.caption("Document Stats")

        # Truncation warning
        CHAR_LIMIT = 600_000
        if st.session_state.char_count > CHAR_LIMIT:
            st.warning(f"⚠️ Document is very large ({st.session_state.char_count:,} chars). The AI will process the first {CHAR_LIMIT:,} characters to ensure stable generation.")

        st.metric("Words", f"{st.session_state.word_count:,}")
        st.metric("Characters", f"{st.session_state.char_count:,}")
        preview = st.session_state.document_text[:300]
        with st.expander("🔍 Text preview (first 300 chars)"):
            st.text(preview + "…" if len(st.session_state.document_text) > 300 else preview)


st.title("AI MCQ Generator")
st.caption("Upload a training document → click Generate → get 5 fresh MCQs instantly.")
st.divider()

col_btn, col_status = st.columns([1, 2])

with col_btn:
    generate_disabled = not st.session_state.uploaded or not st.session_state.api_key
    clicked = st.button(
        "Generate 5 MCQs",
        disabled=generate_disabled,
        use_container_width=True,
        type="primary",
    )

if generate_disabled:
    with col_status:
        if not st.session_state.api_key:
            st.info("🔑 Enter your API key in the sidebar to enable generation.")
        else:
            st.info("⬆️ Upload a document first to enable generation.")

if clicked:
    with st.spinner("🤖 AI is reading the document and generating questions…"):
        try:
            mcqs = generate_mcqs(
                st.session_state.document_text,
                num=5,
                api_key=st.session_state.api_key,
                model=st.session_state.model,
                max_tokens=st.session_state.max_tokens,
                exclude_questions=st.session_state.mcqs,
            )
            st.session_state.mcqs = mcqs
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
            st.code(traceback.format_exc(), language="text")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
            st.code(traceback.format_exc(), language="text")


if st.session_state.mcqs:
    st.subheader(f"{len(st.session_state.mcqs)} Questions Generated")
    st.caption("Each click of **Generate** replaces these with a new set.")

    for idx, mcq in enumerate(st.session_state.mcqs, start=1):
        labels = ["A", "B", "C", "D"]
        options_html = ""
        for label, opt in zip(labels, mcq.options):
            css_class = "correct-answer" if opt == mcq.answer else "option-item"
            options_html += f'<div class="{css_class}"><strong>{label}.</strong> {opt}</div>'

        html = f"""
        <div class="mcq-card">
            <div class="mcq-question">Q{idx}. {mcq.question}</div>
            {options_html}
            <div class="explanation">Explanation: {mcq.explanation}</div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
