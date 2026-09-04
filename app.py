from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)
from database import get_db_connection
from config import Config
from email_service import send_otp_email
from mysql.connector import IntegrityError
from datetime import datetime, timedelta

import bcrypt
import random

import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config.from_object(Config)


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("login.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["POST"])
def login():

    email = request.form["email"]
    password = request.form["password"]

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT user_id, name, email, password, role, status
            FROM users
            WHERE email=%s
        """, (email,))

        user = cursor.fetchone()

        if not user:
            return "Invalid email or password"

        if not bcrypt.checkpw(
            password.encode(),
            user["password"].encode()
        ):
            return "Invalid email or password"

        if user["status"] != "APPROVED":
            return f"Account Status: {user['status']}"

        session["user_id"] = user["user_id"]
        session["role"] = user["role"]
        session["name"] = user["name"]

        if user["role"] == "ADMIN":
            return redirect(url_for("admin_dashboard"))
        elif user["role"] == "DSA":
            return redirect(url_for("dsa_dashboard", user_id=user["user_id"]))
        elif user["role"] == "BANK_EMPLOYEE":
            return redirect(url_for("bank_dashboard", user_id=user["user_id"]))

        return "Unknown User Role"

    except Exception as e:
        return f"Login Error: {e}"

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("home"))

    if session["role"] != "ADMIN":
        return redirect(url_for("home"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Users Table
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    # Total DSAs
    cursor.execute(
        "SELECT COUNT(*) AS total FROM users WHERE role='DSA'"
    )
    total_dsa = cursor.fetchone()["total"]

    # Total Bank Employees
    cursor.execute(
        "SELECT COUNT(*) AS total FROM users WHERE role='BANK_EMPLOYEE'"
    )
    total_bank = cursor.fetchone()["total"]

    # Pending Approvals
    cursor.execute(
        "SELECT COUNT(*) AS total FROM users WHERE status='PENDING'"
    )
    pending = cursor.fetchone()["total"]

    # Total Reviews
    cursor.execute(
        "SELECT COUNT(*) AS total FROM reviews"
    )
    total_reviews = cursor.fetchone()["total"]

    # Top Rated DSA
    cursor.execute("""
    SELECT
    users.name,
    ROUND(AVG(reviews.rating),1) AS rating
    FROM reviews
    JOIN dsa_profiles
    ON reviews.dsa_id=dsa_profiles.dsa_id
    JOIN users
    ON dsa_profiles.user_id=users.user_id
    GROUP BY users.name
    ORDER BY rating DESC
    LIMIT 1
    """)
    top_dsa = cursor.fetchone()
    # Most Popular Loan Type
    cursor.execute("""
    SELECT
    loan_types.loan_name,
    COUNT(*) AS total
    FROM dsa_loans
    JOIN loan_types
    ON dsa_loans.loan_id=loan_types.loan_id
    GROUP BY loan_types.loan_name
    ORDER BY total DESC
    LIMIT 1
    """)
    top_loan = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template(
    "admin.html",
    users=users,
    total_dsa=total_dsa,
    total_bank=total_bank,
    pending=pending,
    total_reviews=total_reviews,
    top_dsa=top_dsa,
    top_loan=top_loan
)

# ---------------- APPROVE USER ----------------

@app.route("/approve/<int:user_id>")
def approve_user(user_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE users SET status='APPROVED' WHERE user_id=%s",
        (user_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin_dashboard"))


# ---------------- REJECT USER ----------------

@app.route("/reject/<int:user_id>")
def reject_user(user_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE users SET status='REJECTED' WHERE user_id=%s",
        (user_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin_dashboard"))


# ---------------- DSA REGISTRATION PAGE ----------------

@app.route("/dsa/register")
def dsa_register():
    return render_template("dsa_register.html")


# ---------------- SAVE DSA ----------------

@app.route("/dsa/register", methods=["POST"])
def save_dsa():

    connection = get_db_connection()
    cursor = connection.cursor()

    name = request.form["name"]
    email = request.form["email"]
    phone = request.form["phone"]
    whatsapp = request.form["whatsapp"]

    photo = request.files.get("photo")
    print(request.files)
    if not photo or photo.filename == "":
        return "Please select a profile photo."

    password = request.form["password"]

    hashed_password = bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt()
    ).decode()

    filename = secure_filename(photo.filename)
    photo.save(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
            )
        )

    otp = str(random.randint(100000,999999))
    session["otp"] = otp
    session["otp_email"] = email
    session["otp_time"] = datetime.now().isoformat()
    
    city = request.form["city"]
    state = request.form["state"]
    address = request.form["address"]

    loans = request.form.getlist("loans")
    banks = request.form["banks"].split(",")

    # Create user
    cursor.execute("""
        INSERT INTO users
        (name,email,phone,password,role,status)
        VALUES(%s,%s,%s,%s,'DSA','PENDING')
    """, (name,email,phone,hashed_password))

    connection.commit()


    user_id = cursor.lastrowid

    # Create profile
    cursor.execute("""
    INSERT INTO dsa_profiles
    (user_id,profile_description,city,state,address,whatsapp,photo)
    VALUES(%s,'',%s,%s,%s,%s,%s)
    """, (user_id, city, state, address, whatsapp, filename))
    connection.commit()

    dsa_id = cursor.lastrowid

    # Save selected loans
    for loan in loans:

        cursor.execute(
            "SELECT loan_id FROM loan_types WHERE loan_name=%s",
            (loan,)
        )

        result = cursor.fetchone()

        if result:
            cursor.execute(
                "INSERT INTO dsa_loans(dsa_id,loan_id) VALUES(%s,%s)",
                (dsa_id, result[0])
            )

    # Save banks
    for bank in banks:

        bank = bank.strip()

        if bank:
            cursor.execute(
                "INSERT INTO dsa_banks(dsa_id,bank_name) VALUES(%s,%s)",
                (dsa_id, bank)
            )

    connection.commit()

    cursor.close()
    connection.close()

    send_otp_email(email, otp)
    return redirect(url_for("verify_otp"))


# ---------------- DSA DASHBOARD ----------------

@app.route("/dsa/dashboard/<int:user_id>")
def dsa_dashboard(user_id):

    if "user_id" not in session:
        return redirect(url_for("home"))
    if session["role"] != "DSA":
        return redirect(url_for("home"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE user_id=%s",
        (user_id,)
    )

    user = cursor.fetchone()

    cursor.execute("""
        SELECT dsa_id
        FROM dsa_profiles
        WHERE user_id=%s
    """,(user_id,))

    dsa = cursor.fetchone()

    avg_rating = 0
    total_reviews = 0

    if dsa:

        cursor.execute("""
        SELECT
        ROUND(AVG(rating),1) AS avg_rating,
        COUNT(*) AS total_reviews
        FROM reviews
        WHERE dsa_id=%s
        """,(dsa["dsa_id"],))

        result = cursor.fetchone()

        avg_rating = result["avg_rating"] or 0
        total_reviews = result["total_reviews"]

    cursor.close()
    connection.close()

    return render_template(
        "dsa_dashboard.html",
        user=user,
        avg_rating=avg_rating,
        total_reviews=total_reviews
    )

@app.route("/bank/register")
def bank_register():
    return render_template("bank_register.html")


@app.route("/bank/register", methods=["POST"])
def save_bank_employee():

    connection = get_db_connection()
    cursor = connection.cursor()

    name = request.form["name"]
    email = request.form["email"]
    phone = request.form["phone"]
    password = request.form["password"]
    hashed_password = bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt()
    ).decode()

    bank_name = request.form["bank_name"]
    branch = request.form["branch"]
    city = request.form["city"]
    state = request.form["state"]

    cursor.execute("""
        INSERT INTO users
        (name,email,phone,password,role,status)
        VALUES(%s,%s,%s,%s,'BANK_EMPLOYEE','PENDING')
    """,(name,email,phone,hashed_password))

    connection.commit()

    user_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO bank_employees
        (user_id,bank_name,branch,city,state,official_email)
        VALUES(%s,%s,%s,%s,%s,%s)
    """,(user_id,bank_name,branch,city,state,email))

    connection.commit()

    cursor.close()
    connection.close()

    return """
    <h2>Registration Successful</h2>
    <p>Your account is waiting for Admin Approval.</p>
    <a href="/">Back to Login</a>
    """
