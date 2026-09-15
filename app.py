from pathlib import Path
import json
import hmac
import os
import sqlite3
import time
from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).parent
DATABASE = BASE_DIR / "quiz.db"
QUIZ_DURATION_SECONDS = 10 * 60
QUIZ_NAME = "General Knowledge"
app = Flask(__name__, template_folder=BASE_DIR, static_folder=BASE_DIR, static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "development-only-change-this-secret")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "baniyasaroj271@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "9840224481")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    connection.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_name TEXT NOT NULL DEFAULT 'General Knowledge',
            question_text TEXT NOT NULL,
            options_json TEXT NOT NULL,
            correct_option INTEGER NOT NULL
        )
    """)
    question_columns = {row[1] for row in connection.execute("PRAGMA table_info(questions)").fetchall()}
    if "quiz_name" not in question_columns:
        connection.execute("ALTER TABLE questions ADD COLUMN quiz_name TEXT NOT NULL DEFAULT 'General Knowledge'")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            answers_json TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT 'Guest',
            quiz_name TEXT NOT NULL DEFAULT 'General Knowledge',
            completion_seconds INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(attempts)").fetchall()}
    if "username" not in columns:
        connection.execute("ALTER TABLE attempts ADD COLUMN username TEXT NOT NULL DEFAULT 'Guest'")
    if "quiz_name" not in columns:
        connection.execute("ALTER TABLE attempts ADD COLUMN quiz_name TEXT NOT NULL DEFAULT 'General Knowledge'")
    if "completion_seconds" not in columns:
        connection.execute("ALTER TABLE attempts ADD COLUMN completion_seconds INTEGER NOT NULL DEFAULT 0")

    if connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0:
        questions = [
            ("Which planet is known as the Red Planet?", ["Earth", "Mars", "Jupiter", "Venus"], 1),
            ("What is the capital city of Japan?", ["Kyoto", "Seoul", "Tokyo", "Bangkok"], 2),
            ("Which language runs in a web browser?", ["Python", "Java", "C++", "JavaScript"], 3),
            ("How many sides does a hexagon have?", ["Five", "Six", "Seven", "Eight"], 1),
            ("What is the largest ocean on Earth?", ["Atlantic Ocean", "Indian Ocean", "Arctic Ocean", "Pacific Ocean"], 3),
        ]
        connection.executemany(
            "INSERT INTO questions (question_text, options_json, correct_option) VALUES (?, ?, ?)",
            [(text, json.dumps(options), correct) for text, options, correct in questions],
        )
    connection.commit()
    connection.close()


@app.get("/")
def home():
    return render_template("index.html")


def admin_required(view):
    @wraps(view)
    def protected_view(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return protected_view


def password_is_valid(password):
    if ADMIN_PASSWORD_HASH:
        from werkzeug.security import check_password_hash
        return check_password_hash(ADMIN_PASSWORD_HASH, password)
    return hmac.compare_digest(password, ADMIN_PASSWORD)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if hmac.compare_digest(username, ADMIN_USERNAME) and password_is_valid(password):
            session["is_admin"] = True
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("Invalid admin username or password.", "error")
    return render_template("admin_login.html")


@app.get("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


def question_from_form(form):
    category = form.get("quiz_name", "").strip()
    question_text = form.get("question_text", "").strip()
    options = [form.get(f"option_{letter}", "").strip() for letter in "abcd"]
    correct_answer = form.get("correct_answer", "")
    if not category or not question_text or not all(options) or correct_answer not in {"0", "1", "2", "3"}:
        return None
    return category[:80], question_text[:500], options, int(correct_answer)


@app.route("/admin", methods=["GET"])
@admin_required
def admin_dashboard():
    connection = get_connection()
    rows = connection.execute("SELECT id, quiz_name, question_text, options_json, correct_option FROM questions ORDER BY id DESC").fetchall()
    connection.close()
    questions_for_view = [{
        "id": row["id"],
        "quiz_name": row["quiz_name"],
        "question_text": row["question_text"],
        "options": json.loads(row["options_json"]),
        "correct_option": row["correct_option"],
    } for row in rows]
    return render_template("admin_dashboard.html", questions=questions_for_view, editing=None)


@app.post("/admin/questions/add")
@admin_required
def add_question():
    question = question_from_form(request.form)
    if question is None:
        flash("Complete every field and choose a correct answer.", "error")
        return redirect(url_for("admin_dashboard"))
    category, question_text, options, correct_option = question
    connection = get_connection()
    connection.execute("INSERT INTO questions (quiz_name, question_text, options_json, correct_option) VALUES (?, ?, ?, ?)", (category, question_text, json.dumps(options), correct_option))
    connection.commit()
    connection.close()
    flash("Question added successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/questions/<int:question_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_question(question_id):
    connection = get_connection()
    row = connection.execute("SELECT id, quiz_name, question_text, options_json, correct_option FROM questions WHERE id = ?", (question_id,)).fetchone()
    if row is None:
        connection.close()
        return "Question not found", 404
    if request.method == "POST":
        question = question_from_form(request.form)
        if question is None:
            connection.close()
            flash("Complete every field and choose a correct answer.", "error")
            return redirect(url_for("edit_question", question_id=question_id))
        category, question_text, options, correct_option = question
        connection.execute("UPDATE questions SET quiz_name = ?, question_text = ?, options_json = ?, correct_option = ? WHERE id = ?", (category, question_text, json.dumps(options), correct_option, question_id))
        connection.commit()
        connection.close()
        flash("Question updated successfully.", "success")
        return redirect(url_for("admin_dashboard"))
    editing = {
        "id": row["id"],
        "quiz_name": row["quiz_name"],
        "question_text": row["question_text"],
        "options": json.loads(row["options_json"]),
        "correct_option": row["correct_option"],
    }
    connection.close()
    return render_template("admin_dashboard.html", questions=[], editing=editing)


@app.post("/admin/questions/<int:question_id>/delete")
@admin_required
def delete_question(question_id):
    connection = get_connection()
    connection.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    connection.commit()
    connection.close()
    flash("Question deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/api/start")
def start_quiz():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()[:30]
    if not username:
        return jsonify({"error": "Please enter a username."}), 400
    session["username"] = username
    return jsonify({"ok": True, "username": username})


@app.get("/api/questions")
def questions():
    if "quiz_started_at" not in session:
        session["quiz_started_at"] = time.time()
    started_at = session["quiz_started_at"]
    remaining_seconds = max(0, QUIZ_DURATION_SECONDS - int(time.time() - started_at))
    connection = get_connection()
    rows = connection.execute("SELECT id, question_text, options_json FROM questions ORDER BY id").fetchall()
    connection.close()
    return jsonify({
        "questions": [
            {
                "id": row["id"],
                "text": row["question_text"],
                "options": [{"id": index, "text": text} for index, text in enumerate(json.loads(row["options_json"]))],
            }
            for row in rows
        ],
        "remaining_seconds": remaining_seconds,
    })


@app.post("/api/submit")
def submit():
    payload = request.get_json(silent=True) or {}
    submitted_answers = payload.get("answers", {})
    started_at = session.get("quiz_started_at")
    if started_at is None:
        return jsonify({"error": "Your quiz session has expired. Please start a new quiz."}), 400
    timed_out = time.time() - started_at >= QUIZ_DURATION_SECONDS
    username = session.get("username", "Guest")
    completion_seconds = min(QUIZ_DURATION_SECONDS, max(0, round(time.time() - started_at)))
    connection = get_connection()
    rows = connection.execute("SELECT id, options_json, correct_option FROM questions ORDER BY id").fetchall()
    score = 0
    unanswered = 0
    details = []
    for row in rows:
        options = json.loads(row["options_json"])
        answer = submitted_answers.get(str(row["id"]))
        valid_options = range(len(options))
        valid_answer = answer is not None and str(answer).isdigit() and int(answer) in valid_options
        is_correct = valid_answer and int(answer) == row["correct_option"]
        if is_correct:
            score += 1
        if not valid_answer:
            unanswered += 1
        details.append({
            "question": connection.execute("SELECT question_text FROM questions WHERE id = ?", (row["id"],)).fetchone()[0],
            "selected_answer": options[int(answer)] if valid_answer else None,
            "correct_answer": options[row["correct_option"]],
            "is_correct": is_correct,
        })
    incorrect = len(rows) - score - unanswered
    percentage = round((score / len(rows)) * 100) if rows else 0
    connection.execute(
        "INSERT INTO attempts (answers_json, score, total, username, quiz_name, completion_seconds) VALUES (?, ?, ?, ?, ?, ?)",
        (json.dumps(submitted_answers), score, len(rows), username, QUIZ_NAME, completion_seconds),
    )
    connection.commit()
    connection.close()
    session["quiz_submitted"] = True
    return jsonify({
        "score": score,
        "total": len(rows),
        "correct": score,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "percentage": percentage,
        "timed_out": timed_out,
        "details": details,
    })


@app.get("/leaderboard")
def leaderboard_page():
    return render_template("leaderboard.html")


@app.get("/api/leaderboard")
def leaderboard_data():
    quiz_name = request.args.get("quiz", QUIZ_NAME)
    connection = get_connection()
    rows = connection.execute("""
        SELECT username, score, total, completion_seconds,
               RANK() OVER (ORDER BY score DESC, completion_seconds ASC, created_at ASC) AS rank
        FROM attempts
        WHERE quiz_name = ?
        ORDER BY score DESC, completion_seconds ASC, created_at ASC
        LIMIT 10
    """, (quiz_name,)).fetchall()
    current_username = session.get("username")
    current_rank = None
    if current_username:
        current = connection.execute("""
            SELECT score, completion_seconds, created_at
            FROM attempts
            WHERE quiz_name = ? AND username = ?
            ORDER BY created_at DESC LIMIT 1
        """, (quiz_name, current_username)).fetchone()
        if current:
            current_rank = connection.execute("""
                SELECT COUNT(*) + 1 FROM attempts
                WHERE quiz_name = ? AND (
                    score > ? OR
                    (score = ? AND completion_seconds < ?) OR
                    (score = ? AND completion_seconds = ? AND created_at < ?)
                )
            """, (quiz_name, current["score"], current["score"], current["completion_seconds"], current["score"], current["completion_seconds"], current["created_at"])).fetchone()[0]
    connection.close()
    return jsonify({
        "quiz": quiz_name,
        "current_username": current_username,
        "current_rank": current_rank,
        "entries": [
            {
                "rank": row["rank"],
                "username": row["username"],
                "score": row["score"],
                "percentage": round((row["score"] / row["total"]) * 100) if row["total"] else 0,
                "completion_seconds": row["completion_seconds"],
            }
            for row in rows
        ],
    })


@app.post("/api/restart")
def restart():
    session.pop("quiz_started_at", None)
    session.pop("quiz_submitted", None)
    return jsonify({"ok": True})


initialize_database()


if __name__ == "__main__":
    app.run(debug=True)