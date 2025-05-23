from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime, timedelta
import sqlite3
import csv
import io
import json
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "admin_secret"

def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE)")
        c.execute("CREATE TABLE IF NOT EXISTS time_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id INTEGER, timestamp TEXT, type TEXT, FOREIGN KEY(employee_id) REFERENCES employees(id))")
        c.execute("CREATE TABLE IF NOT EXISTS planning (employee_id INTEGER, day TEXT, shift TEXT, role TEXT, PRIMARY KEY(employee_id, day))")

init_db()

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/pointeuse")
def pointeuse():
    return render_template("pointeuse.html")

@app.route("/pointe", methods=["POST"])
def pointe():
    code = request.form["code"]
    action = request.form["action"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT id, name FROM employees WHERE code = ?", (code,))
        user = c.fetchone()
        if user:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("INSERT INTO time_logs (employee_id, timestamp, type) VALUES (?, ?, ?)", (user[0], now, action))
            conn.commit()
            return f"{user[1]} a pointé {action} à {now}"
        else:
            return "Code invalide"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "Kankanmoussa17":
            session["admin"] = True
            return redirect(url_for("planning"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/employees")
def employees():
    if not session.get("admin"):
        return redirect(url_for("login"))
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, code FROM employees")
        employees = c.fetchall()
    stats, _ = calculate_stats()
    return render_template("employees.html", employees=employees, stats=stats)

@app.route("/add_employee", methods=["POST"])
def add_employee():
    if not session.get("admin"):
        return redirect(url_for("login"))
    name = request.form["name"]
    code = request.form["code"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO employees (name, code) VALUES (?, ?)", (name, code))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Code déjà utilisé"
    return redirect(url_for("employees"))

@app.route("/delete_employee/<int:emp_id>")
def delete_employee(emp_id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("DELETE FROM time_logs WHERE employee_id = ?", (emp_id,))
        c.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        c.execute("DELETE FROM planning WHERE employee_id = ?", (emp_id,))
        conn.commit()
    return redirect(url_for("employees"))

@app.route("/export_csv/<int:emp_id>")
def export_csv(emp_id):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Entrée", "Sortie", "Pause (min)", "Durée comptabilisée"])

    stats, shifts = calculate_stats()
    total_minutes = 0

    for shift in shifts.get(emp_id, []):
        date = shift["start"].strftime('%Y-%m-%d')
        start = shift["start"].strftime('%H:%M')
        end = shift["end"].strftime('%H:%M')
        pause = shift["pause"]
        net_minutes = int(shift["net_minutes"])
        hours = net_minutes // 60
        minutes = net_minutes % 60
        writer.writerow([date, start, end, pause, f"{hours:02}:{minutes:02}"])
        total_minutes += net_minutes

    total_hours = int(total_minutes) // 60
    total_mins = int(total_minutes) % 60
    writer.writerow([])
    writer.writerow(["", "", "", "Total", f"{total_hours:02}:{total_mins:02}"])

    buffer.seek(0)
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM employees WHERE id = ?", (emp_id,))
        name = c.fetchone()[0].replace(" ", "_")
    return send_file(io.BytesIO(buffer.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name=f"pointages_{name}.csv")

def calculate_stats():
    now = datetime.now()
    current_month = now.strftime('%Y-%m')
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    stats = defaultdict(lambda: {"current": 0, "previous": 0, "shifts": 0})
    shifts = defaultdict(list)

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT employee_id, timestamp, type FROM time_logs ORDER BY timestamp ASC")
        logs = c.fetchall()

        open_shift = {}
        for emp_id, ts, tp in logs:
            if tp == "entrée":
                open_shift[emp_id] = ts
            elif tp == "sortie" and emp_id in open_shift:
                start = datetime.strptime(open_shift[emp_id], '%Y-%m-%d %H:%M:%S')
                end = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                month = start.strftime('%Y-%m')

                pause = 0
                if start.hour < 18 and (end - start).total_seconds() >= 5 * 3600:
                    pause = 60
                elif start.hour >= 18 and (end - start).total_seconds() >= 4 * 3600:
                    pause = 30

                net_minutes = (end - start).total_seconds() / 60 - pause
                net_hours = net_minutes / 60

                if month == current_month:
                    stats[emp_id]["current"] += net_hours
                elif month == last_month:
                    stats[emp_id]["previous"] += net_hours
                stats[emp_id]["shifts"] += 1

                shifts[emp_id].append({
                    "start": start,
                    "end": end,
                    "pause": pause,
                    "net_minutes": net_minutes
                })

                del open_shift[emp_id]

    return stats, shifts

@app.route("/planning", methods=["GET", "POST"])
def planning():
    if not session.get("admin"):
        return redirect(url_for("login"))
    days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        if request.method == "POST":
            data = request.form.get("json")
            shifts = json.loads(data)
            for emp_id, val in shifts.items():
                for day, val in val.items():
                    c.execute("REPLACE INTO planning (employee_id, day, shift, role) VALUES (?, ?, ?, ?)",
                              (emp_id, day, val["shift"], val["role"]))
            conn.commit()
            return redirect(url_for("planning"))
        c.execute("SELECT id, name FROM employees")
        employees = c.fetchall()
        c.execute("SELECT employee_id, day, shift, role FROM planning")
        rows = c.fetchall()
    planning = defaultdict(dict)
    for eid, d, s, r in rows:
        planning[eid][d] = f"{s} {r}"
    return render_template("planning.html", employees=employees, planning=planning, days=days, hours={})