from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, datetime

app = Flask(__name__)

app.secret_key = "quicknotes-secret-key-2025"
UPLOAD_FOLDER  = "uploads"
PHOTO_FOLDER   = "uploads/photos"
ALLOWED_EXT    = {"pdf", "doc", "docx", "ppt", "pptx"}
ALLOWED_PHOTOS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PHOTO_FOLDER, exist_ok=True)

ADMIN_EMAIL    = "admin@quicknotes.com"
ADMIN_PASSWORD = "admin123"

def get_db():
    db = sqlite3.connect("quicknotes.db")
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT NOT NULL,
            subject   TEXT NOT NULL,
            level     TEXT NOT NULL,
            filename  TEXT NOT NULL,
            filetype  TEXT NOT NULL,
            desc      TEXT,
            downloads INTEGER DEFAULT 0,
            created   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            title    TEXT NOT NULL,
            subject  TEXT NOT NULL,
            level    TEXT NOT NULL,
            yt_url   TEXT NOT NULL,
            duration TEXT,
            desc     TEXT,
            views    INTEGER DEFAULT 0,
            created  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT,
            subject  TEXT NOT NULL,
            message  TEXT NOT NULL,
            photo    TEXT,
            status   TEXT DEFAULT 'pending',
            user_id  INTEGER,
            created  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            password   TEXT NOT NULL,
            created    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()

init_db()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTOS

def is_admin():
    return session.get("admin") == True

def current_user():
    return session.get("user_id")

# ─── HOME ─────────────────────────────────────────────────
@app.route("/")
def home():
    db = get_db()
    notes       = db.execute("SELECT * FROM notes  ORDER BY created DESC LIMIT 6").fetchall()
    videos      = db.execute("SELECT * FROM videos ORDER BY created DESC LIMIT 6").fetchall()
    note_count  = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    video_count = db.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    db.close()
    return render_template("home.html", notes=notes, videos=videos,
                           note_count=note_count, video_count=video_count)

# ─── NOTES ────────────────────────────────────────────────
@app.route("/notes")
def notes():
    db      = get_db()
    search  = request.args.get("search", "")
    subject = request.args.get("subject", "all")
    level   = request.args.get("level", "all")
    query   = "SELECT * FROM notes WHERE 1=1"
    params  = []
    if search:
        query += " AND (title LIKE ? OR desc LIKE ? OR subject LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if subject != "all":
        query += " AND subject = ?"
        params.append(subject)
    if level != "all":
        query += " AND level = ?"
        params.append(level)
    query   += " ORDER BY created DESC"
    items    = db.execute(query, params).fetchall()
    subjects = db.execute("SELECT DISTINCT subject FROM notes").fetchall()
    db.close()
    return render_template("notes.html", notes=items, subjects=subjects,
                           search=search, sel_subj=subject, sel_level=level)

# ─── VIDEOS ───────────────────────────────────────────────
@app.route("/videos")
def videos():
    db      = get_db()
    search  = request.args.get("search", "")
    subject = request.args.get("subject", "all")
    query   = "SELECT * FROM videos WHERE 1=1"
    params  = []
    if search:
        query += " AND (title LIKE ? OR desc LIKE ? OR subject LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if subject != "all":
        query += " AND subject = ?"
        params.append(subject)
    query   += " ORDER BY created DESC"
    items    = db.execute(query, params).fetchall()
    subjects = db.execute("SELECT DISTINCT subject FROM videos").fetchall()
    db.close()
    return render_template("videos.html", videos=items, subjects=subjects,
                           search=search, sel_subj=subject)

# ─── DOWNLOAD ─────────────────────────────────────────────
@app.route("/download/<int:note_id>")
def download(note_id):
    db   = get_db()
    note = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not note:
        db.close()
        return "File not found", 404
    db.execute("UPDATE notes SET downloads = downloads + 1 WHERE id = ?", (note_id,))
    db.commit()
    db.close()
    return send_from_directory(app.config["UPLOAD_FOLDER"], note["filename"], as_attachment=True)

