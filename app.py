from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime, timedelta
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

def calculate_hours():
    from collections import defaultdict
    from datetime import datetime
    import calendar

    current_month = datetime.now().strftime('%Y-%m')
    last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    hours_by_employee = defaultdict(lambda: {"current": 0, "previous": 0})

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT employee_id, timestamp, type FROM time_logs ORDER BY timestamp ASC")
        logs = c.fetchall()

    log_map = {}
    for emp_id, ts, tp in logs:
        month = ts[:7]
        if tp == "entrée":
            log_map[emp_id] = ts
        elif tp == "sortie" and emp_id in log_map:
            start = datetime.strptime(log_map[emp_id], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            hours = (end - start).total_seconds() / 3600
            if month == current_month:
                hours_by_employee[emp_id]["current"] += hours
            elif month == last_month:
                hours_by_employee[emp_id]["previous"] += hours
            del log_map[emp_id]

    return hours_by_employee

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

@app.route('/dashboard')
def dashboard():
    if not session.get("admin"):
        return redirect(url_for('login'))
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT e.name, t.timestamp, t.type FROM time_logs t JOIN employees e ON t.employee_id = e.id ORDER BY t.timestamp DESC")
        logs = c.fetchall()
    return render_template('dashboard.html', logs=logs)

@app.route('/employees')
def employees():
    if not session.get("admin"):
        return redirect(url_for('login'))
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM employees")
        employees = c.fetchall()
    hours = calculate_hours()
    return render_template('employees.html', employees=employees, hours=hours)

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