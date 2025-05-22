from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)
app.secret_key = "mon_secret_admin"

def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE)")
        c.execute("CREATE TABLE IF NOT EXISTS time_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER, timestamp TEXT, type TEXT, FOREIGN KEY(employee_id) REFERENCES employees(id))")

init_db()

def calculate_stats():
    from collections import defaultdict
    now = datetime.now()
    current_month = now.strftime('%Y-%m')
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    stats = defaultdict(lambda: {"current": 0, "previous": 0, "shifts": 0})

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT employee_id, timestamp, type FROM time_logs ORDER BY timestamp ASC")
        logs = c.fetchall()

    open_shift = {}
    for emp_id, ts, tp in logs:
        month = ts[:7]
        if tp == "entrée":
            open_shift[emp_id] = ts
        elif tp == "sortie" and emp_id in open_shift:
            start = datetime.strptime(open_shift[emp_id], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            hours = (end - start).total_seconds() / 3600
            if month == current_month:
                stats[emp_id]["current"] += hours
            elif month == last_month:
                stats[emp_id]["previous"] += hours
            stats[emp_id]["shifts"] += 1
            del open_shift[emp_id]

    return stats

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
            c.execute('INSERT INTO time_logs (employee_id, timestamp, type) VALUES (?, ?, ?)', (user[0], now, action))
            conn.commit()
            return f"{user[1]} a pointé {action} à {now}"
        else:
            return "Code invalide"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == "admin" and request.form['password'] == "Kankanmoussa17":
            session['admin'] = True
            return redirect(url_for('employees'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/employees')
def employees():
    if not session.get("admin"):
        return redirect(url_for('login'))
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM employees")
        employees = c.fetchall()
    stats = calculate_stats()
    return render_template('employees.html', employees=employees, stats=stats)

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
    return redirect(url_for('employees'))

@app.route('/delete_employee/<int:emp_id>')
def delete_employee(emp_id):
    if not session.get("admin"):
        return redirect(url_for('login'))
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM time_logs WHERE employee_id = ?", (emp_id,))
        c.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        conn.commit()
    return redirect(url_for('employees'))