from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime, timedelta
import sqlite3
import csv
import io
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "mon_secret_admin"

def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, manual_shifts INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS time_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER, timestamp TEXT, type TEXT, FOREIGN KEY(employee_id) REFERENCES employees(id))")

init_db()

def calculate_stats():
    now = datetime.now()
    current_month = now.strftime('%Y-%m')
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    stats = defaultdict(lambda: {"current": 0, "previous": 0, "shifts": 0})

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT employee_id, timestamp, type FROM time_logs ORDER BY timestamp ASC")
        logs = c.fetchall()
        for emp_id, ts, tp in logs:
            month = ts[:7]
            if tp == "entrée":
                stats[emp_id]["last_in"] = ts
            elif tp == "sortie" and "last_in" in stats[emp_id]:
                start = datetime.strptime(stats[emp_id]["last_in"], '%Y-%m-%d %H:%M:%S')
                end = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                hours = (end - start).total_seconds() / 3600
                if month == current_month:
                    stats[emp_id]["current"] += hours
                elif month == last_month:
                    stats[emp_id]["previous"] += hours
                stats[emp_id]["shifts"] += 1
                del stats[emp_id]["last_in"]

        c.execute("SELECT id, manual_shifts FROM employees")
        for emp_id, manual in c.fetchall():
            stats[emp_id]["manual"] = manual

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
        c.execute("SELECT id, name, code, manual_shifts FROM employees")
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

@app.route('/update_shifts/<int:emp_id>', methods=['POST'])
def update_shifts(emp_id):
    new_value = request.form['manual_shifts']
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("UPDATE employees SET manual_shifts = ? WHERE id = ?", (new_value, emp_id))
        conn.commit()
    return redirect(url_for('employees'))

@app.route('/export_csv/<int:emp_id>')
def export_csv(emp_id):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Horodatage", "Type"])

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM employees WHERE id = ?", (emp_id,))
        name = c.fetchone()[0]
        c.execute("SELECT timestamp, type FROM time_logs WHERE employee_id = ? ORDER BY timestamp", (emp_id,))
        for row in c.fetchall():
            writer.writerow(row)

    buffer.seek(0)
    return send_file(io.BytesIO(buffer.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name=f"{name}_pointages.csv")