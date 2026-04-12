from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash, jsonify
from werkzeug.utils import secure_filename
import sqlite3, os, datetime

app = Flask(__name__)

app.secret_key = "quicknotes-secret-key-2025"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXT   = {"pdf", "doc", "docx", "ppt", "pptx"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    db.commit()
    db.close()

init_db()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def is_admin():
    return session.get("admin") == True

@app.route("/")
def home():
    db = get_db()
    notes  = db.execute("SELECT * FROM notes  ORDER BY created DESC LIMIT 6").fetchall()
    videos = db.execute("SELECT * FROM videos ORDER BY created DESC LIMIT 6").fetchall()
    note_count  = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    video_count = db.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    db.close()
    return render_template("home.html", notes=notes, videos=videos,
                           note_count=note_count, video_count=video_count)

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
    query  += " ORDER BY created DESC"
    items   = db.execute(query, params).fetchall()
    subjects = db.execute("SELECT DISTINCT subject FROM notes").fetchall()
    db.close()
    return render_template("notes.html", notes=items, subjects=subjects,
                           search=search, sel_subj=subject, sel_level=level)

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

@app.route("/admin/panel")
def admin_panel():
    if not is_admin():
        return redirect(url_for("admin"))
    db     = get_db()
    notes  = db.execute("SELECT * FROM notes  ORDER BY created DESC").fetchall()
    videos = db.execute("SELECT * FROM videos ORDER BY created DESC").fetchall()
    db.close()
    return render_template("admin_panel.html", notes=notes, videos=videos)

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

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)

# ─── REQUESTS TABLE ───────────────────────────────────────
def init_requests_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status  TEXT DEFAULT 'pending',
            created TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()

init_requests_db()

@app.route("/request-notes", methods=["GET", "POST"])
def request_notes():
    if request.method == "POST":
        name    = request.form.get("name", "Anonymous").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        if not subject or not message:
            flash("Please fill in subject and message.", "error")
            return redirect(url_for("request_notes"))
        db = get_db()
        db.execute("INSERT INTO requests (name, subject, message) VALUES (?,?,?)",
                   (name or "Anonymous", subject, message))
        db.commit()
        db.close()
        flash("Your request has been sent! We will make those notes soon.", "success")
        return redirect(url_for("request_notes"))
    db = get_db()
    reqs = db.execute("SELECT * FROM requests ORDER BY created DESC").fetchall()
    db.close()
    return render_template("request_notes.html", requests=reqs)

@app.route("/admin/requests")
def admin_requests():
    if not is_admin():
        return redirect(url_for("admin"))
    db   = get_db()
    reqs = db.execute("SELECT * FROM requests ORDER BY created DESC").fetchall()
    db.close()
    return render_template("admin_requests.html", requests=reqs)

@app.route("/admin/delete-request/<int:req_id>", methods=["POST"])
def delete_request(req_id):
    if not is_admin():
        return redirect(url_for("admin"))
    db = get_db()
    db.execute("DELETE FROM requests WHERE id = ?", (req_id,))
    db.commit()
    db.close()
    flash("Request deleted.", "success")
    return redirect(url_for("admin_requests"))

@app.route("/admin/mark-done/<int:req_id>", methods=["POST"])
def mark_done(req_id):
    if not is_admin():
        return redirect(url_for("admin"))
    db = get_db()
    db.execute("UPDATE requests SET status = 'done' WHERE id = ?", (req_id,))
    db.commit()
    db.close()
    flash("Marked as done!", "success")
    return redirect(url_for("admin_requests"))
