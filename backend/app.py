from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pdfplumber
import os
from docx import Document
from pydub import AudioSegment
import speech_recognition as sr

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SKILLS = [
    "python", "java", "javascript", "react", "node.js", "flask",
    "sql", "mysql", "mongodb", "html", "css",
    "machine learning", "deep learning", "ai", "nlp",
    "data analysis", "pandas", "numpy", "tensorflow",
    "pytorch", "aws", "docker", "git", "rest api",
    "api", "fastapi", "django", "tableau", "power bi",
    "excel", "communication", "problem solving"
]


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_text_from_docx(file_path):
    document = Document(file_path)
    text = ""
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"
    return text


def extract_resume_text(file_path, filename):
    filename = filename.lower()

    if filename.endswith(".pdf"):
        return extract_text_from_pdf(file_path)

    if filename.endswith(".docx"):
        return extract_text_from_docx(file_path)

    raise Exception("Unsupported file format. Please upload PDF or DOCX only.")


def find_skills(text):
    text = text.lower()
    found = []

    for skill in SKILLS:
        if skill in text:
            found.append(skill)

    return found


def extract_section(text, possible_headers):
    lines = text.split("\n")
    section_lines = []
    capture = False

    all_headers = [
        "education", "experience", "work experience", "professional experience",
        "projects", "academic projects", "certifications", "certification",
        "skills", "technical skills", "summary", "objective", "achievements"
    ]

    for line in lines:
        clean_line = line.strip()
        lower_line = clean_line.lower()

        if any(header == lower_line for header in possible_headers):
            capture = True
            continue

        if capture and any(header == lower_line for header in all_headers):
            break

        if capture and clean_line:
            section_lines.append(clean_line)

    if len(section_lines) == 0:
        return ["Not found"]

    return section_lines[:10]


def extract_resume_sections(text):
    return {
        "education": extract_section(text, ["education"]),
        "experience": extract_section(text, ["experience", "work experience", "professional experience"]),
        "projects": extract_section(text, ["projects", "academic projects"]),
        "certifications": extract_section(text, ["certifications", "certification"])
    }


def generate_resume_suggestions(match_score, missing_skills):
    suggestions = []

    if match_score < 50:
        suggestions.append("Your resume needs stronger alignment with this job description.")
        suggestions.append("Add more job-specific keywords, tools, and measurable project details.")
    elif match_score < 75:
        suggestions.append("Your resume is partially aligned with this role.")
        suggestions.append("Add missing skills and improve your project bullet points.")
    else:
        suggestions.append("Your resume is strongly aligned with this role.")
        suggestions.append("You can still improve it by adding measurable achievements and role-specific keywords.")

    for skill in missing_skills:
        suggestions.append(f"Add experience, project work, or certification related to {skill}.")

    return suggestions


def generate_resume_bullets(matched_skills, missing_skills):
    bullets = []

    if matched_skills:
        bullets.append(
            "Developed projects using " + ", ".join(matched_skills[:5]) +
            " to solve real-world software and AI problems."
        )

        bullets.append(
            "Applied " + ", ".join(matched_skills[:5]) +
            " to build scalable, user-focused applications with measurable functionality."
        )

    if missing_skills:
        bullets.append(
            "Currently improving skills in " + ", ".join(missing_skills[:5]) +
            " to better align with industry job requirements."
        )

    bullets.append(
        "Built an AI-powered resume and interview assistant that analyzes resumes, compares job descriptions, identifies missing skills, and generates personalized interview preparation questions."
    )

    bullets.append(
        "Implemented a Flask-based backend to process PDF/DOCX resumes, extract text, calculate ATS-style match scores, and return structured career recommendations."
    )

    return bullets


def generate_improved_summary(matched_skills, missing_skills):
    if matched_skills:
        skills_text = ", ".join(matched_skills[:6])
    else:
        skills_text = "software development, problem solving, and technical project implementation"

    summary = (
        "Motivated Computer Science graduate student with hands-on experience in "
        + skills_text +
        ". Skilled in building practical, user-focused applications, analyzing requirements, "
        "and developing solutions that connect technical implementation with real-world business needs."
    )

    if missing_skills:
        summary += (
            " Currently expanding expertise in "
            + ", ".join(missing_skills[:3]) +
            " to better align with industry role requirements."
        )

    return summary


def generate_better_project_descriptions(matched_skills):
    skills_text = ", ".join(matched_skills[:5]) if matched_skills else "Python, Flask, HTML, CSS, and API development"

    return [
        "Developed an AI Resume + Interview Assistant using "
        + skills_text +
        " to analyze resumes, compare job descriptions, identify missing skills, and generate personalized interview preparation content.",

        "Implemented resume parsing for PDF and DOCX files, extracted key resume sections, and generated structured outputs including ATS score, strong keywords, weak sections, and improvement suggestions.",

        "Designed a professional web interface that allows users to upload resumes, paste job descriptions, review analysis results, record interview answers, and download a complete resume analysis report."
    ]


