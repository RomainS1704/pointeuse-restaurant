import os
app = Flask(__name__)
app.config['DEBUG'] = True
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE)")
        c.execute("CREATE TABLE IF NOT EXISTS time_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER, timestamp TEXT, type TEXT, FOREIGN KEY(employee_id) REFERENCES employees(id))")
    print("Database initialized")

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
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        query = "SELECT e.name, t.timestamp, t.type FROM time_logs t JOIN employees e ON t.employee_id = e.id ORDER BY t.timestamp DESC"
        c.execute(query)
        logs = c.fetchall()
    return render_template('dashboard.html', logs=logs)

@app.route('/add_employee', methods=['POST'])
def add_employee():
    name = request.form['name']
    code = request.form['code']
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        try:
            c.execute('INSERT INTO employees (name, code) VALUES (?, ?)', (name, code))
            conn.commit()
            return redirect(url_for('pointeuse'))
        except sqlite3.IntegrityError:
            return "Ce code est déjà utilisé."

init_db()

if __name__ == '__main__':
    app.run(debug=True)