# ─── STUDENT SIGNUP ───────────────────────────────────────
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user():
        return redirect(url_for("home"))
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        if not name or not email or not password:
            return render_template("signup.html", error="Please fill in all fields.")
        if password != confirm:
            return render_template("signup.html", error="Passwords do not match.")
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters.")
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            db.close()
            return render_template("signup.html", error="Email already registered. Please login.")
        hashed = generate_password_hash(password)
        db.execute("INSERT INTO users (name, email, password) VALUES (?,?,?)", (name, email, hashed))
        db.commit()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()
        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        flash(f"Welcome {name}! Account created successfully.", "success")
        return redirect(url_for("home"))
    return render_template("signup.html", error=None)

# ─── STUDENT LOGIN ────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("home"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db   = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()
        if not user or not check_password_hash(user["password"], password):
            return render_template("login.html", error="Invalid email or password.")
        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("home"))
    return render_template("login.html", error=None)

# ─── STUDENT LOGOUT ───────────────────────────────────────
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))

# ─── REQUEST NOTES ────────────────────────────────────────
@app.route("/request-notes", methods=["GET", "POST"])
def request_notes():
    if request.method == "POST":
        name    = request.form.get("name", "Anonymous").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        photo_filename = None
        if not subject or not message:
            flash("Please fill in subject and message.", "error")
            return redirect(url_for("request_notes"))
        photo = request.files.get("photo")
        if photo and photo.filename != "" and allowed_photo(photo.filename):
            photo_filename = secure_filename(str(int(datetime.datetime.now().timestamp())) + "_" + photo.filename)
            photo.save(os.path.join(PHOTO_FOLDER, photo_filename))
        db = get_db()
        db.execute("INSERT INTO requests (name, subject, message, photo, user_id) VALUES (?,?,?,?,?)",
                   (name or "Anonymous", subject, message, photo_filename, current_user()))
        db.commit()
        db.close()
        flash("Your request has been sent! We will make those notes soon.", "success")
        return redirect(url_for("request_notes"))
    db   = get_db()
    reqs = db.execute("SELECT * FROM requests ORDER BY created DESC").fetchall()
    db.close()
    return render_template("request_notes.html", requests=reqs)

# ─── SERVE PHOTOS ─────────────────────────────────────────
@app.route("/uploads/photos/<filename>")
def uploaded_photo(filename):
    return send_from_directory(PHOTO_FOLDER, filename)

# ─── ADMIN LOGIN ──────────────────────────────────────────
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        email    = request.form.get("email")
        password = request.form.get("password")
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        return render_template("admin_login.html", error="Invalid email or password.")
    if is_admin():
        return redirect(url_for("admin_panel"))
    return render_template("admin_login.html", error=None)

# ─── ADMIN PANEL ──────────────────────────────────────────
@app.route("/admin/panel")
def admin_panel():
    if not is_admin():
        return redirect(url_for("admin"))
    db       = get_db()
    notes    = db.execute("SELECT * FROM notes    ORDER BY created DESC").fetchall()
    videos   = db.execute("SELECT * FROM videos   ORDER BY created DESC").fetchall()
    requests = db.execute("SELECT * FROM requests ORDER BY created DESC").fetchall()
    users    = db.execute("SELECT * FROM users    ORDER BY created DESC").fetchall()
    pending  = db.execute("SELECT COUNT(*) FROM requests WHERE status='pending'").fetchone()[0]
    db.close()
    return render_template("admin_panel.html", notes=notes, videos=videos,
                           requests=requests, pending=pending, users=users)

@app.route("/admin/upload-note", methods=["POST"])
def upload_note():
    if not is_admin():
        return redirect(url_for("admin"))
    title   = request.form.get("title", "").strip()
    subject = request.form.get("subject", "")
    level   = request.form.get("level", "")
    desc    = request.form.get("desc", "").strip()
    file    = request.files.get("file")
    if not title or not file or file.filename == "":
        flash("Please fill in all fields and select a file.", "error")
        return redirect(url_for("admin_panel"))
    if not allowed_file(file.filename):
        flash("File type not allowed. Use PDF, DOC, DOCX, PPT, PPTX.", "error")
        return redirect(url_for("admin_panel"))
    filename = secure_filename(str(int(datetime.datetime.now().timestamp())) + "_" + file.filename)
    filetype = filename.rsplit(".", 1)[1].lower()
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    db = get_db()
    db.execute("INSERT INTO notes (title, subject, level, filename, filetype, desc) VALUES (?,?,?,?,?,?)",
               (title, subject, level, filename, filetype, desc))
    db.commit()
    db.close()
    flash(f'"{title}" uploaded successfully!', "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/upload-video", methods=["POST"])