def generate_role_keywords(jd_skills, missing_skills):
    keywords = []

    for skill in jd_skills:
        keywords.append(skill)

    for skill in missing_skills:
        if skill not in keywords:
            keywords.append(skill)

    extra_keywords = [
        "team collaboration",
        "problem solving",
        "software development",
        "project implementation",
        "debugging",
        "technical documentation"
    ]

    for word in extra_keywords:
        if word not in keywords:
            keywords.append(word)

    return keywords[:15]


def generate_interview_questions_grouped(matched_skills):
    hr_questions = [
        "Tell me about yourself.",
        "Why are you interested in this role?",
        "What are your strengths and weaknesses?",
        "Why should we hire you?"
    ]

    technical_questions = []

    for skill in matched_skills:
        if skill == "python":
            technical_questions += [
                "Explain list vs tuple in Python.",
                "What is a decorator in Python?"
            ]

        elif skill == "react":
            technical_questions += [
                "What are React hooks?",
                "Explain virtual DOM."
            ]

        elif skill == "sql":
            technical_questions += [
                "What is JOIN in SQL?",
                "Difference between DELETE and TRUNCATE?"
            ]

        elif skill == "machine learning":
            technical_questions += [
                "Explain overfitting in machine learning.",
                "Difference between supervised and unsupervised learning?"
            ]

        elif skill == "flask":
            technical_questions += [
                "What is Flask?",
                "Explain Flask routing."
            ]

        elif skill == "javascript":
            technical_questions += [
                "What is closure in JavaScript?",
                "Difference between var, let, and const?"
            ]

        elif skill == "mysql":
            technical_questions += [
                "What is a primary key in MySQL?",
                "Explain normalization in databases."
            ]

        elif skill == "aws":
            technical_questions += [
                "What is EC2 in AWS?",
                "Difference between S3 and RDS?"
            ]

        elif skill == "docker":
            technical_questions += [
                "What is Docker?",
                "Difference between Docker image and container?"
            ]

        elif skill == "git":
            technical_questions += [
                "Difference between git pull and git fetch?",
                "What is a merge conflict?"
            ]

    if len(technical_questions) == 0:
        technical_questions = [
            "Explain one technical project from your resume.",
            "What challenges did you face while building your project?",
            "How did you test and debug your application?"
        ]

    behavioral_questions = [
        "Tell me about a time you solved a difficult technical problem.",
        "Describe a time when you worked in a team.",
        "Tell me about a time you handled pressure or a deadline.",
        "Describe a situation where you had to learn a new technology quickly."
    ]

    return {
        "hr_questions": hr_questions,
        "technical_questions": technical_questions,
        "behavioral_questions": behavioral_questions
    }


def generate_star_answers():
    return [
        {
            "question": "Tell me about a time you solved a difficult technical problem.",
            "answer": {
                "situation": "During a project, I had to build a resume analysis system that could process different resume formats and compare them with job descriptions.",
                "task": "My task was to extract resume text, identify skills, calculate match score, and generate useful feedback for users.",
                "action": "I used Flask for the backend, pdfplumber and python-docx for resume parsing, and created logic to compare resume skills with job-required skills.",
                "result": "The system successfully generated ATS-style match scores, missing skills, improvement suggestions, and interview questions."
            }
        },
        {
            "question": "Describe a time when you learned a new technology quickly.",
            "answer": {
                "situation": "While working on the AI Resume + Interview Assistant, I needed to support both PDF and DOCX resume formats.",
                "task": "I had to learn how to extract text from DOCX files and integrate that feature into the existing backend.",
                "action": "I researched the python-docx library, added DOCX parsing logic, and connected it with the existing resume analysis route.",
                "result": "The application became more flexible because users could upload both PDF and DOCX resumes."
            }
        }
    ]


def generate_mock_feedback(user_answer):
    answer = user_answer.strip()

    if len(answer) == 0:
        return {
            "clarity_score": 0,
            "confidence_score": 0,
            "missing_points": ["Please type or record an answer first."],
            "improved_answer": "No answer provided."
        }

    word_count = len(answer.split())

    clarity_score = min(100, max(40, word_count * 3))
    confidence_score = min(100, max(45, word_count * 2))

    missing_points = []

    if word_count < 30:
        missing_points.append("Your answer is too short. Add more details.")
    if "project" not in answer.lower():
        missing_points.append("Mention a specific project or real example.")
    if "result" not in answer.lower() and "impact" not in answer.lower():
        missing_points.append("Add the result or impact of your work.")
    if "i" not in answer.lower():
        missing_points.append("Use clear ownership by explaining what you personally did.")

    if len(missing_points) == 0:
        missing_points.append("Good answer. You can make it stronger by adding measurable results.")

    improved_answer = (
        "In my project, I worked on solving a real-world problem by analyzing the requirements, "
        "building the solution step by step, and testing the final output. I personally contributed "
        "to the implementation, debugging, and improvement of the system. As a result, the project "
        "became more practical, user-friendly, and aligned with real job requirements."
    )

    return {
        "clarity_score": clarity_score,
        "confidence_score": confidence_score,
        "missing_points": missing_points,
        "improved_answer": improved_answer
    }


