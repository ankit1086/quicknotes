@app.route('/admin')
def admin_panel():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('quicknotes.db')
    conn.row_factory = sqlite3.Row

    notes = conn.execute("SELECT * FROM notes").fetchall()
    requests = conn.execute("SELECT * FROM requests").fetchall()

    conn.close()

    return render_template('admin_panel.html', notes=notes, requests=requests)
