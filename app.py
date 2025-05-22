from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime
import sqlite3
import csv
import io

app = Flask(__name__)
app.secret_key = "mon_secret_admin"

def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE)")
        c.execute("CREATE TABLE IF NOT EXISTS time_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER, timestamp TEXT, type TEXT, FOREIGN KEY(employee_id) REFERENCES employees(id))")

init_db()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/pointeuse')
def pointeuse():
    return render_template('pointeuse.html')

@app.route('/pointe', methods=['POST'])
def pointe():
    code = request.form['code']
    action = request.form['action']
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('SELECT id, name FROM employees WHERE code = ?', (code,))
        user = c.fetchone()
        if user:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute('INSERT INTO time_logs (employee_id, timestamp, type) VALUES (?, ?, ?)',
                      (user[0], now, action))
            conn.commit()
            return f"{user[1]} a pointé {action} à {now}"
        else:
            return "Code invalide"

@app.route('/dashboard')
def dashboard():
    if not session.get("admin"):
        return redirect(url_for('login'))
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT e.name, t.timestamp, t.type FROM time_logs t JOIN employees e ON t.employee_id = e.id ORDER BY t.timestamp DESC")
        logs = c.fetchall()
    return render_template('dashboard.html', logs=logs)

@app.route('/add_employee', methods=['POST'])
def add_employee():
    if not session.get("admin"):
        return redirect(url_for('login'))
    name = request.form['name']
    code = request.form['code']
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        try:
            c.execute('INSERT INTO employees (name, code) VALUES (?, ?)', (name, code))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Code déjà utilisé"
    return redirect(url_for('dashboard'))

@app.route('/export_csv')
def export_csv():
    if not session.get("admin"):
        return redirect(url_for('login'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Nom', 'Horodatage', 'Type'])
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT e.name, t.timestamp, t.type FROM time_logs t JOIN employees e ON t.employee_id = e.id ORDER BY t.timestamp DESC")
        for row in c.fetchall():
            writer.writerow(row)
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='pointages.csv')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == "admin" and request.form['password'] == "admin123":
            session['admin'] = True
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)