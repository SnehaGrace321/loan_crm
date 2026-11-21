from flask import Flask, render_template, request, redirect, url_for, session
from config import get_db_connection
import bcrypt

app = Flask(__name__)
app.secret_key = "loan-crm-secret-key"


@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s AND status = 'active'",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user:
            try:
                password_valid = bcrypt.checkpw(
                    password.encode("utf-8"),
                    user["password_hash"].encode("utf-8")
                )
            except ValueError:
                password_valid = False

            if password_valid:
                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["role"] = user["role"]

                if user["role"] == "admin":
                    return redirect(url_for("dashboard"))
                else:
                    return redirect(url_for("staff_dashboard"))

        return render_template(
            "login.html",
            error="Invalid email or password"
        )

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Total leads
    cursor.execute("SELECT COUNT(*) AS total_leads FROM leads")
    total_leads = cursor.fetchone()["total_leads"]

    # Today's calls
    cursor.execute("""
        SELECT COUNT(*) AS today_calls
        FROM calls
        WHERE DATE(called_at) = CURDATE()
    """)
    today_calls = cursor.fetchone()["today_calls"]

    # Interested leads
    cursor.execute("""
        SELECT COUNT(*) AS interested_leads
        FROM leads
        WHERE status = 'interested'
    """)
    interested_leads = cursor.fetchone()["interested_leads"]

    # Approved loans
    cursor.execute("""
        SELECT COUNT(*) AS approved_loans
        FROM loan_applications
        WHERE status = 'approved'
    """)
    approved_loans = cursor.fetchone()["approved_loans"]

    cursor.close()
    db.close()

    return render_template(
        "admin/dashboard.html",
        name=session["name"],
        total_leads=total_leads,
        today_calls=today_calls,
        interested_leads=interested_leads,
        approved_loans=approved_loans

    )


@app.route("/staff/dashboard")
def staff_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "staff":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Assigned leads
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM leads
        WHERE assigned_to = %s
    """, (session["user_id"],))

    total_leads = cursor.fetchone()["total"]

    # Today's calls
    cursor.execute("""
        SELECT COUNT(*) AS today_calls
        FROM calls
        WHERE staff_id = %s
        AND DATE(called_at) = CURDATE()
    """, (session["user_id"],))

    today_calls = cursor.fetchone()["today_calls"]

    # Interested leads
    cursor.execute("""
        SELECT COUNT(DISTINCT lead_id) AS interested_leads
        FROM calls
        WHERE staff_id = %s
        AND interest_status = 'interested'
    """, (session["user_id"],))

    interested_leads = cursor.fetchone()["interested_leads"]

    # Scheduled follow-ups
    cursor.execute("""
        SELECT COUNT(*) AS followups
        FROM calls
        WHERE staff_id = %s
        AND follow_up_date IS NOT NULL
    """, (session["user_id"],))

    followups = cursor.fetchone()["followups"]

    cursor.close()
    db.close()

    return render_template(
        "staff/dashboard.html",
        name=session["name"],
        total_leads=total_leads,
        today_calls=today_calls,
        interested_leads=interested_leads,
        followups=followups
    )


@app.route("/staff/leads")
def staff_leads():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "staff":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM leads
        WHERE assigned_to = %s
        ORDER BY created_at DESC
    """, (session["user_id"],))

    leads = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "staff/leads.html",
        leads=leads
    )


@app.route("/staff/call/<int:lead_id>", methods=["GET", "POST"])
def staff_call(lead_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "staff":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Get only the lead assigned to this staff member
    cursor.execute("""
        SELECT *
        FROM leads
        WHERE id = %s
        AND assigned_to = %s
    """, (lead_id, session["user_id"]))

    lead = cursor.fetchone()

    if not lead:
        cursor.close()
        db.close()
        return "Lead not found or not assigned to you", 404

    if request.method == "POST":

        call_status = request.form["call_status"]
        interest_status = request.form["interest_status"]
        remarks = request.form["remarks"]
        follow_up_date = request.form.get("follow_up_date")

        # Save call
        cursor.execute("""
            INSERT INTO calls
            (lead_id, staff_id, call_status, interest_status, remarks,follow_up_date)
            VALUES (%s, %s, %s, %s, %s,%s)
        """, (
            lead_id,
            session["user_id"],
            call_status,
            interest_status,
            remarks,
            follow_up_date
        ))

        # Update lead status
        cursor.execute("""
            UPDATE leads
            SET status = %s
            WHERE id = %s
        """, (interest_status, lead_id))

        db.commit()

        cursor.close()
        db.close()

        return redirect(url_for("staff_leads"))

    cursor.close()
    db.close()

    return render_template(
        "staff/call.html",
        lead=lead
    )


@app.route("/staff/followups")
def staff_followups():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "staff":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            c.lead_id,
            c.follow_up_date,
            c.remarks,
            l.customer_name,
            l.phone,
            l.loan_type
        FROM calls c
        JOIN leads l
        ON c.lead_id = l.id
        WHERE c.staff_id = %s
        AND c.follow_up_date IS NOT NULL
        ORDER BY c.follow_up_date ASC
    """, (session["user_id"],))

    followups = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "staff/followups.html",
        followups=followups
    )





@app.route("/admin/leads")
def leads():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Get all leads with assigned staff name
    cursor.execute("""
        SELECT
            leads.*,
            users.name AS staff_name
        FROM leads
        LEFT JOIN users
        ON leads.assigned_to = users.id
        ORDER BY leads.created_at DESC
    """)

    leads = cursor.fetchall()

    # Get active staff members
    cursor.execute("""
        SELECT id, name
        FROM users
        WHERE role = 'staff'
        AND status = 'active'
        ORDER BY name
    """)

    staff = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "admin/leads.html",
        leads=leads,
        staff=staff
    )





@app.route("/admin/leads/assign/<int:lead_id>", methods=["POST"])
def assign_lead(lead_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    staff_id = request.form["staff_id"]

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE leads
        SET assigned_to = %s,
            status = 'assigned'
        WHERE id = %s
    """, (staff_id, lead_id))

    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("leads"))




