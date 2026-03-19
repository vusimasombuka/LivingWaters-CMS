from flask import Blueprint, render_template, request, redirect, url_for, send_file
from flask_login import login_required
from app.decorators import role_required
from app.extensions import db
from sqlalchemy import text, inspect
import csv
import io
from app.extensions import db
from sqlalchemy import func, case
from datetime import date
from app.models.check_in import CheckIn
from app.models.visitor import Visitor
from app.models.giving import Giving
from sqlalchemy import extract
import calendar
from flask import session
import json
from app.models.service import Service
from app.models.member import Member
from app.models.visitor import Visitor
from app.models.check_in import CheckIn
from app.models.sms_log import SMSLog
from app.models.service import Service
from app.utils.branching import branch_query

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

LAST_RESULTS = []
LAST_COLUMNS = []


def get_tables():
    inspector = inspect(db.engine)

    tables = []

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        tables.append({
            "name": table_name,
            "columns": columns
        })

    return tables


# ================= REPORTS HOME =================
@reports_bp.route("/", methods=["GET"])
@login_required
@role_required("super_admin")
def reports_home():

    inspector = inspect(db.engine)

    tables = []
    for table_name in inspector.get_table_names():
        tables.append({
            "name": table_name,
            "columns": inspector.get_columns(table_name)
        })

    return render_template(
        "reports.html",
        tables=tables,
        results=None,
        columns=None,
        query=""
    )


# ================= RUN SQL QUERY =================
@reports_bp.route("/run", methods=["POST"])
@login_required
@role_required("super_admin")
def run_query():

    
    query = request.form.get("query")

    if not query:
        return "Query is required."

    query_clean = query.lower().strip()

    blocked_keywords = ["insert", "update", "delete", "drop", "alter", "create"]

    if not query_clean.startswith("select") or any(word in query_clean for word in blocked_keywords):
        return "Only SELECT queries are allowed."

    try:
        result = db.session.execute(text(query))

        rows = result.fetchall()
        columns = result.keys()

        session["last_columns"] = list(columns)
        session["last_results"] = [list(row) for row in rows]

        return render_template(
            "reports.html",
            results=rows,
            columns=columns,
            query=query,
            tables=get_tables()
        )

    except Exception as e:
        return f"Error: {str(e)}"



# ================= EXPORT SQL CSV =================
@reports_bp.route("/export-sql-csv")
@login_required
@role_required("super_admin")
def export_sql_csv():

    columns = session.get("last_columns")
    rows = session.get("last_results")

    if not columns or not rows:
        return redirect(url_for("reports.reports_home"))

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(columns)
    writer.writerows(rows)

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="sql_report.csv"
    )





@reports_bp.route('/attendance')
@login_required
@role_required("admin", "super_admin")
def attendance_simple():

    rows = (
        branch_query(CheckIn)
        .join(Service, CheckIn.service_id == Service.id)
        .with_entities(
            Service.name,
            db.func.count(CheckIn.id)
        )
        .group_by(Service.name)
        .all()
    )

    attendance_data = [
        {"label": service, "total": total}
        for service, total in rows
    ]

    return render_template(
        "reports/attendance.html",
        attendance_data=attendance_data
    )




@reports_bp.route("/reports/attendance/summary")
@login_required
@role_required("admin", "super_admin")
def attendance_summary():

    data = (
        branch_query(CheckIn)
        .join(Service, CheckIn.service_id == Service.id)
        .with_entities(
            Service.name.label("label"),
            db.func.count(CheckIn.id).label("total")
        )
        .group_by(Service.name)
        .order_by(db.func.count(CheckIn.id).desc())
        .all()
    )

    labels = [row.label for row in data]
    totals = [row.total for row in data]

    return render_template(
        "reports/attendance.html",
        labels=labels,
        totals=totals
    )



@reports_bp.route("/attendance/daily")
@login_required
@role_required("admin", "super_admin")
def attendance_daily():

    rows = (
        branch_query(CheckIn)
        .with_entities(
            db.func.date(CheckIn.created_at).label("label"),
            db.func.count(CheckIn.id).label("total")
        )
        .group_by(db.func.date(CheckIn.created_at))
        .order_by(db.func.date(CheckIn.created_at))
        .all()
    )

    attendance_data = [
        {"label": str(row.label), "total": row.total}
        for row in rows
    ]

    return render_template(
        "reports/attendance.html",
        attendance_data=attendance_data
    )



@reports_bp.route("/attendance/by-service")
@login_required
@role_required("admin", "super_admin")
def attendance_by_service():

    rows = (
        branch_query(CheckIn)
        .join(Service, CheckIn.service_id == Service.id)
        .with_entities(
            Service.name.label("label"),
            db.func.count(CheckIn.id).label("total")
        )
        .group_by(Service.name)
        .order_by(db.func.count(CheckIn.id).desc())
        .all()
    )

    attendance_data = [
        {"label": row.label or "Unknown", "total": row.total}
        for row in rows
    ]

    return render_template(
        "reports/attendance.html",
        attendance_data=attendance_data
    )



