import os
import uuid
from datetime import timedelta

import pdfplumber
import speech_recognition as sr
from docx import Document
from pydub import AudioSegment
from dotenv import load_dotenv
from openai import OpenAI
from pymongo import MongoClient
import bcrypt

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    verify_jwt_in_request
)

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "default-secret")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=7)

jwt = JWTManager(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["resume_assistant"]
users_collection = db["users"]
reports_collection = db["reports"]

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SKILLS = [
    "python", "java", "javascript", "react", "node", "node.js",
    "flask", "django", "fastapi", "sql", "mysql", "mongodb",
    "machine learning", "deep learning", "ai", "nlp",
    "data analysis", "pandas", "numpy", "tensorflow", "pytorch",
    "html", "css", "git", "docker", "aws", "api", "rest api"
]


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


def extract_text_from_pdf(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

    return text


def extract_text_from_docx(file):
    document = Document(file)
    text = ""

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"

    return text


def find_skills(text):
    text = text.lower()
    found = []

    for skill in SKILLS:
        if skill.lower() in text:
            found.append(skill)

    return list(set(found))


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
        return jsonify({"error": "Name, email, and password are required"}), 400

    existing_user = users_collection.find_one({"email": email})

    if existing_user:
        return jsonify({"error": "User already exists"}), 400

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    users_collection.insert_one({
        "name": name,
        "email": email,
        "password": hashed_password
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

    if not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=email)

    return jsonify({
        "message": "Login successful",
        "token": token,
        "name": user["name"],
        "email": user["email"]
    })


@app.route("/analyze-resume", methods=["POST"])
def analyze_resume():
    if "resume" not in request.files:
        return jsonify({"error": "No resume uploaded"}), 400

    if "job_description" not in request.form:
        return jsonify({"error": "No job description provided"}), 400

    resume = request.files["resume"]
    job_description = request.form["job_description"]

    filename = resume.filename.lower()

    if filename.endswith(".pdf"):
        resume_text = extract_text_from_pdf(resume)

    elif filename.endswith(".docx"):
        resume_text = extract_text_from_docx(resume)

    else:
        return jsonify({"error": "Unsupported file format. Upload PDF or DOCX only."}), 400

    resume_skills = find_skills(resume_text)
    jd_skills = find_skills(job_description)

    matched_skills = list(set(resume_skills) & set(jd_skills))
    missing_skills = list(set(jd_skills) - set(resume_skills))

    if len(jd_skills) > 0:
        ats_score = int((len(matched_skills) / len(jd_skills)) * 100)
    else:
        ats_score = 0

    improved_summary = ask_gpt(f"""
    Create a professional ATS-friendly resume summary.

    Resume Skills:
    {resume_skills}

    Job Description:
    {job_description}

    Keep it concise and professional.
    """)

    better_project_descriptions = ask_gpt(f"""
    Generate 3 ATS-friendly project descriptions.

    Resume Skills:
    {resume_skills}

    Job Description:
    {job_description}

    Use bullet points.
    """)

    role_keywords = ask_gpt(f"""
    Extract important ATS keywords from this job description.

    Job Description:
    {job_description}
    """)

    interview_questions = ask_gpt(f"""
    Generate:

    1. HR interview questions
    2. Technical interview questions
    3. Behavioral interview questions
    4. STAR format sample answers

    Resume Skills:
    {resume_skills}

    Job Description:
    {job_description}
    """)

    result = {
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
    }

    try:
        verify_jwt_in_request(optional=True)
        current_user = get_jwt_identity()

        if current_user:
            reports_collection.insert_one({
                "user_email": current_user,
                "report_id": str(uuid.uuid4()),
                "result": result
            })

    except Exception:
        pass

    return jsonify(result)


@app.route("/reports", methods=["GET"])
@jwt_required()
def get_reports():
    current_user = get_jwt_identity()

    reports = list(reports_collection.find(
        {"user_email": current_user},
        {"_id": 0}
    ))

    return jsonify({"reports": reports})


@app.route("/analyze-answer", methods=["POST"])
def analyze_answer():
    data = request.get_json()
    answer = data.get("answer", "")

    if not answer.strip():
        return jsonify({"error": "Answer is required"}), 400

    feedback = ask_gpt(f"""
    Analyze this interview answer.

    Give:
    1. Clarity score out of 10
    2. Confidence score out of 10
    3. Missing points
    4. Improved answer

    Answer:
    {answer}
    """)

    return jsonify({"feedback": feedback})


@app.route("/analyze-voice", methods=["POST"])
def analyze_voice():
    if "audio" not in request.files:
        return jsonify({"error": "No audio uploaded"}), 400

    audio_file = request.files["audio"]

    original_path = os.path.join(UPLOAD_FOLDER, "voice_input.webm")
    wav_path = os.path.join(UPLOAD_FOLDER, "voice_input.wav")

    audio_file.save(original_path)

    try:
        audio = AudioSegment.from_file(original_path)
        audio.export(wav_path, format="wav")

        recognizer = sr.Recognizer()

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        transcript = recognizer.recognize_google(audio_data)

        feedback = ask_gpt(f"""
        Analyze this spoken interview response.

        Give:
        1. Confidence score
        2. Clarity feedback
        3. Missing points
        4. Better answer

        Answer:
        {transcript}
        """)

        return jsonify({
            "transcript": transcript,
            "feedback": feedback
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)