@app.route("/analyze-resume", methods=["POST"])
def analyze_resume():
    if "resume" not in request.files:
        return jsonify({"error": "No resume uploaded"}), 400

    if "job_description" not in request.form:
        return jsonify({"error": "No job description provided"}), 400

    resume_file = request.files["resume"]
    job_description = request.form["job_description"]

    if resume_file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not (
        resume_file.filename.lower().endswith(".pdf")
        or resume_file.filename.lower().endswith(".docx")
    ):
        return jsonify({"error": "Please upload a valid PDF or DOCX resume only"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    resume_file.save(file_path)

    try:
        resume_text = extract_resume_text(file_path, resume_file.filename)

        resume_skills = find_skills(resume_text)
        jd_skills = find_skills(job_description)
        resume_sections = extract_resume_sections(resume_text)

        matched_skills = list(set(resume_skills) & set(jd_skills))
        missing_skills = list(set(jd_skills) - set(resume_skills))
        strong_keywords = matched_skills

        weak_sections = []

        if resume_sections["education"] == ["Not found"]:
            weak_sections.append("Education section is missing or not clearly labeled.")

        if resume_sections["experience"] == ["Not found"]:
            weak_sections.append("Experience section is missing or not clearly labeled.")

        if resume_sections["projects"] == ["Not found"]:
            weak_sections.append("Projects section is missing or not clearly labeled.")

        if resume_sections["certifications"] == ["Not found"]:
            weak_sections.append("Certifications section is missing or not clearly labeled.")

        if len(jd_skills) == 0:
            match_score = 0
        else:
            match_score = round((len(matched_skills) / len(jd_skills)) * 100, 2)

        resume_suggestions = generate_resume_suggestions(match_score, missing_skills)
        resume_bullets = generate_resume_bullets(matched_skills, missing_skills)

        improved_summary = generate_improved_summary(matched_skills, missing_skills)
        better_project_descriptions = generate_better_project_descriptions(matched_skills)
        role_keywords = generate_role_keywords(jd_skills, missing_skills)

        interview_data = generate_interview_questions_grouped(matched_skills)
        star_answers = generate_star_answers()

        return jsonify({
            "message": "Resume analyzed successfully",
            "match_score": match_score,
            "resume_skills": resume_skills,
            "job_required_skills": jd_skills,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "strong_keywords": strong_keywords,
            "weak_sections": weak_sections,
            "education": resume_sections["education"],
            "experience": resume_sections["experience"],
            "projects": resume_sections["projects"],
            "certifications": resume_sections["certifications"],
            "resume_suggestions": resume_suggestions,
            "resume_bullets": resume_bullets,
            "improved_summary": improved_summary,
            "better_project_descriptions": better_project_descriptions,
            "role_keywords": role_keywords,
            "hr_questions": interview_data["hr_questions"],
            "technical_questions": interview_data["technical_questions"],
            "behavioral_questions": interview_data["behavioral_questions"],
            "star_answers": star_answers,
            "resume_preview": resume_text[:1000]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/mock-feedback", methods=["POST"])
def mock_feedback():
    data = request.get_json()

    if not data or "answer" not in data:
        return jsonify({"error": "No answer provided"}), 400

    feedback = generate_mock_feedback(data["answer"])
    return jsonify(feedback)


@app.route("/voice-feedback", methods=["POST"])
def voice_feedback():
    if "audio" not in request.files:
        return jsonify({"error": "No audio uploaded"}), 400

    audio_file = request.files["audio"]
    original_audio_path = os.path.join(UPLOAD_FOLDER, audio_file.filename)
    wav_audio_path = os.path.join(UPLOAD_FOLDER, "converted_answer.wav")

    audio_file.save(original_audio_path)

    try:
        audio = AudioSegment.from_file(original_audio_path)
        audio.export(wav_audio_path, format="wav")

        recognizer = sr.Recognizer()

        with sr.AudioFile(wav_audio_path) as source:
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data)

        feedback = generate_mock_feedback(text)
        feedback["transcribed_text"] = text

        return jsonify(feedback)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)