from flask import Flask, render_template, request, jsonify, session
from groq import Groq
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import urllib.parse
import urllib.request
import json

app = Flask(__name__)
app.secret_key = "unichatbot2024"

def init_db():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  role TEXT,
                  message TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    if not name or not email or not password:
        return jsonify({"error": "All fields required"}), 400
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        hashed = generate_password_hash(password)
        c.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        session["user_id"] = user_id
        session["user_name"] = name
        session["user_email"] = email
        return jsonify({"status": "ok", "name": name, "email": email})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("SELECT id, name, password FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_email"] = email
            return jsonify({"status": "ok", "name": user[1], "email": email})
        return jsonify({"error": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/auto-login", methods=["POST"])
def auto_login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("SELECT id, name, password FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_email"] = email
            return jsonify({"status": "ok", "name": user[1], "email": email})
        return jsonify({"error": "Auto login failed"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "ok"})

@app.route("/set-key", methods=["POST"])
def set_key():
    data = request.get_json()
    session["api_key"] = data.get("api_key")
    return jsonify({"status": "ok"})

@app.route("/chat", methods=["POST"])
def chat():
    api_key = session.get("api_key")
    user_id = session.get("user_id")
    if not api_key:
        return jsonify({"error": "No API key set"}), 401
    data = request.get_json()
    user_message = data.get("message")
    history = data.get("history", [])
    try:
        client = Groq(api_key=api_key)
        messages = [{"role": "system", "content": """You are UniAssist, a helpful AI assistant for university students worldwide. You help students from ANY university around the world including LPU, Chandigarh University, Delhi University, IITs, NITs, Harvard, MIT, Oxford, Cambridge, and all other universities globally.

You assist with:
- Admissions, eligibility and application process for any university
- Course registration, syllabus and academic schedules
- Scholarships, financial aid and fee structure
- Hostel, accommodation and campus facilities
- Exam schedules, results and study tips
- Library, labs and campus resources
- Student clubs, events and extracurricular activities
- Career services, internships and placements
- Campus maps, transport and directions
- Faculty contacts and department information
- Visa and international student guidance
- Mental health and student wellbeing

Always be friendly, helpful and concise. If you don't know specific details about a university, guide the student to check the official university website or contact the relevant department."""}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, max_tokens=1000)
        reply = response.choices[0].message.content
        if user_id:
            conn = sqlite3.connect('chat_history.db')
            c = conn.cursor()
            c.execute("INSERT INTO chats (user_id, role, message) VALUES (?, ?, ?)", (user_id, "user", user_message))
            c.execute("INSERT INTO chats (user_id, role, message) VALUES (?, ?, ?)", (user_id, "assistant", reply))
            conn.commit()
            conn.close()
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear-history", methods=["POST"])
def clear_history():
    user_id = session.get("user_id")
    if user_id:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("DELETE FROM chats WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})

@app.route("/university-image", methods=["POST"])
def university_image():
    data = request.get_json()
    query = data.get("query", "")
    try:
        search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
        req = urllib.request.Request(search_url, headers={"User-Agent": "UniAssist/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            wiki_data = json.loads(response.read().decode())
            image = wiki_data.get("thumbnail", {}).get("source", None)
            description = wiki_data.get("extract", "")[:400]
            title = wiki_data.get("title", query)
            url = wiki_data.get("content_urls", {}).get("desktop", {}).get("page", "")
            return jsonify({"image": image, "description": description, "title": title, "url": url})
    except:
        return jsonify({"image": None, "description": "", "title": query, "url": ""})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")