@app.route("/bank/dashboard/<int:user_id>")
def bank_dashboard(user_id):

    if "user_id" not in session:
        return redirect(url_for("home"))
    if session["role"] != "BANK_EMPLOYEE":
        return redirect(url_for("home"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE user_id=%s",
        (user_id,)
    )

    user = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template("bank_dashboard.html", user=user)
@app.route("/customer")
def customer():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    search = request.args.get("search", "")
    city = request.args.get("city", "")
    loan = request.args.get("loan", "")

    query = """
    SELECT DISTINCT
        users.user_id,
        dsa_profiles.dsa_id,
        users.name,
        users.email,
        users.role,
        users.status,
        COALESCE(dsa_profiles.city, bank_employees.city) AS city
    FROM users
    LEFT JOIN dsa_profiles
        ON users.user_id = dsa_profiles.user_id
    LEFT JOIN bank_employees
        ON users.user_id = bank_employees.user_id
    LEFT JOIN dsa_loans
        ON dsa_profiles.dsa_id = dsa_loans.dsa_id
    LEFT JOIN loan_types
        ON dsa_loans.loan_id = loan_types.loan_id
    WHERE users.status = 'APPROVED'
    """

    params = []

    if search:
        query += " AND users.name LIKE %s"
        params.append("%" + search + "%")

    if city:
        query += " AND COALESCE(dsa_profiles.city, bank_employees.city) LIKE %s"
        params.append("%" + city + "%")

    if loan:
        query += " AND loan_types.loan_name = %s"
        params.append(loan)

    cursor.execute(query, tuple(params))
    people = cursor.fetchall()
    print("People Found:", people)

    cursor.close()
    connection.close()

    return render_template("customer.html", people=people)

@app.route("/review/<int:dsa_id>")
def review_page(dsa_id):

    return render_template(
        "review.html",
        dsa_id=dsa_id
    )


@app.route("/review/<int:dsa_id>", methods=["POST"])
def save_review(dsa_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    customer_name = request.form["customer_name"]
    rating = request.form["rating"]
    comment = request.form["comment"]

    cursor.execute("""
    INSERT INTO reviews
    (dsa_id,customer_name,rating,comment)
    VALUES(%s,%s,%s,%s)
    """,(dsa_id,customer_name,rating,comment))

    connection.commit()

    cursor.close()
    connection.close()

    return """
    <h2>Review Submitted Successfully</h2>
    <a href='/customer'>Back to Customer Portal</a>
    """

@app.route("/dsa/profile/<int:dsa_id>")
def dsa_profile(dsa_id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # User + City
    cursor.execute("""
        SELECT
        users.user_id,
        users.name,
        users.email,
        dsa_profiles.city,
        dsa_profiles.whatsapp,
        dsa_profiles.photo
        FROM users
        JOIN dsa_profiles
        ON users.user_id = dsa_profiles.user_id
        WHERE dsa_profiles.dsa_id = %s
    """, (dsa_id,))

    user = cursor.fetchone()

    # Loan Types
    cursor.execute("""
        SELECT loan_types.loan_name
        FROM dsa_loans
        JOIN loan_types
        ON dsa_loans.loan_id = loan_types.loan_id
        WHERE dsa_loans.dsa_id = %s
    """, (dsa_id,))

    loans = cursor.fetchall()

    # Banks
    cursor.execute("""
        SELECT bank_name
        FROM dsa_banks
        WHERE dsa_id = %s
    """, (dsa_id,))

    banks = cursor.fetchall()

    # Rating
    cursor.execute("""
        SELECT
            ROUND(AVG(rating),1) AS avg_rating,
            COUNT(*) AS total_reviews
        FROM reviews
        WHERE dsa_id = %s
    """, (dsa_id,))

    rating = cursor.fetchone()

    # Reviews
    cursor.execute("""
        SELECT customer_name, rating, comment
        FROM reviews
        WHERE dsa_id = %s
        ORDER BY review_id DESC
    """, (dsa_id,))

    reviews = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "dsa_profile.html",
        dsa_id=dsa_id,
        user=user,
        city=user["city"] if user else "",
        whatsapp=user["whatsapp"],
        loans=loans,
        banks=banks,
        avg_rating=rating["avg_rating"] or 0,
        total_reviews=rating["total_reviews"],
        reviews=reviews
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))

@app.route("/verify-otp")
def verify_otp():

    return render_template("verify_otp.html")

@app.route("/verify-otp", methods=["POST"])
def verify_otp_post():

    entered_otp = request.form["otp"]

    if "otp" not in session:
        return "OTP Expired. Please Register Again."

    otp_time = datetime.fromisoformat(session["otp_time"])

    if datetime.now() > otp_time + timedelta(minutes=5):
        session.pop("otp", None)
        session.pop("otp_email", None)
        session.pop("otp_time", None)
        return "OTP Expired. Please Register Again."


    if entered_otp != session["otp"]:
        return "Invalid OTP"

    session["otp_verified"] = True

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE users
        SET status='APPROVED'
        WHERE email=%s
        """,
        (session["otp_email"],)
        )
    connection.commit()
    cursor.close()
    connection.close()

    session.pop("otp", None)
    session.pop("otp_email", None)
    session.pop("otp_time", None)
    return """
    <h2>OTP Verified Successfully</h2>
    <p>Your account is now active.</p>
    <a href="/">Go to Login</a>
    """

@app.route("/resend-otp")
def resend_otp():

    if "otp_email" not in session:
        return "Please Register Again."

    otp = str(random.randint(100000,999999))

    session["otp"] = otp
    session["otp_time"] = datetime.now().isoformat()

    send_otp_email(session["otp_email"], otp)

    return redirect(url_for("verify_otp"))

from flask import send_from_directory

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )

if __name__ == "__main__":
    app.run(debug=True)