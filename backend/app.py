import os
import uuid
import datetime

import pdfplumber
import speech_recognition as sr
from docx import Document
from pydub import AudioSegment
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt
from openai import OpenAI

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config["SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "NITIKA_SECRET_KEY")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["resume_assistant"]

users_collection = db["users"]
reports_collection = db["reports"]
interview_collection = db["interview_history"]

SKILLS_DATABASE = [
    "python", "java", "javascript", "html", "css", "react", "node",
    "mongodb", "sql", "mysql", "machine learning", "deep learning",
    "tensorflow", "flask", "django", "docker", "kubernetes", "aws",
    "git", "github", "communication", "leadership", "nlp",
    "data analysis", "c++", "c", "pandas", "numpy", "opencv",
    "streamlit", "spring boot", "microservices", "rest api", "api",
    "jwt", "openai", "mongodb atlas"
]


@app.route("/")
def home():
    return send_from_directory(os.getcwd(), "index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "running",
        "message": "AI Resume Interview Assistant API is healthy"
    })


def verify_token(req):
    auth_header = req.headers.get("Authorization")

    if not auth_header:
        return None

    try:
        token = auth_header.split(" ")[1]

        decoded = jwt.decode(
            token,
            app.config["SECRET_KEY"],
            algorithms=["HS256"]
        )

        return decoded["user_id"]

    except Exception:
        return None


def ask_gpt(prompt):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert ATS resume reviewer and AI interview coach."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=900
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"GPT Error: {str(e)}"


