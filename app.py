
import os
import json
import io
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from xml.sax.saxutils import escape

# ---------------- CONFIGURATION ----------------

load_dotenv()
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.getenv("GEMINI_API_KEY")
st.set_page_config(
    page_title="StudyGenie",
    page_icon="🎓",
    layout="wide"
)

# ---------------- DESIGN ----------------

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

# ---------------- HEADER ----------------

st.markdown(
    '<div class="main-title">🎓 StudyGenie</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Learn • Prepare • Excel ✨'
    '<br>AI Question Paper Generator</div>',
    unsafe_allow_html=True
)

st.divider()

st.info(
    "Upload your PDF notes or photos of your notes. "
    "StudyGenie will read your material and generate "
    "an exam-style question paper automatically."
)

# ---------------- FILE UPLOAD ----------------

uploaded_files = st.file_uploader(
    "📚 Upload your study material",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
    help="You can upload PDFs and photos of handwritten or printed notes."
)

if uploaded_files:
    st.success(f"{len(uploaded_files)} file(s) uploaded successfully!")

    for file in uploaded_files:
        st.write(f"📄 {file.name}")

        if file.type.startswith("image/"):
            st.image(file, caption=file.name, width=300)

# ---------------- GENERATE QUESTIONS ----------------

if st.button("✨ Generate Question Paper", use_container_width=True):

    if not uploaded_files:
        st.warning("Please upload at least one PDF or photo first.")

    else:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            st.error("Gemini API key not found. Check your .env file.")
            st.stop()

        if sum(file.size for file in uploaded_files) > 20 * 1024 * 1024:
            st.error("Your uploaded files exceed 20 MB. Please upload smaller files.")
            st.stop()

        client = genai.Client(api_key=api_key)

        prompt = """
        You are an expert college examination question paper generator.

        Read all the uploaded study materials carefully.
        The files can contain printed text, handwritten notes,
        diagrams, tables, formulas or textbook content.

        Automatically identify the subject and important topics.

        Generate exactly 12 useful, exam-style questions based
        on the uploaded material.

        Do not ask the user to select a subject, unit, marks,
        difficulty or question type.

        Return ONLY valid JSON in this exact structure:

        {
          "subject": "Detected subject name",
          "topics": ["Topic 1", "Topic 2"],
          "questions": [
            {
              "question": "Question text",
              "marks": 5
            }
          ]
        }

        Requirements:
        - Questions must be relevant to the uploaded material.
        - Include a mixture of short and long answer questions.
        - Assign reasonable marks (2, 5 or 10).
        - Avoid duplicate questions.
        - Do not invent content unrelated to the notes.
        - If handwriting is unclear, do not guess missing information.
        """

        content_parts = [prompt]

        try:
            with st.spinner(
                "✨ StudyGenie is reading your notes and preparing questions..."
            ):

                for file in uploaded_files:
                    file_bytes = file.getvalue()

                    part = types.Part.from_bytes(
                        data=file_bytes,
                        mime_type=file.type
                    )

                    content_parts.append(part)

                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=content_parts,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.4
                    )
                )

                result = json.loads(response.text)

                st.session_state["paper"] = result

            st.success("Your question paper has been generated!")

        except Exception as e:
            st.error("Something went wrong while generating questions.")
            st.error(str(e))

# ---------------- DISPLAY QUESTION PAPER ----------------

if "paper" in st.session_state:

    paper = st.session_state["paper"]

    st.divider()

    st.markdown("## 📝 Your Generated Question Paper")

    st.markdown(
        f"**Subject:** {paper.get('subject', 'Not detected')}"
    )

    topics = paper.get("topics", [])

    if topics:
        st.write("**Important topics:** " + ", ".join(topics))

    st.write("**Instructions:** Answer all questions.")

    total_marks = 0

    for index, item in enumerate(paper.get("questions", []), 1):

        marks = int(item.get("marks", 5))
        total_marks += marks

        st.markdown(
            f"**Q{index}. {item.get('question', '')}**"
        )

        st.caption(f"Marks: {marks}")

    st.markdown(f"### Total Marks: {total_marks}")

    # ---------------- DOWNLOAD PDF ----------------

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

    story = []

    story.append(Paragraph("STUDYGENIE", title_style))
    story.append(Paragraph("IMPORTANT QUESTION PAPER", title_style))
    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            f"<b>Subject:</b> {escape(str(paper.get('subject', 'Not detected')))}",
            styles["Normal"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Total Marks:</b> {total_marks}",
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", color=HexColor("#9670cf")))
    story.append(Spacer(1, 15))

    story.append(
        Paragraph("<b>Instructions:</b> Answer all questions.", styles["Normal"])
    )

    story.append(Spacer(1, 15))

    for index, item in enumerate(paper.get("questions", []), 1):

        question = escape(str(item.get("question", "")))
        marks = int(item.get("marks", 5))

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

st.divider()

st.markdown(
    "<center>💜 Made with StudyGenie | Learn • Prepare • Excel</center>",
    unsafe_allow_html=True
)
