from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import func
from datetime import datetime, date, timedelta

from app.extensions import db
from app.decorators import role_required
from app.models.giving import Giving
from app.models.member import Member
from app.models.visitor import Visitor
from app.utils import normalize_sa_phone

from app.models.sms_template import SMSTemplate
from app.models.sms_log import SMSLog
from app.services.sms_rotation_service import get_rotated_template

from datetime import date, datetime, timedelta

from app.models.check_in import CheckIn
from flask_login import current_user

from app.models.service import Service



giving_bp = Blueprint("giving", __name__, url_prefix="/giving")


from datetime import datetime
from sqlalchemy import func, extract

@giving_bp.route("/dashboard")
@login_required
@role_required("super_admin", "admin", "finance")
def giving_dashboard():

    from app.utils.branching import branch_query
    from sqlalchemy import extract

    now = datetime.utcnow()

    start_of_month = datetime(now.year, now.month, 1)
    if now.month == 12:
        end_of_month = datetime(now.year + 1, 1, 1)
    else:
        end_of_month = datetime(now.year, now.month + 1, 1)

    base_query = branch_query(Giving)

    # TOTALS
    total_amount = base_query.with_entities(func.sum(Giving.amount)).scalar() or 0

    month_total = (
        base_query
        .filter(Giving.created_at >= start_of_month)
        .filter(Giving.created_at < end_of_month)
        .with_entities(func.sum(Giving.amount))
        .scalar()
        or 0
    )

    member_total = (
        base_query
        .filter(Giving.member_id.isnot(None))
        .with_entities(func.sum(Giving.amount))
        .scalar()
        or 0
    )

    visitor_total = (
        base_query
        .filter(Giving.visitor_id.isnot(None))
        .with_entities(func.sum(Giving.amount))
        .scalar()
        or 0
    )

    # MONTHLY TOTALS
    raw_monthly = (
        base_query
        .with_entities(
            extract("year", Giving.created_at).label("year"),
            extract("month", Giving.created_at).label("month"),
            func.sum(Giving.amount)
        )
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    monthly_totals = [
        {
            "month": f"{int(year)}-{int(month):02d}",
            "total": float(total)
        }
        for year, month, total in raw_monthly
    ]

    # CATEGORY TOTALS
    raw_types = (
        base_query
        .with_entities(Giving.giving_type, func.sum(Giving.amount))
        .group_by(Giving.giving_type)
        .all()
    )

    category_totals = [
        {"category": t if t else "Unspecified", "total": float(a)}
        for t, a in raw_types
    ]

    # RECENT GIVING
    recent_giving = (
        base_query
        .order_by(Giving.created_at.desc())
        .limit(10)
        .all()
    )

    total_for_percentage = member_total + visitor_total

    member_percentage = (
        (member_total / total_for_percentage) * 100
        if total_for_percentage > 0 else 0
    )

    visitor_percentage = (
        (visitor_total / total_for_percentage) * 100
        if total_for_percentage > 0 else 0
    )

    return render_template(
        "giving_dashboard.html",
        total_amount=float(total_amount),
        month_total=float(month_total),
        member_total=float(member_total),
        visitor_total=float(visitor_total),
        monthly_totals=monthly_totals,
        category_totals=category_totals,
        type_totals=[
            {"type": "Members", "total": float(member_total)},
            {"type": "Visitors", "total": float(visitor_total)}
        ],
        member_percentage=member_percentage,
        visitor_percentage=visitor_percentage,
        recent_giving=recent_giving
    )


from flask import Response
import csv
from io import StringIO


@giving_bp.route("/export/recent")
@login_required
@role_required("super_admin", "admin", "finance")
def export_recent_giving():

    from app.utils.branching import branch_query

    recent_giving = (
        branch_query(Giving)
        .order_by(Giving.created_at.desc())
        .all()
    )

    si = StringIO()
    writer = csv.writer(si)

    # Header row
    writer.writerow(["Date", "Amount", "Type", "Member ID", "Visitor ID"])

    for g in recent_giving:
        writer.writerow([
            g.created_at.strftime("%Y-%m-%d"),
            float(g.amount),
            g.giving_type,
            g.member_id,
            g.visitor_id
        ])

    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=recent_giving.csv"
        }
    )

@giving_bp.route("/export/monthly")
@login_required
@role_required("super_admin", "admin", "finance")
def export_monthly_summary():

    from app.utils.branching import branch_query
    from sqlalchemy import func  # Add this import

    raw_monthly = (
        branch_query(Giving)
        .with_entities(
            func.to_char(Giving.created_at, 'YYYY-MM'),
            func.sum(Giving.amount)
        )
        .group_by(func.to_char(Giving.created_at, 'YYYY-MM'))
        .order_by(func.to_char(Giving.created_at, 'YYYY-MM'))
        .all()
    )

@giving_bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def add_giving():

    from app.models.lookup import Lookup
    from app.models.sms_template import SMSTemplate
    from app.models.sms_log import SMSLog

    # Fetch offering types from Master Data
    offering_types = Lookup.query.filter_by(category="offering_type").all()

    if request.method == "POST":

        raw_phone = request.form.get("phone")
        phone = normalize_sa_phone(raw_phone) if raw_phone else None  # CHANGED: Allow empty phone

        # Optional: Get name for phone-less giving
        giver_name = request.form.get("giver_name", "Anonymous")

        # If phone provided, try to find member/visitor
        member = None
        visitor = None
        
        if phone:
            member = db.session.execute(
                db.select(Member).where(Member.phone == phone)
            ).scalar_one_or_none()

            if not member:
                visitor = db.session.execute(
                    db.select(Visitor).where(Visitor.phone == phone)
                ).scalar_one_or_none()

        # ================= SAVE GIVING =================
        giving = Giving(
            branch_id=current_user.branch_id,
            phone=phone,  # Can be None
            amount=float(request.form["amount"]),
            giving_type=request.form["giving_type"],
            notes=request.form.get("notes"),
            giver_name=giver_name if not phone else None  # Track name if no phone
        )

        if member:
            giving.member_id = member.id

        if visitor:
            giving.visitor_id = visitor.id

        db.session.add(giving)
        db.session.commit()

        # ================= SMS TEMPLATE ROTATION =================
        # Only send SMS if phone exists
        if phone:
            template = get_rotated_template(phone, giving.giving_type)

            if template:
                message = template.message

                if member:
                    message = message.replace("{name}", member.first_name)
                elif visitor:
                    message = message.replace("{name}", visitor.first_name)
                else:
                    message = message.replace("{name}", "Friend")

                sms = SMSLog(
                    phone=phone,
                    message=message,
                    message_type=giving.giving_type.lower(),
                    related_table="giving",
                    related_id=giving.id,
                    status="pending",
                    branch_id=giving.branch_id,
                    template_id=template.id
                )

                db.session.add(sms)
                db.session.commit()
        else:
            # Log that no SMS was sent due to missing phone
            flash(f"Giving recorded for {giver_name}. No SMS sent (no phone on file).", "info")

        flash("Offering recorded successfully.", "success")
        return redirect(url_for("giving.giving_dashboard"))
    
    # GET request - show form
    return render_template("add_giving.html", offering_types=offering_types)