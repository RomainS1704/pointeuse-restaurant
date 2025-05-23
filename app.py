from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "admin_secret"

def init_db():
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT UNIQUE)")
        c.execute("CREATE TABLE IF NOT EXISTS planning (employee_id INTEGER, day TEXT, shift TEXT, role TEXT, PRIMARY KEY(employee_id, day))")
init_db()

@app.route("/")
def home():
    return render_template("home.html")

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

@app.route("/pointeuse")
def pointeuse():
    return render_template("pointeuse.html")

@app.route("/planning", methods=["GET", "POST"])
def planning():
    if not session.get("admin"):
        return redirect(url_for("login"))

    days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    roles = ["cuisine", "plonge", "manager", "directeur", "barman", "service", "service R+1", "service R+2", "runner"]
    heures = ["09:00-15:00", "10:00-16:00", "12:00-18:00", "18:00-23:00", "18:00-00:00", "19:00-01:00", "20:00-02:00"]

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()

        if request.method == "POST":
            c.execute("DELETE FROM planning")
            for key in request.form:
                if key.startswith("shift_"):
                    _, emp_id, day = key.split("_")
                    value = request.form[key].strip()
                    if value:
                        if " " in value:
                            shift, role = value.split(" ", 1)
                            c.execute("REPLACE INTO planning (employee_id, day, shift, role) VALUES (?, ?, ?, ?)",
                                      (emp_id, day, shift, role))
            conn.commit()

        c.execute("SELECT id, name FROM employees")
        employees = c.fetchall()
        c.execute("SELECT employee_id, day, shift, role FROM planning")
        rows = c.fetchall()

    planning_data = defaultdict(dict)
    for emp_id, day, shift, role in rows:
        planning_data[int(emp_id)][day] = f"{shift} {role}"

    total_hours = {}
    for emp_id in planning_data:
        total = 0
        for val in planning_data[emp_id].values():
            if "-" in val:
                timeslot = val.split(" ")[0]
                try:
                    start, end = timeslot.split("-")
                    h1, m1 = map(int, start.split(":"))
                    h2, m2 = map(int, end.split(":"))
                    diff = (h2 * 60 + m2) - (h1 * 60 + m1)
                    if diff < 0:
                        diff += 24 * 60
                    total += diff
                except:
                    pass
        total_hours[emp_id] = f"{total // 60}h{total % 60:02}"

    return render_template("planning.html", employees=employees, planning=planning_data,
                           days=days, roles=roles, heures=heures, hours=total_hours)