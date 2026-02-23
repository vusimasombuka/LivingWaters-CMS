from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import date, datetime, timedelta
from flask_login import current_user
from app.extensions import db
from app.models.member import Member
from app.models.visitor import Visitor
from app.models.check_in import CheckIn
from app.utils import normalize_sa_phone
from app.decorators import role_required
from app.models.sms_template import SMSTemplate
from app.models.sms_log import SMSLog
from app.services.sms_rotation_service import get_rotated_template
from app.models.service import Service

checkin_bp = Blueprint("checkin", __name__)

@checkin_bp.route("/check-in", methods=["GET", "POST"])
@role_required("super_admin", "usher", "admin")
def check_in():

    services = Service.query.filter_by(active=True).all()

    if request.method == "POST":

        from datetime import datetime, timedelta

        phone = normalize_sa_phone(request.form.get("phone"))
        service_id = request.form.get("service_id")
        today = date.today()

        # ================= CHECK FOR NAME-BASED CHECK-IN (NO PHONE) =================
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        
        # If no phone but has name, check in without phone
        if not phone and first_name and last_name:
            return handle_name_based_checkin(first_name, last_name, service_id, today)

        if not service_id:
            flash("Service is required.", "error")
            return redirect(url_for("checkin.check_in"))

        if not phone:
            # Show form for name-based check-in
            return render_template(
                "checkin_no_phone.html",
                service_id=service_id,
                services=services
            )

        service = Service.query.get(service_id)

        if not service:
            flash("Invalid service selected.", "error")
            return redirect(url_for("checkin.check_in"))

        # ================= SERVICE DAY VALIDATION =================
        now = datetime.now()

        if now.strftime("%A") != service.day_of_week:
            flash("Check-in is only allowed on the scheduled service day.", "error")
            return redirect(url_for("checkin.check_in"))

        service_time = datetime.strptime(service.time, "%H:%M").time()
        service_datetime = datetime.combine(now.date(), service_time)

        window_start = service_datetime - timedelta(hours=2)
        window_end = service_datetime + timedelta(hours=1)

        if not (window_start <= now <= window_end):
            flash("Check-in is only allowed during the service time window.", "error")
            return redirect(url_for("checkin.check_in"))

        # ================= HARD BLOCK DUPLICATES =================
        existing = CheckIn.query.filter_by(
            phone=phone,
            service_id=service.id,
            check_in_date=today
        ).first()

        if existing:
            flash("You are already checked in for this service today.", "info")
            return redirect(url_for("checkin.check_in"))

        # ================= MEMBER =================
        member = Member.query.filter_by(phone=phone).first()
        if member:

            db.session.add(CheckIn(
                phone=phone,
                member_id=member.id,
                service_id=service.id,
                check_in_date=today
            ))
            db.session.commit()

            # Only send SMS if member has phone
            if member.phone:
                send_member_sms(member, "member_returning")

            flash(f"Welcome back, {member.first_name}!", "success")
            return redirect(url_for("checkin.check_in"))

        # ================= EXISTING VISITOR =================
        visitor = Visitor.query.filter_by(phone=phone).first()
        if visitor:

            db.session.add(CheckIn(
                phone=phone,
                visitor_id=visitor.id,
                service_id=service.id,
                check_in_date=today
            ))
            db.session.commit()

            # Only send SMS if visitor has phone
            if visitor.phone:
                send_visitor_sms(visitor, "visitor_returning")

            flash(f"Welcome back, {visitor.first_name}! We're glad to see you again.", "success")
            return redirect(url_for("checkin.check_in"))

        
        # ================= FIRST TIME VISITOR =================
        if request.form.get("first_name"):

            # 🔒 CHECK IF MEMBER WITH THIS PHONE EXISTS
            existing_member = Member.query.filter_by(phone=phone).first()
            if existing_member:
                flash(
                    f"This phone number belongs to a member ({existing_member.first_name} {existing_member.last_name}). "
                    f"Please use member check-in instead.",
                    "error"
                )
                return redirect(url_for("checkin.check_in"))

            # 🔒 CHECK IF VISITOR WITH THIS PHONE EXISTS (shouldn't happen due to earlier check, but safety)
            existing_visitor = Visitor.query.filter_by(phone=phone).first()
            if existing_visitor:
                flash(
                    f"A visitor with this phone already exists. Please check in as returning visitor.",
                    "warning"
                )
                return redirect(url_for("checkin.check_in"))

            visitor = Visitor(
                first_name=request.form["first_name"],
                last_name=request.form["last_name"],
                phone=phone,
                branch_id=current_user.branch_id
            )

            db.session.add(visitor)
            db.session.flush()

            db.session.add(CheckIn(
                phone=phone,
                visitor_id=visitor.id,
                service_id=service.id,
                check_in_date=today
            ))

            db.session.commit()

            # Only send SMS if visitor has phone
            if phone:
                template = SMSTemplate.query.filter_by(
                    message_type="visitor_thank_you",
                    active=True
                ).first()

                if template:
                    message = template.message.replace("{name}", visitor.first_name)

                    sms = SMSLog(
                        phone=phone,
                        message=message,
                        message_type="visitor_thank_you",
                        related_table="check_in",
                        related_id=visitor.id,
                        status="scheduled",
                        branch_id=current_user.branch_id,
                        template_id=template.id
                    )

                    db.session.add(sms)
                    db.session.commit()

            flash(f"Thank you for visiting, {visitor.first_name}!", "success")
            return redirect(url_for("checkin.check_in"))

        return render_template(
            "visitor_details.html",
            phone=phone,
            service_id=service_id
        )

    return render_template("checkin_phone.html", services=services)