@reports_bp.route("/reports/attendance")
@login_required
@role_required("admin", "super_admin")
def attendance_analytics():

    attendance_data = (
        branch_query(CheckIn)
        .join(Service, CheckIn.service_id == Service.id)
        .with_entities(
            Service.name.label("label"),
            db.func.count(CheckIn.id).label("total")
        )
        .group_by(Service.name)
        .all()
    )

    chart_data = [
        {"label": row.label, "total": row.total}
        for row in attendance_data
    ]

    return render_template(
        "reports/attendance.html",
        attendance_data=chart_data
    )


@reports_bp.route("/attendance/trend")
@login_required
@role_required("admin", "super_admin")
def attendance_trend():

    rows = (
        branch_query(CheckIn)
        .with_entities(
            db.func.date(CheckIn.created_at).label("date"),
            db.func.count(CheckIn.id).label("total")
        )
        .group_by(db.func.date(CheckIn.created_at))
        .order_by(db.func.date(CheckIn.created_at))
        .all()
    )

    attendance_data = [
        {
            "label": row.date.strftime("%Y-%m-%d"),
            "total": row.total
        }
        for row in rows
    ]

    return render_template(
        "reports/attendance.html",
        attendance_data=attendance_data,
        chart_type="line"
    )




@reports_bp.route("/reports/giving", methods=["GET"])
@login_required
@role_required("finance", "admin", "super_admin")
def giving_analytics():

    year = request.args.get("year", type=int) or date.today().year
    selected_month = request.args.get("month", type=int) or date.today().month

    # -----------------------------
    # 1️⃣ Selected month → totals by giving type
    # -----------------------------
    month_rows = (
        branch_query(Giving)
        .with_entities(
            Giving.giving_type.label("type"),
            db.func.sum(Giving.amount).label("total")
        )
        .filter(
            extract("year", Giving.created_at) == year,
            extract("month", Giving.created_at) == selected_month
        )
        .group_by(Giving.giving_type)
        .all()
    )

    monthly_by_type = [
        {"label": r.type, "total": float(r.total)}
        for r in month_rows
    ]

    totals = {"Donation": 0, "Tithe": 0, "Offering": 0}
    for r in month_rows:
        totals[r.type] = float(r.total)

    # -----------------------------
    # 2️⃣ Full year → Jan–Dec totals
    # -----------------------------
    year_rows = (
        branch_query(Giving)
        .with_entities(
            extract("month", Giving.created_at).label("month"),
            db.func.sum(Giving.amount).label("total")
        )
        .filter(extract("year", Giving.created_at) == year)
        .group_by(extract("month", Giving.created_at))
        .order_by(extract("month", Giving.created_at))
        .all()
    )

    yearly_totals = [
        {
            "month": calendar.month_name[int(r.month)],
            "total": float(r.total)
        }
        for r in year_rows
    ]

    months = [
        {"value": i, "name": calendar.month_name[i]}
        for i in range(1, 13)
    ]

    return render_template(
        "reports/giving.html",
        monthly_by_type=monthly_by_type,
        yearly_totals=yearly_totals,
        totals=totals,
        selected_month=selected_month,
        year=year,
        months=months
    )




@reports_bp.route("/reports/giving/export")
@login_required
@role_required("finance", "admin", "super_admin")
def export_giving_csv():
    import csv
    from flask import Response

    rows = branch_query(Giving) \
    .with_entities(
        Giving.giving_type,
        Giving.amount,
        Giving.created_at
    ) \
    .order_by(Giving.created_at) \
    .all()

    def generate():
        yield "Type,Amount,Date\n"
        for r in rows:
            yield f"{r.giving_type},{r.amount},{r.created_at.date()}\n"

    return Response(generate(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=giving.csv"})



@reports_bp.route("/retention-monitor")
@login_required
@role_required("admin", "super_admin")
def retention_monitor():

    from datetime import date, timedelta

    today = date.today()
    cutoff = today - timedelta(days=14)

    data = []

    def process(person, person_type):

        last_checkin = (
            branch_query(CheckIn)
            .filter(
                getattr(CheckIn, f"{person_type}_id") == person.id
            )
            .order_by(CheckIn.check_in_date.desc())
            .first()
        )

        if not last_checkin:
            return

        if last_checkin.check_in_date > cutoff:
            return

        sms_count = SMSLog.query.filter_by(
            phone=person.phone,
            message_type="absentees_follow_up"
        ).count()

        status = "Active Follow-up" if sms_count < 3 else "Completed (3 Sent)"

        data.append({
            "first_name": person.first_name,
            "last_name": person.last_name,
            "phone": person.phone,
            "type": person_type.capitalize(),
            "last_checkin": last_checkin.check_in_date,
            "sms_count": sms_count,
            "status": status
        })

    # 🔒 Branch isolated members
    for m in branch_query(Member).all():
        process(m, "member")

    # 🔒 Branch isolated visitors
    for v in branch_query(Visitor).all():
        process(v, "visitor")

    return render_template(
        "reports/retention_monitor.html",
        data=data
    )