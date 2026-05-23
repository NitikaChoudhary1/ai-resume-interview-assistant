import os
import pdfplumber
import docx
import speech_recognition as sr

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

app = Flask(__name__)
CORS(app)

# =========================
# SKILLS DATABASE
# =========================

SKILLS = [
    "python",
    "java",
    "javascript",
    "react",
    "node",
    "flask",
    "django",
    "sql",
    "mongodb",
    "machine learning",
    "data analysis",
    "html",
    "css",
    "git",
    "docker",
    "aws"
]

# =========================
# HOME ROUTE
# =========================

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

# =========================
# PDF TEXT EXTRACTION
# =========================

def extract_text_from_pdf(file):

    text = ""

    with pdfplumber.open(file) as pdf:

        for page in pdf.pages:
            extracted = page.extract_text()

            if extracted:
                text += extracted + "\n"

    return text

# =========================
# DOCX TEXT EXTRACTION
# =========================

def extract_text_from_docx(file):

    doc = docx.Document(file)

    text = "\n".join([para.text for para in doc.paragraphs])

    return text

# =========================
# SKILL FINDER
# =========================

def find_skills(text):

    text = text.lower()

    found = []

    for skill in SKILLS:

        if skill.lower() in text:
            found.append(skill)

    return found

# =========================
# OPENAI GPT FUNCTION
# =========================

def ask_gpt(prompt):

    try:

        response = client.chat.completions.create(
            model="gpt-4.1-mini",

            messages=[
                {
                    "role": "system",
                    "content": "You are an expert ATS resume reviewer and interview coach."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.7,
            max_tokens=800
        )

        return response.choices[0].message.content

    except Exception as e:

        return f"GPT Error: {str(e)}"

# =========================
# RESUME ANALYSIS ROUTE
# =========================

@app.route("/analyze-resume", methods=["POST"])
def analyze_resume():

    if "resume" not in request.files:
        return jsonify({"error": "No resume uploaded"}), 400

    if "job_description" not in request.form:
        return jsonify({"error": "No job description"}), 400

    resume = request.files["resume"]

    job_description = request.form["job_description"]

    filename = resume.filename.lower()

    # =========================
    # EXTRACT TEXT
    # =========================

    if filename.endswith(".pdf"):

        resume_text = extract_text_from_pdf(resume)

    elif filename.endswith(".docx"):

        resume_text = extract_text_from_docx(resume)

    else:

        return jsonify({"error": "Unsupported file format"}), 400

    # =========================
    # FIND SKILLS
    # =========================

    resume_skills = find_skills(resume_text)

    jd_skills = find_skills(job_description)

    matched_skills = list(set(resume_skills) & set(jd_skills))

    missing_skills = list(set(jd_skills) - set(resume_skills))

    # =========================
    # ATS SCORE
    # =========================

    if len(jd_skills) > 0:

        ats_score = int((len(matched_skills) / len(jd_skills)) * 100)

    else:

        ats_score = 0

    # =========================
    # GPT IMPROVED SUMMARY
    # =========================

    improved_summary = ask_gpt(
        f"""
        Create a professional ATS-friendly resume summary.

        Resume Skills:
        {resume_skills}

        Job Description:
        {job_description}

        Keep it concise and professional.
        """
    )

    # =========================
    # GPT PROJECT DESCRIPTIONS
    # =========================

    better_project_descriptions = ask_gpt(
        f"""
        Generate 3 ATS-friendly project descriptions.

        Resume Skills:
        {resume_skills}

        Job Description:
        {job_description}

        Use bullet points.
        """
    )

    # =========================
    # GPT ROLE KEYWORDS
    # =========================

    role_keywords = ask_gpt(
        f"""
        Extract important ATS keywords
        from this job description.

        Job Description:
        {job_description}
        """
    )

    # =========================
    # GPT INTERVIEW QUESTIONS
    # =========================

    interview_questions = ask_gpt(
        f"""
        Generate:

        1. HR interview questions
        2. Technical interview questions
        3. Behavioral interview questions
        4. STAR format sample answers

        Resume Skills:
        {resume_skills}

        Job Description:
        {job_description}
        """
    )

    return jsonify({

        "resume_skills": resume_skills,

        "job_description_skills": jd_skills,

        "matched_skills": matched_skills,

        "missing_skills": missing_skills,

        "ats_score": ats_score,

        "improved_summary": improved_summary,

        "better_project_descriptions": better_project_descriptions,

        "role_keywords": role_keywords,

        "interview_questions": interview_questions,

        "resume_preview": resume_text[:1500]
    })

# =========================
# MOCK INTERVIEW FEEDBACK
# =========================

@app.route("/analyze-answer", methods=["POST"])
def analyze_answer():

    data = request.get_json()

    answer = data.get("answer", "")

    feedback = ask_gpt(
        f"""
        Analyze this interview answer.

        Give:
        1. Clarity score out of 10
        2. Confidence score out of 10
        3. Missing points
        4. Improved answer

        Answer:
        {answer}
        """
    )

    return jsonify({
        "feedback": feedback
    })

# =========================
# VOICE ANALYSIS
# =========================

@app.route("/analyze-voice", methods=["POST"])
def analyze_voice():

    if "audio" not in request.files:
        return jsonify({"error": "No audio uploaded"}), 400

    audio_file = request.files["audio"]

    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_file) as source:

        audio = recognizer.record(source)

    try:

        text = recognizer.recognize_google(audio)

        feedback = ask_gpt(
            f"""
            Analyze this interview response.

            Give:
            1. Confidence score
            2. Clarity feedback
            3. Missing points
            4. Better answer

            Answer:
            {text}
            """
        )

        return jsonify({
            "transcript": text,
            "feedback": feedback
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        })

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    app.run(debug=True)