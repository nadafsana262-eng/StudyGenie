
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
    HRFlowable,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
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
# 3. ERROR HANDLING
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


# --------------------------------------------------
# 4. GENERATE QUESTIONS USING GEMINI
# --------------------------------------------------

def generate_questions(
    client,
    content_parts,
    question_count,
    marks_each,
    question_type,
    difficulty,
    include_answers
):

    prompt = f"""
You are an expert college examination paper generator.

Analyse the uploaded study material carefully.

Generate EXACTLY {question_count} unique questions.

QUESTION SETTINGS:

Question type: {question_type}
Difficulty level: {difficulty}
Marks per question: {marks_each}
Include answers: {include_answers}

IMPORTANT INSTRUCTIONS:

1. Generate exactly {question_count} questions.
2. Every question must carry exactly {marks_each} marks.
3. Questions must be based on the uploaded study material.
4. Avoid duplicate questions.
5. Match the selected difficulty level.
6. Do not invent unrelated information.

QUESTION TYPE RULES:

If question type is MCQ:
- Each question must have exactly four options.
- Options must be labelled A, B, C and D.
- Only one option should be correct.
- Include the correct option in the answer field.

If question type is Short Answer:
- Generate short-answer examination questions.
- Include a clear, relevant answer if answers are requested.

If question type is Long Answer:
- Generate detailed, descriptive examination questions.
- Include a suitable answer if answers are requested.

If question type is Mixed:
- Include a suitable combination of MCQs, short-answer
  questions and long-answer questions.
- MCQs must have four options.

ANSWER RULES:

If include_answers is true:
- Provide a correct answer for every question.
- For MCQs, provide the correct option and explanation.
- For other questions, provide a clear model answer.

If include_answers is false:
- Set the answer field to an empty string.

Return ONLY valid JSON in this format:

{{
  "subject": "Detected subject name",
  "topics": ["Topic 1", "Topic 2"],
  "difficulty": "{difficulty}",
  "question_type": "{question_type}",
  "questions": [
    {{
      "question": "Question text",
      "type": "MCQ",
      "options": {{
        "A": "Option A",
        "B": "Option B",
        "C": "Option C",
        "D": "Option D"
      }},
      "answer": "Correct answer",
      "explanation": "Explanation if applicable",
      "marks": {marks_each}
    }}
  ]
}}

For non-MCQ questions, use an empty object for options.

Return valid JSON only. Do not include Markdown.
"""

    content_parts = [prompt] + content_parts

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
                raise ValueError("Empty AI response.")

            result = json.loads(response.text)

            if not isinstance(result, dict):
                raise ValueError("Invalid JSON response.")

            questions = result.get("questions")

            if not isinstance(questions, list):
                raise ValueError("Questions were not returned.")

            if len(questions) < question_count:
                raise ValueError(
                    f"Only {len(questions)} questions were generated. "
                    f"{question_count} were requested."
                )

            questions = questions[:question_count]

            for question in questions:

                question["marks"] = marks_each

                if not include_answers:
                    question["answer"] = ""
                    question["explanation"] = ""

                if not isinstance(question.get("options"), dict):
                    question["options"] = {}

                if question.get("type") == "MCQ":

                    options = question["options"]

                    for option in ["A", "B", "C", "D"]:
                        if not options.get(option):
                            raise ValueError(
                                "An MCQ is missing one or more options."
                            )

                    if include_answers and not question.get("answer"):
                        raise ValueError(
                            "An MCQ is missing its correct answer."
                        )

            result["questions"] = questions

            return result

        except Exception as error:

            errors.append(f"{model_name}: {str(error)}")

            code = get_error_code(error)

            if code in (400, 401, 403, 429):
                raise

    raise RuntimeError(
        "AI generation failed. " + " | ".join(errors)
    )


# --------------------------------------------------
# 5. PURPLE UI DESIGN
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
    "Upload your study material and generate "
    "AI-powered questions, answers and MCQs."
)


# --------------------------------------------------
# 7. UPLOAD STUDY MATERIAL
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

col1, col2 = st.columns(2)

with col1:

    question_count = st.number_input(
        "Number of questions",
        min_value=1,
        max_value=100,
        value=12,
        step=1
    )

with col2:

    marks_each = st.number_input(
        "Marks per question",
        min_value=1,
        max_value=100,
        value=5,
        step=1
    )

st.markdown("### Question Type")

question_type = st.selectbox(
    "Choose question format",
    [
        "MCQ",
        "Short Answer",
        "Long Answer",
        "Mixed"
    ]
)

st.markdown("### Difficulty Level")

difficulty = st.selectbox(
    "Choose difficulty",
    [
        "Easy",
        "Medium",
        "Hard",
        "Mixed"
    ]
)

st.markdown("### Answer Settings")

include_answers = st.checkbox(
    "Include answers and explanations",
    value=True
)

st.info(
    f"**Questions:** {int(question_count)}  \n"
    f"**Marks per question:** {int(marks_each)}  \n"
    f"**Total marks:** {int(question_count) * int(marks_each)}  \n"
    f"**Question type:** {question_type}  \n"
    f"**Difficulty:** {difficulty}  \n"
    f"**Answers included:** {'Yes' if include_answers else 'No'}"
)


# --------------------------------------------------
# 9. GENERATE QUESTION PAPER
# --------------------------------------------------

