import secrets
from datetime import datetime
import time
from flask import *
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db_connection
from flask import Flask

app = Flask(__name__)

app.secret_key = "api_gateway_secret"


@app.route("/")
def home():

    if "user_id" in session:
        return redirect("/dashboard")

    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO users
            (
                name,
                email,
                password
            )
            VALUES(%s,%s,%s)
        """,
        (
            name,
            email,
            generate_password_hash(password)
        ))

        conn.commit()

        cur.execute(
            "SELECT id FROM users WHERE email=%s",
            (email,)
        )

        user_id = cur.fetchone()[0]

        api_key = secrets.token_hex(32)

        cur.execute("""
            INSERT INTO api_keys
            (
                user_id,
                api_key
            )
            VALUES (%s,%s)
        """,
        (
            user_id,
            api_key
        ))

        conn.commit()

        cur.close()
        conn.close()

        flash("Registration Successful")

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                name,
                password,
                role
            FROM users
            WHERE email=%s
        """,
        (email,))

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and check_password_hash(
            user[2],
            password
        ):

            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["role"] = user[3]

            return redirect("/dashboard")

        flash("Invalid Email or Password")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT api_key
        FROM api_keys
        WHERE user_id=%s
    """, (session["user_id"],))

    api_key = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM api_logs
        WHERE user_id=%s
    """, (session["user_id"],))

    total_requests = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(
            AVG(response_time_ms),
            0
        )
        FROM api_logs
        WHERE user_id=%s
    """, (session["user_id"],))

    avg_response = round(float(cur.fetchone()[0]), 2)

    cur.execute("""
        SELECT COUNT(*)
        FROM api_logs
        WHERE user_id=%s
        AND status_code >= 400
    """, (session["user_id"],))

    errors = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "dashboard.html",
        user=session["user_name"],
        api_key=api_key,
        total_requests=total_requests,
        avg_response=avg_response,
        errors=errors
    )


@app.route("/api/weather")
def weather_api():

    api_key = request.headers.get("X-API-KEY")

    if not api_key:
        return jsonify(
            {
                "error": "API Key Missing"
            }
        ), 401

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id
        FROM api_keys
        WHERE api_key=%s
    """,
    (api_key,))

    user = cur.fetchone()

    if not user:

        cur.close()
        conn.close()

        return jsonify(
            {
                "error": "Invalid API Key"
            }
        ), 401

    start_time = time.time()

    response = {
        "city": "Trivandrum",
        "temperature": "31°C",
        "condition": "Sunny"
    }

    response_time = round(
        (time.time() - start_time) * 1000,
        2
    )

    cur.execute("""
        INSERT INTO api_logs
        (
            user_id,
            endpoint,
            response_time_ms,
            status_code
        )
        VALUES
        (%s,%s,%s,%s)
    """,
    (
        user[0],
        "/api/weather",
        response_time,
        200
    ))

    conn.commit()

    cur.close()
    conn.close()

    return jsonify(response)


@app.route("/requests")
def requests_page():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            endpoint,
            request_time,
            response_time_ms,
            status_code
        FROM api_logs
        WHERE user_id=%s
        ORDER BY request_time DESC
    """,
    (session["user_id"],))

    logs = cur.fetchall()

    print("Current User ID:", session["user_id"])
    print("Logs:", logs)

    cur.close()
    conn.close()

    return render_template(
        "requests.html",
        logs=logs
    )


@app.route("/analytics")
def analytics():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cur = conn.cursor()

    # Requests by endpoint

    cur.execute("""
        SELECT
            endpoint,
            COUNT(*)
        FROM api_logs
        WHERE user_id=%s
        GROUP BY endpoint
    """, (session["user_id"],))

    endpoint_data = cur.fetchall()

    labels = [row[0] for row in endpoint_data]
    values = [row[1] for row in endpoint_data]

    # Success vs Errors

    cur.execute("""
        SELECT COUNT(*)
        FROM api_logs
        WHERE user_id=%s
        AND status_code = 200
    """, (session["user_id"],))

    success_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM api_logs
        WHERE user_id=%s
        AND status_code >= 400
    """, (session["user_id"],))

    error_count = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "analytics.html",
        labels=labels,
        values=values,
        success_count=success_count,
        error_count=error_count
    )


@app.route("/admin")
def admin():

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role") != "admin":
        return redirect("/dashboard")

    conn = get_db_connection()
    cur = conn.cursor()

    # Total Users

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    # Total API Keys

    cur.execute("SELECT COUNT(*) FROM api_keys")
    total_keys = cur.fetchone()[0]

    # Total Requests

    cur.execute("SELECT COUNT(*) FROM api_logs")
    total_logs = cur.fetchone()[0]

    # Recent Logs

    cur.execute("""
        SELECT
            endpoint,
            request_time,
            status_code
        FROM api_logs
        ORDER BY request_time DESC
        LIMIT 10
    """)

    recent_logs = cur.fetchall()

    # Endpoint Usage Statistics

    cur.execute("""
        SELECT
            endpoint,
            COUNT(*) AS requests
        FROM api_logs
        GROUP BY endpoint
        ORDER BY requests DESC
    """)

    endpoint_stats = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_keys=total_keys,
        total_logs=total_logs,
        recent_logs=recent_logs,
        endpoint_stats=endpoint_stats
    )


@app.route("/regenerate_key", methods=["POST"])
def regenerate_key():

    if "user_id" not in session:
        return redirect("/login")

    new_key = secrets.token_hex(32)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE api_keys
        SET api_key=%s
        WHERE user_id=%s
    """,
    (
        new_key,
        session["user_id"]
    ))

    conn.commit()

    cur.close()
    conn.close()

    flash("API Key Regenerated Successfully")

    return redirect("/dashboard")


@app.route("/docs")
def docs():
    return render_template("docs.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )