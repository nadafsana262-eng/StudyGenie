
import os
import io
import json
import streamlit as st

from dotenv import load_dotenv
from google import genai
from google.genai import types

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from xml.sax.saxutils import escape


# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="StudyGenie",
    page_icon="🎓",
    layout="wide"
)

load_dotenv()

PRIMARY_MODEL = "gemini-3.5-flash-lite"
BACKUP_MODEL = "gemini-3.8-flash"

MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_TOTAL_SIZE = 20 * 1024 * 1024


# --------------------------------------------------
# 2. API KEY
# --------------------------------------------------

def get_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass

    return os.getenv("GEMINI_API_KEY")


# --------------------------------------------------
# 3. ERROR CLASSIFICATION
# --------------------------------------------------

def get_error_code(error):
    code = getattr(error, "code", None)

    if code is not None:
        try:
            return int(code)
        except (TypeError, ValueError):
            pass

    message = str(error).lower()

    for number in (429, 503, 502, 504, 500):
        if str(number) in message:
            return number

    return None


def is_temporary_error(error):
    code = get_error_code(error)

    return code in (500, 502, 503, 504)


# --------------------------------------------------
# 4. GEMINI GENERATION WITH BACKUP MODEL
# --------------------------------------------------

def generate_questions(client, content_parts, question_count, marks_each):

    models = [
        PRIMARY_MODEL,
        BACKUP_MODEL
    ]

    errors = []

    for model_name in models:

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                    max_output_tokens=8192
                )
            )

            if not response or not response.text:
                raise ValueError("The AI returned an empty response.")

            result = json.loads(response.text)

            if not isinstance(result, dict):
                raise ValueError("Invalid response format.")

            questions = result.get("questions")

            if not isinstance(questions, list) or not questions:
                raise ValueError("No questions were generated.")

            if len(questions) < question_count:
                raise ValueError(
                    f"The AI returned {len(questions)} questions, but "
                    f"{question_count} were requested. Please try again."
                )

            # Keep exactly the requested number and apply the chosen marks.
            result["questions"] = questions[:question_count]

            for question in result["questions"]:
                question["marks"] = marks_each

            return result

        except Exception as error:

            errors.append((model_name, error))

            code = get_error_code(error)

            # Do not waste time retrying quota or authentication errors.
            if code in (400, 401, 403, 429):
                raise

            # Try backup model for temporary server errors,
            # model availability errors, or invalid responses.
            if model_name == PRIMARY_MODEL:
                continue

    details = "; ".join(
        f"{name}: {str(error)[:250]}"
        for name, error in errors
    )

    raise RuntimeError(
        "Both Gemini models failed. Details: " + details
    )


# --------------------------------------------------
# 5. DESIGN
# --------------------------------------------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #f8f4ff, #eee5ff);
}

.main-title {
    text-align: center;
    color: #673ab7;
    font-size: 44px;
    font-weight: 800;
}

.subtitle {
    text-align: center;
    color: #655477;
    font-size: 17px;
}