def upload_video():
    if not is_admin():
        return redirect(url_for("admin"))
    title    = request.form.get("title", "").strip()
    subject  = request.form.get("subject", "")
    level    = request.form.get("level", "")
    yt_url   = request.form.get("yt_url", "").strip()
    duration = request.form.get("duration", "").strip()
    desc     = request.form.get("desc", "").strip()
    if not title or not yt_url:
        flash("Please fill in all fields.", "error")
        return redirect(url_for("admin_panel"))
    db = get_db()
    db.execute("INSERT INTO videos (title, subject, level, yt_url, duration, desc) VALUES (?,?,?,?,?,?)",
               (title, subject, level, yt_url, duration, desc))
    db.commit()
    db.close()
    flash(f'Video "{title}" added successfully!', "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete-note/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    if not is_admin():
        return redirect(url_for("admin"))
    db   = get_db()
    note = db.execute("SELECT filename FROM notes WHERE id = ?", (note_id,)).fetchone()
    if note:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], note["filename"]))
        except:
            pass
        db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        db.commit()
    db.close()
    flash("Note deleted.", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete-video/<int:vid_id>", methods=["POST"])
def delete_video(vid_id):
    if not is_admin():
        return redirect(url_for("admin"))
    db = get_db()
    db.execute("DELETE FROM videos WHERE id = ?", (vid_id,))
    db.commit()
    db.close()
    flash("Video deleted.", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete-request/<int:req_id>", methods=["POST"])
def delete_request(req_id):
    if not is_admin():
        return redirect(url_for("admin"))
    db = get_db()
    db.execute("DELETE FROM requests WHERE id = ?", (req_id,))
    db.commit()
    db.close()
    flash("Request deleted.", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/mark-done/<int:req_id>", methods=["POST"])
def mark_done(req_id):
    if not is_admin():
        return redirect(url_for("admin"))
    db = get_db()
    db.execute("UPDATE requests SET status = 'done' WHERE id = ?", (req_id,))
    db.commit()
    db.close()
    flash("Marked as done!", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not is_admin():
        return redirect(url_for("admin"))
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    db.close()
    flash("User deleted.", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)

# ─── RATINGS ──────────────────────────────────────────────
def init_extra_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            user_id INTEGER,
            stars   INTEGER NOT NULL,
            created TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            user_id INTEGER,
            name    TEXT,
            comment TEXT NOT NULL,
            created TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(note_id, user_id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            email   TEXT NOT NULL,
            message TEXT NOT NULL,
            created TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()

init_extra_db()

@app.route("/note/<int:note_id>")
def note_detail(note_id):
    db   = get_db()
    note = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not note:
        db.close()
        return "Note not found", 404
    comments = db.execute("SELECT * FROM comments WHERE note_id = ? ORDER BY created DESC", (note_id,)).fetchall()
    ratings  = db.execute("SELECT AVG(stars) as avg, COUNT(*) as cnt FROM ratings WHERE note_id = ?", (note_id,)).fetchone()
    user_rating = None
    bookmarked  = False
    if current_user():
        ur = db.execute("SELECT stars FROM ratings WHERE note_id=? AND user_id=?", (note_id, current_user())).fetchone()
        user_rating = ur["stars"] if ur else None
        bm = db.execute("SELECT id FROM bookmarks WHERE note_id=? AND user_id=?", (note_id, current_user())).fetchone()
        bookmarked = bm is not None
    db.close()
    avg_stars = round(ratings["avg"] or 0, 1)
    return render_template("note_detail.html", note=note, comments=comments,
                           avg_stars=avg_stars, rating_count=ratings["cnt"],
                           user_rating=user_rating, bookmarked=bookmarked)

@app.route("/rate-note/<int:note_id>", methods=["POST"])
def rate_note(note_id):
    if not current_user():
        flash("Please login to rate notes.", "error")
        return redirect(url_for("note_detail", note_id=note_id))
    stars = int(request.form.get("stars", 5))
    db    = get_db()
    existing = db.execute("SELECT id FROM ratings WHERE note_id=? AND user_id=?", (note_id, current_user())).fetchone()
    if existing:
        db.execute("UPDATE ratings SET stars=? WHERE note_id=? AND user_id=?", (stars, note_id, current_user()))
    else:
        db.execute("INSERT INTO ratings (note_id, user_id, stars) VALUES (?,?,?)", (note_id, current_user(), stars))
    db.commit()
    db.close()
    flash(f"You rated this {stars} stars!", "success")
    return redirect(url_for("note_detail", note_id=note_id))

@app.route("/comment-note/<int:note_id>", methods=["POST"])
def comment_note(note_id):
    name    = request.form.get("name", "Anonymous").strip()
    comment = request.form.get("comment", "").strip()
    if not comment:
        flash("Please write a comment.", "error")
        return redirect(url_for("note_detail", note_id=note_id))
    if current_user():
        db   = get_db()
        user = db.execute("SELECT name FROM users WHERE id=?", (current_user(),)).fetchone()
        name = user["name"] if user else name
        db.close()
    db = get_db()
    db.execute("INSERT INTO comments (note_id, user_id, name, comment) VALUES (?,?,?,?)",
               (note_id, current_user(), name or "Anonymous", comment))
    db.commit()
    db.close()
    flash("Comment added!", "success")
    return redirect(url_for("note_detail", note_id=note_id))

@app.route("/bookmark/<int:note_id>", methods=["POST"])
def toggle_bookmark(note_id):
    if not current_user():
        flash("Please login to bookmark notes.", "error")
        return redirect(url_for("note_detail", note_id=note_id))
    db = get_db()
    existing = db.execute("SELECT id FROM bookmarks WHERE note_id=? AND user_id=?", (note_id, current_user())).fetchone()
    if existing:
        db.execute("DELETE FROM bookmarks WHERE note_id=? AND user_id=?", (note_id, current_user()))
        flash("Bookmark removed.", "success")
    else:
        db.execute("INSERT INTO bookmarks (note_id, user_id) VALUES (?,?)", (note_id, current_user()))
        flash("Note bookmarked!", "success")
    db.commit()
    db.close()
    return redirect(url_for("note_detail", note_id=note_id))

@app.route("/my-bookmarks")
def my_bookmarks():
    if not current_user():
        flash("Please login to see your bookmarks.", "error")
        return redirect(url_for("login"))
    db    = get_db()
    notes = db.execute("""
        SELECT notes.* FROM notes
        JOIN bookmarks ON notes.id = bookmarks.note_id
        WHERE bookmarks.user_id = ?
        ORDER BY bookmarks.created DESC
    """, (current_user(),)).fetchall()
    db.close()
    return render_template("bookmarks.html", notes=notes)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name    = request.form.get("name", "").strip()
        email   = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        if not name or not email or not message:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("contact"))
        db = get_db()
        db.execute("INSERT INTO contacts (name, email, message) VALUES (?,?,?)", (name, email, message))
        db.commit()
        db.close()
        flash("Message sent! We will reply soon.", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/faq")
def faq():
    return render_template("faq.html")

# ─── AI STUDY ASSISTANT ───────────────────────────────────
import json
try:
    import urllib.request
except:
    pass

@app.route("/ai-assistant")
def ai_assistant():
    return render_template("ai_assistant.html")

@app.route("/api/ask-ai", methods=["POST"])
def ask_ai():
    try:
        data    = request.get_json()
        message = data.get("message", "").strip()
        history = data.get("history", [])
        if not message:
            return jsonify({"error": "Please type a question."}), 400

        # Build messages for Claude API
        messages = []
        for h in history[-10:]:  # last 10 messages for context
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        # Call Claude API
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return jsonify({"reply": "AI Assistant is not configured yet. Please add your API key in Render settings."}), 200

        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1024,
            "system": "You are a helpful study assistant for students on QuickNotes platform. Help students understand subjects like Maths, Physics, Chemistry, Biology, History, English, Computer Science, Economics, Geography, Political Science, B.Sc Nursing and more. Explain concepts simply and clearly. Give examples. Be encouraging and supportive. Keep answers concise but complete. If a student asks something unrelated to studying, politely redirect them to study topics.",
            "messages": messages
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            reply  = result["content"][0]["text"]
            return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"Sorry, I could not process your question. Please try again. Error: {str(e)}"}), 200