if st.button(
    "✨ Generate Question Paper",
    use_container_width=True
):

    if not uploaded_files:

        st.warning("Please upload your study material first.")

    else:

        api_key = get_api_key()

        if not api_key:

            st.error(
                "Gemini API key not found. "
                "Configure GEMINI_API_KEY first."
            )
            st.stop()

        total_size = sum(
            file.size for file in uploaded_files
        )

        if total_size > MAX_TOTAL_SIZE:

            st.error("Total upload size exceeds 20 MB.")
            st.stop()

        invalid_file = next(
            (
                file for file in uploaded_files
                if file.size == 0 or file.size > MAX_FILE_SIZE
            ),
            None
        )

        if invalid_file:

            st.error(
                f"{invalid_file.name} is empty "
                "or exceeds the file size limit."
            )
            st.stop()

        try:

            with st.spinner(
                "✨ StudyGenie is analysing your notes..."
            ):

                client = genai.Client(
                    api_key=api_key,
                    http_options=types.HttpOptions(
                        timeout=90000
                    )
                )

                content_parts = []

                for file in uploaded_files:

                    content_parts.append(
                        types.Part.from_bytes(
                            data=file.getvalue(),
                            mime_type=file.type
                        )
                    )

                result = generate_questions(
                    client=client,
                    content_parts=content_parts,
                    question_count=int(question_count),
                    marks_each=int(marks_each),
                    question_type=question_type,
                    difficulty=difficulty,
                    include_answers=include_answers
                )

                result["marks_each"] = int(marks_each)
                result["include_answers"] = include_answers
                result["requested_count"] = int(question_count)

                st.session_state["paper"] = result

            st.success("🎉 Your question paper is ready!")

        except Exception as error:

            code = get_error_code(error)

            if code == 429:

                st.error(
                    "Gemini API quota or rate limit reached. "
                    "Please try again later."
                )

            elif code in (500, 502, 503, 504):

                st.error(
                    "The AI service is temporarily unavailable. "
                    "Please try again later."
                )

            elif code in (401, 403):

                st.error(
                    "API authentication error. "
                    "Check your Gemini API key and permissions."
                )

            else:

                st.error("Unable to generate the question paper.")

            with st.expander("Technical error details"):
                st.code(str(error))


# --------------------------------------------------
# 10. DISPLAY QUESTION PAPER
# --------------------------------------------------

if "paper" in st.session_state:

    paper = st.session_state["paper"]

    st.divider()

    st.markdown("## 📝 Generated Question Paper")

    st.write(
        f"**Subject:** {paper.get('subject', 'Not detected')}"
    )

    st.write(
        f"**Difficulty:** {paper.get('difficulty', 'Not specified')}"
    )

    topics = paper.get("topics", [])

    if topics:
        st.write("**Topics:** " + ", ".join(map(str, topics)))

    st.write("**Instructions:** Answer all questions.")

    total_marks = 0

    for index, question in enumerate(
        paper.get("questions", []), 1
    ):

        marks = int(question.get("marks", 0))
        total_marks += marks

        st.markdown(
            f"**Q{index}. {question.get('question', '')}**"
        )

        if question.get("type") == "MCQ":

            options = question.get("options", {})

            for letter in ["A", "B", "C", "D"]:

                if options.get(letter):
                    st.write(
                        f"**{letter}.** {options[letter]}"
                    )

        st.caption(f"Marks: {marks}")

        if paper.get("include_answers"):

            with st.expander(f"View Answer {index}"):

                st.write(
                    "**Answer:** "
                    + str(question.get("answer", "Not provided"))
                )

                explanation = question.get("explanation", "")

                if explanation:
                    st.write("**Explanation:** " + str(explanation))

        st.divider()

    st.markdown(f"### Total Marks: {total_marks}")


    # --------------------------------------------------
    # 11. PDF GENERATION
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
        alignment=1,
        spaceAfter=15
    )

    question_style = ParagraphStyle(
        "Question",
        parent=styles["Normal"],
        fontSize=11,
        leading=17,
        spaceAfter=5
    )

    option_style = ParagraphStyle(
        "Option",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        leftIndent=20,
        spaceAfter=3
    )

    answer_style = ParagraphStyle(
        "Answer",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        leftIndent=10,
        textColor=HexColor("#45227b"),
        spaceAfter=8
    )

    story = [

        Paragraph("STUDYGENIE", title_style),

        Paragraph("QUESTION PAPER", title_style),

        Spacer(1, 10),

        Paragraph(
            "<b>Subject:</b> "
            + escape(str(paper.get("subject", "Not detected"))),
            styles["Normal"]
        ),

        Paragraph(
            "<b>Difficulty:</b> "
            + escape(str(paper.get("difficulty", ""))),
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

    for index, question in enumerate(
        paper.get("questions", []), 1
    ):

        question_text = escape(
            str(question.get("question", ""))
        )

        marks = int(question.get("marks", 0))

        story.append(
            Paragraph(
                f"<b>Q{index}.</b> {question_text} "
                f"<b>[{marks} Marks]</b>",
                question_style
            )
        )

        if question.get("type") == "MCQ":

            options = question.get("options", {})

            for letter in ["A", "B", "C", "D"]:

                option_text = escape(
                    str(options.get(letter, ""))
                )

                if option_text:
                    story.append(
                        Paragraph(
                            f"<b>{letter}.</b> {option_text}",
                            option_style
                        )
                    )

        story.append(Spacer(1, 8))

        if paper.get("include_answers"):

            answer = escape(
                str(question.get("answer", "Not provided"))
            )

            story.append(
                Paragraph(
                    f"<b>Answer:</b> {answer}",
                    answer_style
                )
            )

            explanation = question.get("explanation", "")

            if explanation:

                story.append(
                    Paragraph(
                        "<b>Explanation:</b> "
                        + escape(str(explanation)),
                        answer_style
                    )
                )

        story.append(Spacer(1, 10))

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
# 12. FOOTER
# --------------------------------------------------

st.divider()

st.markdown(
    "<center>💜 Made with StudyGenie | "
    "Learn • Prepare • Excel</center>",
    unsafe_allow_html=True
)