div.stButton > button {
    background: linear-gradient(90deg, #7e57c2, #ab83e8);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 12px 25px;
    font-weight: bold;
}

div.stButton > button:hover {
    color: white;
    border: 1px solid #673ab7;
}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# 6. HEADER
# --------------------------------------------------

st.markdown(
    '<div class="main-title">🎓 StudyGenie</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Learn • Prepare • Excel ✨'
    '<br>AI Question Paper Generator'
    '</div>',
    unsafe_allow_html=True
)

st.divider()

st.info(
    "Upload your PDF notes or study photos. "
    "StudyGenie will automatically generate "
    "an exam-style question paper."
)


# --------------------------------------------------
# 7. FILE UPLOAD
# --------------------------------------------------

uploaded_files = st.file_uploader(
    "📚 Upload your study material",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True
)

if uploaded_files:

    st.success(
        f"{len(uploaded_files)} file(s) uploaded successfully!"
    )

    for file in uploaded_files:

        st.write(f"📄 {file.name}")

        if file.type.startswith("image/"):
            st.image(file, width=250)


# --------------------------------------------------
# 8. QUESTION PAPER SETTINGS
# --------------------------------------------------

st.markdown("## ⚙️ Question Paper Settings")

setting_col1, setting_col2 = st.columns(2)

with setting_col1:
    question_count = st.number_input(
        "Number of questions",
        min_value=1,
        max_value=100,
        value=12,
        step=1,
        help="Enter how many questions you want (1 to 100)."
    )

with setting_col2:
    marks_each = st.number_input(
        "Marks per question",
        min_value=1,
        max_value=100,
        value=5,
        step=1,
        help="Enter the marks for each question (1 to 100)."
    )

st.info(
    f"Your paper will contain {int(question_count)} questions "
    f"with {int(marks_each)} marks each. "
    f"Total marks: {int(question_count) * int(marks_each)}."
)


# --------------------------------------------------
# 9. GENERATE QUESTION PAPER
# --------------------------------------------------

if st.button(
    "✨ Generate Question Paper",
    use_container_width=True
):

    if not uploaded_files:

        st.warning("Please upload your notes first.")

    else:

        api_key = get_api_key()

        if not api_key:

            st.error(
                "Gemini API key not found. "
                "Please configure GEMINI_API_KEY."
            )
            st.stop()

        total_size = sum(
            file.size for file in uploaded_files
        )

        if total_size > MAX_TOTAL_SIZE:

            st.error(
                "Total upload size exceeds 20 MB. "
                "Please upload smaller files."
            )
            st.stop()

        invalid_file = next(
            (
                file for file in uploaded_files
                if file.size == 0
                or file.size > MAX_FILE_SIZE
            ),
            None
        )

        if invalid_file:

            st.error(
                f"{invalid_file.name} is empty "
                "or exceeds the file size limit."
            )
            st.stop()

        prompt = f"""
You are an expert college examination question paper generator.

Carefully read all uploaded study materials.
Automatically identify the subject and important topics.

Generate EXACTLY {int(question_count)} unique exam-style questions
based only on the uploaded material.

Every question must carry EXACTLY {int(marks_each)} marks.
Do not change the requested number of questions or marks.

Return ONLY valid JSON in this structure:

{{
  "subject": "Detected subject name",
  "topics": ["Topic 1", "Topic 2"],
  "questions": [
    {{
      "question": "Question text",
      "marks": {int(marks_each)}
    }}
  ]
}}

Requirements:
1. Generate exactly {int(question_count)} questions.
2. Every question must be worth exactly {int(marks_each)} marks.
3. Avoid duplicate or nearly identical questions.
4. Questions must be relevant to the uploaded notes.
5. Do not invent unrelated information.
6. Do not include answers.
7. Return valid JSON only.
"""

        try:

            with st.spinner(
                "✨ StudyGenie is analysing your notes..."
            ):

                content_parts = [prompt]

                for file in uploaded_files:

                    content_parts.append(
                        types.Part.from_bytes(
                            data=file.getvalue(),
                            mime_type=file.type
                        )
                    )

                client = genai.Client(
                    api_key=api_key,
                    http_options=types.HttpOptions(
                        timeout=90000
                    )
                )

                result = generate_questions(
                    client,
                    content_parts,
                    int(question_count),
                    int(marks_each)
                )

                result["marks_each"] = int(marks_each)
                result["requested_count"] = int(question_count)
                st.session_state["paper"] = result

            st.success(
                "🎉 Your question paper is ready!"
            )

        except Exception as error:

            code = get_error_code(error)

            if code == 429:

                st.error(
                    "Gemini API quota or rate limit reached. "
                    "Please check your Google AI Studio usage "
                    "and try again later."
                )

            elif code in (500, 502, 503, 504):

                st.error(
                    "Both AI models are temporarily unavailable. "
                    "Please try again later."
                )

            elif code in (401, 403):

                st.error(
                    "API authentication or permission error. "
                    "Check your Gemini API key and API access."
                )

            else:

                st.error(
                    "Unable to generate the question paper."
                )

            with st.expander("Technical error details"):
                st.code(str(error))


# --------------------------------------------------
# 9. DISPLAY GENERATED PAPER
# --------------------------------------------------

if "paper" in st.session_state:

    paper = st.session_state["paper"]

    st.divider()

    st.markdown("## 📝 Your Generated Question Paper")

    st.markdown(
        f"**Subject:** {paper.get('subject', 'Not detected')}"
    )

    topics = paper.get("topics", [])

    if topics:
        st.write(
            "**Important topics:** "
            + ", ".join(map(str, topics))
        )

    st.write("**Instructions:** Answer all questions.")

    total_marks = 0

    for index, item in enumerate(
        paper.get("questions", []), 1
    ):

        marks = int(paper.get("marks_each", item.get("marks", 5)))
        total_marks += marks

        st.markdown(
            f"**Q{index}. {item.get('question', '')}**"
        )

        st.caption(f"Marks: {marks}")

    st.markdown(f"### Total Marks: {total_marks}")


    # --------------------------------------------------
    # 10. PDF DOWNLOAD
    # --------------------------------------------------

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=HexColor("#673ab7"),
        alignment=TA_CENTER,
        spaceAfter=15
    )

    question_style = ParagraphStyle(
        "Question",
        parent=styles["Normal"],
        fontSize=11,
        leading=17,
        spaceAfter=5
    )

    story = [
        Paragraph("STUDYGENIE", title_style),
        Paragraph("IMPORTANT QUESTION PAPER", title_style),
        Spacer(1, 10),

        Paragraph(
            "<b>Subject:</b> "
            + escape(
                str(paper.get("subject", "Not detected"))
            ),
            styles["Normal"]
        ),

        Paragraph(
            f"<b>Total Marks:</b> {total_marks}",
            styles["Normal"]
        ),

        Spacer(1, 12),

        HRFlowable(
            width="100%",
            color=HexColor("#9670cf")
        ),

        Spacer(1, 15),

        Paragraph(
            "<b>Instructions:</b> Answer all questions.",
            styles["Normal"]
        ),

        Spacer(1, 15)
    ]

    for index, item in enumerate(
        paper.get("questions", []), 1
    ):

        question = escape(
            str(item.get("question", ""))
        )

        marks = int(paper.get("marks_each", item.get("marks", 5)))

        story.append(
            Paragraph(
                f"<b>Q{index}.</b> {question} "
                f"<b>[{marks} Marks]</b>",
                question_style
            )
        )

        story.append(Spacer(1, 12))

    doc.build(story)

    buffer.seek(0)

    st.download_button(
        label="📥 Download Question Paper PDF",
        data=buffer,
        file_name="StudyGenie_Question_Paper.pdf",
        mime="application/pdf",
        use_container_width=True
    )


# --------------------------------------------------
# 11. FOOTER
# --------------------------------------------------

st.divider()

st.markdown(
    "<center>💜 Made with StudyGenie | "
    "Learn • Prepare • Excel</center>",
    unsafe_allow_html=True
)