@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    existing_user = users_collection.find_one({"email": email})

    if existing_user:
        return jsonify({"error": "User already exists"}), 400

    hashed_password = generate_password_hash(password)

    users_collection.insert_one({
        "name": name,
        "email": email,
        "password": hashed_password,
        "created_at": datetime.datetime.utcnow()
    })

    return jsonify({"message": "Signup successful"}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = users_collection.find_one({"email": email})

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    if not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = jwt.encode(
        {
            "user_id": str(user["_id"]),
            "email": user["email"],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
        },
        app.config["SECRET_KEY"],
        algorithm="HS256"
    )

    return jsonify({
        "message": "Login successful",
        "token": token,
        "name": user["name"],
        "email": user["email"]
    })


@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()

    email = data.get("email")
    new_password = data.get("new_password")

    if not email or not new_password:
        return jsonify({"error": "Email and new password are required"}), 400

    user = users_collection.find_one({"email": email})

    if not user:
        return jsonify({"error": "User not found"}), 404

    hashed_password = generate_password_hash(new_password)

    users_collection.update_one(
        {"email": email},
        {"$set": {"password": hashed_password}}
    )

    return jsonify({
        "message": "Password reset successful. Please login with your new password."
    })


def extract_pdf_text(file_path):
    text = ""

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

    return text


def extract_docx_text(file_path):
    document = Document(file_path)
    text = ""

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"

    return text


def extract_skills(text):
    text = text.lower()
    found_skills = []

    for skill in SKILLS_DATABASE:
        if skill.lower() in text:
            found_skills.append(skill)

    return list(set(found_skills))


def calculate_ats_score(resume_skills, jd_skills):
    if not jd_skills:
        return 0

    matched = set(resume_skills).intersection(set(jd_skills))
    score = (len(matched) / len(jd_skills)) * 100

    return round(score)


@app.route("/analyze-resume", methods=["POST"])
def analyze_resume():
    if "resume" not in request.files:
        return jsonify({"error": "Resume not uploaded"}), 400

    resume = request.files["resume"]
    job_description = request.form.get("job_description")

    if not job_description:
        return jsonify({"error": "Job description required"}), 400

    filename = secure_filename(resume.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    resume.save(file_path)

    if filename.lower().endswith(".pdf"):
        resume_text = extract_pdf_text(file_path)

    elif filename.lower().endswith(".docx"):
        resume_text = extract_docx_text(file_path)

    else:
        return jsonify({"error": "Unsupported file type. Upload PDF or DOCX only."}), 400

    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(job_description)

    matched_skills = list(set(resume_skills).intersection(set(jd_skills)))
    missing_skills = list(set(jd_skills) - set(resume_skills))

    ats_score = calculate_ats_score(resume_skills, jd_skills)

    improved_summary = ask_gpt(f"""
    Write a professional ATS-friendly resume summary.

    Resume:
    {resume_text[:3000]}

    Job Description:
    {job_description}
    """)

    better_projects = ask_gpt(f"""
    Improve the candidate's project descriptions for this role.

    Resume:
    {resume_text[:3000]}

    Job Description:
    {job_description}

    Return 3 strong bullet points.
    """)

    role_keywords = ask_gpt(f"""
    Extract the most important ATS keywords from this job description.

    Job Description:
    {job_description}
    """)

    interview_questions = ask_gpt(f"""
    Generate interview preparation content for this job.

    Include:
    1. HR questions
    2. Technical questions
    3. Behavioral questions
    4. STAR sample answers

    Resume Skills:
    {resume_skills}

    Job Description:
    {job_description}
    """)

    result = {
        "ats_score": ats_score,
        "resume_skills": resume_skills,
        "job_description_skills": jd_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "improved_summary": improved_summary,
        "better_project_descriptions": better_projects,
        "role_keywords": role_keywords,
        "interview_questions": interview_questions,
        "resume_preview": resume_text[:5000],
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    user_id = verify_token(request)

    if user_id:
        reports_collection.insert_one({
            "user_id": user_id,
            "result": result,
            "created_at": datetime.datetime.utcnow()
        })
        result["saved_to_database"] = True
    else:
        result["saved_to_database"] = False

    return jsonify(result)


@app.route("/reports", methods=["GET"])
def reports():
    user_id = verify_token(request)

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    saved_reports = list(
        reports_collection.find({"user_id": user_id}).sort("created_at", -1)
    )

    for report in saved_reports:
        report["_id"] = str(report["_id"])

    return jsonify({"reports": saved_reports})


@app.route("/generate-interview-question", methods=["POST"])
def generate_interview_question():
    data = request.get_json()

    job_description = data.get("job_description", "")
    resume_skills = data.get("resume_skills", [])

    if not job_description:
        return jsonify({"error": "Job description is required"}), 400

    question = ask_gpt(f"""
    Generate ONE realistic interview question based on this job description and candidate skills.

    Job Description:
    {job_description}

    Candidate Skills:
    {resume_skills}

    Return only the question.
    """)

    return jsonify({"question": question})


@app.route("/analyze-answer", methods=["POST"])
def analyze_answer():
    data = request.get_json()

    answer = data.get("answer", "")

    if not answer:
        return jsonify({"error": "Answer required"}), 400

    feedback = ask_gpt(f"""
    Evaluate this interview answer.

    Give:
    - Confidence score out of 10
    - Communication score out of 10
    - Technical score out of 10
    - ATS relevance score out of 100
    - Missing points
    - Improvement suggestions
    - Better answer

    Answer:
    {answer}
    """)

    return jsonify({"feedback": feedback})


@app.route("/analyze-voice", methods=["POST"])
def analyze_voice():
    if "audio" not in request.files:
        return jsonify({"error": "Audio missing"}), 400

    audio = request.files["audio"]

    original_path = os.path.join(UPLOAD_FOLDER, "voice_answer.webm")
    wav_path = os.path.join(UPLOAD_FOLDER, "voice_answer.wav")

    audio.save(original_path)

    try:
        audio_file = AudioSegment.from_file(original_path)
        audio_file.export(wav_path, format="wav")

        recognizer = sr.Recognizer()

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        transcript = recognizer.recognize_google(audio_data)

    except Exception as e:
        return jsonify({"error": "Speech recognition failed: " + str(e)}), 500

    feedback = ask_gpt(f"""
    Evaluate this spoken interview answer.

    Give:
    - Confidence score
    - Communication score
    - Technical score
    - Missing points
    - Suggestions
    - Better answer

    Answer:
    {transcript}
    """)

    return jsonify({
        "transcript": transcript,
        "feedback": feedback
    })


@app.route("/voice-interview-evaluate", methods=["POST"])
def voice_interview_evaluate():
    if "audio" not in request.files:
        return jsonify({"error": "Audio missing"}), 400

    audio = request.files["audio"]
    question = request.form.get("question")
    job_description = request.form.get("job_description")

    if not question:
        return jsonify({"error": "Interview question missing"}), 400

    original_path = os.path.join(UPLOAD_FOLDER, "candidate_interview.webm")
    wav_path = os.path.join(UPLOAD_FOLDER, "candidate_interview.wav")

    audio.save(original_path)

    try:
        audio_file = AudioSegment.from_file(original_path)
        audio_file.export(wav_path, format="wav")

        recognizer = sr.Recognizer()

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        transcript = recognizer.recognize_google(audio_data)

    except Exception as e:
        return jsonify({"error": "Speech recognition failed: " + str(e)}), 500

    evaluation = ask_gpt(f"""
    You are an AI interviewer.

    Interview Question:
    {question}

    Candidate Answer:
    {transcript}

    Job Description:
    {job_description}

    Give:
    - Interview Answer Score out of 100
    - ATS Interview Match Score out of 100
    - Confidence score out of 10
    - Communication score out of 10
    - Technical score out of 10
    - Strong points
    - Missing keywords/concepts
    - What candidate should improve
    - Better sample answer
    - Final hiring recommendation
    """)

    user_id = verify_token(request)
    saved = False

    if user_id:
        interview_collection.insert_one({
            "user_id": user_id,
            "question": question,
            "transcript": transcript,
            "evaluation": evaluation,
            "created_at": datetime.datetime.utcnow()
        })
        saved = True

    return jsonify({
        "transcript": transcript,
        "evaluation": evaluation,
        "saved_to_database": saved
    })


@app.route("/interview-history", methods=["GET"])
def interview_history():
    user_id = verify_token(request)

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    interviews = list(
        interview_collection.find({"user_id": user_id}).sort("created_at", -1)
    )

    for item in interviews:
        item["_id"] = str(item["_id"])

    return jsonify({"interviews": interviews})


if __name__ == "__main__":
    app.run(debug=True, port=5001)