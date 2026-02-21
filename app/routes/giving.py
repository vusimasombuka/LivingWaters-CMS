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


from app.models.service import Service



giving_bp = Blueprint("giving", __name__, url_prefix="/giving")


@giving_bp.route("/dashboard")
@login_required
@role_required("super_admin", "admin", "finance")
def giving_dashboard():

    now = datetime.utcnow()

    # =========================
    # TOTALS
    # =========================
    total_amount = db.session.query(func.sum(Giving.amount)).scalar() or 0

    month_total = (
        db.session.query(func.sum(Giving.amount))
        .filter(func.strftime("%Y-%m", Giving.created_at) == now.strftime("%Y-%m"))
        .scalar()
        or 0
    )

    member_total = (
        db.session.query(func.sum(Giving.amount))
        .filter(Giving.member_id.isnot(None))
        .scalar()
        or 0
    )

    visitor_total = (
        db.session.query(func.sum(Giving.amount))
        .filter(Giving.visitor_id.isnot(None))
        .scalar()
        or 0
    )

    # =========================
    # MONTHLY TOTALS
    # =========================
    raw_monthly = (
        db.session.query(
            func.strftime("%Y-%m", Giving.created_at),
            func.sum(Giving.amount)
        )
        .group_by(func.strftime("%Y-%m", Giving.created_at))
        .order_by(func.strftime("%Y-%m", Giving.created_at))
        .all()
    )

    monthly_totals = [
        {"month": m, "total": float(t)}
        for m, t in raw_monthly
    ]

    # =========================
    # CATEGORY TOTALS
    # =========================
    raw_types = (
        db.session.query(
            Giving.giving_type,
            func.sum(Giving.amount)
        )
        .group_by(Giving.giving_type)
        .all()
    )

    category_totals = [
        {"category": t if t else "Unspecified", "total": float(a)}
        for t, a in raw_types
    ]

    # =========================
    # TYPE TOTALS
    # =========================
    type_totals = [
        {"type": "Members", "total": float(member_total)},
        {"type": "Visitors", "total": float(visitor_total)}
    ]

    # =========================
    # MEMBER / VISITOR %
    # =========================
    total_for_percentage = member_total + visitor_total

    if total_for_percentage > 0:
        member_percentage = (member_total / total_for_percentage) * 100
        visitor_percentage = (visitor_total / total_for_percentage) * 100
    else:
        member_percentage = 0
        visitor_percentage = 0

    # =========================
    # RECENT GIVING
    # =========================
    recent_giving = (
    db.session.query(Giving)
    .order_by(Giving.created_at.desc())
    .limit(10)
    .all()
)


    return render_template(
        "giving_dashboard.html",
        total_amount=total_amount,
        month_total=month_total,
        member_total=member_total,
        visitor_total=visitor_total,
        monthly_totals=monthly_totals,
        category_totals=category_totals,
        type_totals=type_totals,
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

    recent_giving = (
        Giving.query
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

    raw_monthly = (
        db.session.query(
            func.strftime("%Y-%m", Giving.created_at),
            func.sum(Giving.amount)
        )
        .group_by(func.strftime("%Y-%m", Giving.created_at))
        .order_by(func.strftime("%Y-%m", Giving.created_at))
        .all()
    )

    si = StringIO()
    writer = csv.writer(si)

    writer.writerow(["Month", "Total"])

    for month, total in raw_monthly:
        writer.writerow([month, float(total)])

    output = si.getvalue()

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=monthly_summary.csv"
        }
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
                    branch_id=1,
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