@app.route("/admin/leads/add", methods=["GET", "POST"])
def add_lead():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    if request.method == "POST":

        customer_name = request.form["customer_name"]
        phone = request.form["phone"]
        email = request.form["email"]
        city = request.form["city"]
        loan_type = request.form["loan_type"]
        loan_amount = request.form["loan_amount"]
        source = request.form["source"]

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO leads
            (customer_name, phone, email, city, loan_type, loan_amount, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            customer_name,
            phone,
            email,
            city,
            loan_type,
            loan_amount,
            source
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect(url_for("leads"))

    return render_template("admin/add_lead.html")


@app.route("/admin/bulk-upload")
def bulk_upload():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    return render_template("admin/bulk_upload.html")

@app.route("/admin/employees")
def employees():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, email, role, daily_target, status, created_at
        FROM users
        ORDER BY created_at DESC
    """)

    employees = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "admin/employees.html",
        employees=employees
    )



@app.route("/admin/banks")
def banks():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    return render_template("admin/banks.html")



@app.route("/admin/employees/add", methods=["GET", "POST"])
def add_employee():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        daily_target = request.form["daily_target"]

        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO users
            (name, email, password_hash, role, daily_target, status)
            VALUES (%s, %s, %s, 'staff', %s, 'active')
        """, (
            name,
            email,
            password_hash,
            daily_target
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect(url_for("employees"))

    return render_template("admin/add_employee.html")


@app.route("/admin/employees/edit/<int:employee_id>", methods=["GET", "POST"])
def edit_employee(employee_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        daily_target = request.form["daily_target"]
        status = request.form["status"]

        cursor.execute("""
            UPDATE users
            SET name = %s,
                email = %s,
                daily_target = %s,
                status = %s
            WHERE id = %s
            AND role = 'staff'
        """, (
            name,
            email,
            daily_target,
            status,
            employee_id
        ))

        db.commit()

        cursor.close()
        db.close()

        return redirect(url_for("employees"))

    cursor.execute("""
        SELECT *
        FROM users
        WHERE id = %s
        AND role = 'staff'
    """, (employee_id,))

    employee = cursor.fetchone()

    cursor.close()
    db.close()

    if not employee:
        return "Employee not found", 404

    return render_template(
        "admin/edit_employee.html",
        employee=employee
    )




@app.route("/admin/employees/delete/<int:employee_id>", methods=["POST"])
def delete_employee(employee_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied", 403

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE users
        SET status = 'inactive'
        WHERE id = %s
        AND role = 'staff'
    """, (employee_id,))

    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("employees"))




@app.route("/mobile-admin", methods=["GET", "POST"])
def mobile_admin():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM users
            WHERE email = %s
            AND role = 'admin'
            AND status = 'active'
        """, (email,))

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and bcrypt.checkpw(
            password.encode("utf-8"),
            user["password_hash"].encode("utf-8")
        ):

            session["mobile_admin_id"] = user["id"]
            session["mobile_admin_name"] = user["name"]

            return redirect(url_for("mobile_admin_dashboard"))

        return render_template(
            "mobile_admin/login.html",
            error="Invalid admin email or password"
        )

    return render_template("mobile_admin/login.html")


@app.route("/mobile-admin/dashboard")
def mobile_admin_dashboard():

    if "mobile_admin_id" not in session:
        return redirect(url_for("mobile_admin"))

    return render_template(
        "mobile_admin/dashboard.html"
    )

@app.route("/mobile-admin/leads")
def mobile_admin_leads():

    if "mobile_admin_id" not in session:
        return redirect(url_for("mobile_admin"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            leads.*,
            users.name AS staff_name
        FROM leads
        LEFT JOIN users
            ON leads.assigned_to = users.id
        ORDER BY leads.created_at DESC
    """)

    leads = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "mobile_admin/leads.html",
        leads=leads
    )




@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)