def handle_name_based_checkin(first_name, last_name, service_id, today):
    """Handle check-in for people without phones"""
    
    service = Service.query.get(service_id)
    if not service:
        flash("Invalid service selected.", "error")
        return redirect(url_for("checkin.check_in"))

    # Check if visitor exists by name (optional - might create duplicates)
    visitor = Visitor.query.filter_by(
        first_name=first_name,
        last_name=last_name
    ).first()

    if not visitor:
        # Create new visitor without phone
        visitor = Visitor(
            first_name=first_name,
            last_name=last_name,
            phone=None,  # No phone
            branch_id=current_user.branch_id
        )
        db.session.add(visitor)
        db.session.flush()

    # Create check-in without phone
    checkin = CheckIn(
        phone=None,  # No phone
        visitor_id=visitor.id,
        service_id=service.id,
        check_in_date=today
    )
    
    db.session.add(checkin)
    db.session.commit()

    flash(f"Welcome, {visitor.first_name}! (No phone on file - no SMS sent)", "info")
    return redirect(url_for("checkin.check_in"))


def send_member_sms(member, message_type):
    """Send SMS to member if they have phone"""
    if not member.phone:
        return
    
    template = get_rotated_template(member.phone, message_type)
    if template:
        message = template.message.replace("{name}", member.first_name)
        sms = SMSLog(
            phone=member.phone,
            message=message,
            message_type=message_type,
            related_table="member",
            related_id=member.id,
            status="pending",
            branch_id=current_user.branch_id,
            template_id=template.id
        )
        db.session.add(sms)
        db.session.commit()


def send_visitor_sms(visitor, message_type):
    """Send SMS to visitor if they have phone"""
    if not visitor.phone:
        return
    
    template = get_rotated_template(visitor.phone, message_type)
    if template:
        message = template.message.replace("{name}", visitor.first_name)
        sms = SMSLog(
            phone=visitor.phone,
            message=message,
            message_type=message_type,
            related_table="check_in",
            related_id=visitor.id,
            status="pending",
            branch_id=current_user.branch_id,
            template_id=template.id
        )
        db.session.add(sms)
        db.session.commit()