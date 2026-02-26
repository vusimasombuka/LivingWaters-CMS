from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
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
from sqlalchemy.orm import joinedload

checkin_bp = Blueprint("checkin", __name__)


def is_check_in_window_open(service):
    """
    Check if check-in is currently allowed for this service.
    Returns (bool, message) tuple.
    Window: 2 hours before start time to 2 hours after start time.
    """
    from datetime import datetime
    
    # Map day names to weekday numbers (Monday=0, Sunday=6)
    days_map = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    
    now = datetime.now()
    service_day_num = days_map.get(service.day_of_week)
    
    if service_day_num is None:
        return False, "Invalid service day configuration"
    
    # Check if today is the service day
    if now.weekday() != service_day_num:
        return False, f"Check-in is only available on {service.day_of_week}s"
    
    # Parse service time (handle both 24h and 12h formats)
    try:
        service_time = datetime.strptime(service.time, "%H:%M").time()
    except ValueError:
        try:
            service_time = datetime.strptime(service.time, "%I:%M %p").time()
        except ValueError:
            return False, "Invalid service time format"
    
    # Create service datetime for today
    service_datetime = datetime.combine(now.date(), service_time)
    
    # Define window: 2 hours before to 2 hours after
    window_start = service_datetime - timedelta(hours=2)
    window_end = service_datetime + timedelta(hours=2)
    
    if now < window_start:
        time_until = window_start - now
        hours, remainder = divmod(time_until.seconds, 3600)
        minutes = remainder // 60
        return False, f"Check-in opens in {hours}h {minutes}m ({service.time})"
    
    if now > window_end:
        return False, f"Check-in closed for this service (ended at {window_end.strftime('%H:%M')})"
    
    return True, "Check-in is open"


@checkin_bp.route("/check-in", methods=["GET", "POST"])
@role_required("super_admin", "usher", "admin")
def check_in():
    """Main check-in route"""
    
    if request.method == "POST":
        phone = normalize_sa_phone(request.form.get("phone"))
        service_id = request.form.get("service_id")
        today = date.today()
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")

        if not service_id:
            flash("Service is required.", "error")
            return redirect(url_for("checkin.check_in"))

        # Get service and derive branch
        service = Service.query.get(service_id)
        if not service:
            flash("Invalid service selected.", "error")
            return redirect(url_for("checkin.check_in"))
        
        # CHECK TIME WINDOW
        allowed, message = is_check_in_window_open(service)
        if not allowed:
            flash(f"Check-in unavailable: {message}", "warning")
            return redirect(url_for("checkin.check_in"))
        
        branch_id = service.branch_id
        
        # Security check
        if current_user.role != "super_admin":
            if branch_id != current_user.branch_id:
                abort(403)

        # ============================================
        # CASE 1: Has Phone Number
        # ============================================
        if phone:
            # Check if already checked in today (ONLY if phone provided)
            existing = CheckIn.query.filter_by(
                phone=phone,
                service_id=service.id,
                check_in_date=today
            ).first()

            if existing:
                flash("Already checked in for this service.", "info")
                return redirect(url_for("checkin.check_in"))

            # CHECK 1: Is this a MEMBER?
            member = Member.query.filter_by(phone=phone, branch_id=branch_id).first()
            if member:
                db.session.add(CheckIn(
                    phone=phone,
                    member_id=member.id,
                    service_id=service.id,
                    check_in_date=today,
                    branch_id=branch_id
                ))
                db.session.commit()

                send_member_sms(member, "member_returning", branch_id)
                flash(f"Welcome back, {member.first_name}!", "success")
                return redirect(url_for("checkin.check_in"))

            # CHECK 2: Is this a RETURNING VISITOR?
            visitor = Visitor.query.filter_by(phone=phone, branch_id=branch_id).first()
            if visitor:
                db.session.add(CheckIn(
                    phone=phone,
                    visitor_id=visitor.id,
                    service_id=service.id,
                    check_in_date=today,
                    branch_id=branch_id
                ))
                db.session.commit()

                send_visitor_sms(visitor, "visitor_returning", branch_id, delay=False)
                flash(f"Welcome back, {visitor.first_name}!", "success")
                return redirect(url_for("checkin.check_in"))

            # CHECK 3: NEW VISITOR (Phone not found in system)
            # If names provided, create visitor immediately
            if first_name and last_name:
                visitor = Visitor(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    branch_id=branch_id
                )
                db.session.add(visitor)
                db.session.flush()

                db.session.add(CheckIn(
                    phone=phone,
                    visitor_id=visitor.id,
                    service_id=service.id,
                    check_in_date=today,
                    branch_id=branch_id
                ))
                db.session.commit()

                send_visitor_sms(visitor, "visitor_thank_you", branch_id, delay=True)
                flash(f"Thank you for visiting, {visitor.first_name}!", "success")
                return redirect(url_for("checkin.check_in"))
            
            # Phone provided but not found in DB, and NO names yet
            # Redirect to details page to collect first/last name
            return render_template("visitor_details.html", phone=phone, service_id=service_id)

        # ============================================
        # CASE 2: No Phone Number (direct from no-phone form)
        # ============================================
        else:
            if not first_name or not last_name:
                flash("First and last name are required.", "error")
                return redirect(url_for("checkin.check_in_no_phone"))

            # NOTE: No duplicate check here - allow multiple no-phone entries
            # Create visitor without phone
            visitor = Visitor(
                first_name=first_name,
                last_name=last_name,
                phone=None,
                branch_id=branch_id
            )
            db.session.add(visitor)
            db.session.flush()

            db.session.add(CheckIn(
                phone=None,
                visitor_id=visitor.id,
                service_id=service.id,
                check_in_date=today,
                branch_id=branch_id
            ))
            db.session.commit()

            flash(f"Welcome, {visitor.first_name}! Visitor recorded.", "success")
            return redirect(url_for("checkin.check_in"))

    # GET REQUEST - Show main check-in form
    if current_user.role == "super_admin":
        services = Service.query.options(joinedload(Service.branch)).filter_by(active=True).all()
    else:
        services = Service.query.filter_by(active=True, branch_id=current_user.branch_id).all()

    return render_template("checkin_phone.html", services=services)


@checkin_bp.route("/check-in/no-phone", methods=["GET"])
@role_required("super_admin", "usher", "admin")
def check_in_no_phone():
    """Show the no-phone check-in form"""
    
    if current_user.role == "super_admin":
        services = Service.query.options(joinedload(Service.branch)).filter_by(active=True).all()
    else:
        services = Service.query.filter_by(active=True, branch_id=current_user.branch_id).all()
    
    return render_template("checkin_no_phone.html", services=services)


def send_member_sms(member, message_type, branch_id):
    """Send SMS to member"""
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
            branch_id=branch_id,
            template_id=template.id
        )
        db.session.add(sms)
        db.session.commit()


def send_visitor_sms(visitor, message_type, branch_id, delay=False):
    """Send SMS to visitor"""
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
            status="scheduled" if delay else "pending",
            branch_id=branch_id,
            template_id=template.id
        )
        db.session.add(sms)
        db.session.commit()

        # ================= PUBLIC CHECK-IN (QR CODE) =================

@checkin_bp.route("/welcome/<token>", methods=["GET", "POST"])
def public_check_in(token):
    """Public check-in via branch QR code"""
    from app.models.branch import Branch
    from sqlalchemy import case
    
    branch = Branch.query.filter_by(public_token=token).first_or_404()
    
    # Get active services for this branch
    all_services = Service.query.filter_by(
        branch_id=branch.id, 
        active=True
    ).order_by(
        case(
            (Service.day_of_week == 'Sunday', 1),
            (Service.day_of_week == 'Monday', 2),
            (Service.day_of_week == 'Tuesday', 3),
            (Service.day_of_week == 'Wednesday', 4),
            (Service.day_of_week == 'Thursday', 5),
            (Service.day_of_week == 'Friday', 6),
            (Service.day_of_week == 'Saturday', 7),
        ),
        Service.time
    ).all()
    
    services = all_services
    
    if not services:
        return render_template("public_error.html", 
                             message="No active services available for this branch.",
                             branch_name=branch.name)

    if request.method == "POST":
        service_id = request.form.get("service_id")
        phone = normalize_sa_phone(request.form.get("phone"))
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        today = date.today()
        
        if not service_id:
            flash("Please select a service.", "warning")
            return redirect(url_for("checkin.public_check_in", token=token))
        
        if not first_name or not last_name:
            flash("First and last name are required.", "warning")
            return redirect(url_for("checkin.public_check_in", token=token))
        
        service = Service.query.get(service_id)
        if not service or service.branch_id != branch.id:
            abort(403)
        
        # CHECK TIME WINDOW FOR PUBLIC CHECK-IN
        allowed, message = is_check_in_window_open(service)
        if not allowed:
            flash(f"Check-in unavailable: {message}", "warning")
            return redirect(url_for("checkin.public_check_in", token=token))
        
        # Check for duplicate ONLY if phone is provided
        if phone:
            existing = CheckIn.query.filter_by(
                phone=phone,
                service_id=service.id,
                check_in_date=today
            ).first()
            
            if existing:
                flash("You've already checked in for this service today. Welcome back!", "info")
                return redirect(url_for("checkin.public_check_in", token=token))
        # NOTE: If no phone, we skip the duplicate check entirely
        
        # Process check-in (simplified logic)
        if phone:
            member = Member.query.filter_by(phone=phone, branch_id=branch.id).first()
            if member:
                db.session.add(CheckIn(
                    phone=phone,
                    member_id=member.id,
                    service_id=service.id,
                    check_in_date=today,
                    branch_id=branch.id
                ))
                db.session.commit()
                send_member_sms(member, "member_returning", branch.id)
                flash(f"Welcome back, {member.first_name}! Checked in for {service.name}.", "success")
                return redirect(url_for("checkin.public_check_in", token=token))
            
            visitor = Visitor.query.filter_by(phone=phone, branch_id=branch.id).first()
            if visitor:
                db.session.add(CheckIn(
                    phone=phone,
                    visitor_id=visitor.id,
                    service_id=service.id,
                    check_in_date=today,
                    branch_id=branch.id
                ))
                db.session.commit()
                send_visitor_sms(visitor, "visitor_returning", branch.id, delay=False)
                flash(f"Welcome back, {visitor.first_name}! Checked in for {service.name}.", "success")
                return redirect(url_for("checkin.public_check_in", token=token))
            
            # New visitor
            visitor = Visitor(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                branch_id=branch.id
            )
            db.session.add(visitor)
            db.session.flush()
            
            db.session.add(CheckIn(
                phone=phone,
                visitor_id=visitor.id,
                service_id=service.id,
                check_in_date=today,
                branch_id=branch.id
            ))
            db.session.commit()
            send_visitor_sms(visitor, "visitor_thank_you", branch.id, delay=True)
            flash(f"Thank you for visiting, {visitor.first_name}!", "success")
            return redirect(url_for("checkin.public_check_in", token=token))
        else:
            # No phone - no duplicate check, just create new record
            visitor = Visitor(
                first_name=first_name,
                last_name=last_name,
                phone=None,
                branch_id=branch.id
            )
            db.session.add(visitor)
            db.session.flush()
            
            db.session.add(CheckIn(
                phone=None,
                visitor_id=visitor.id,
                service_id=service.id,
                check_in_date=today,
                branch_id=branch.id
            ))
            db.session.commit()
            flash(f"Welcome, {visitor.first_name}! Checked in for {service.name}.", "success")
            return redirect(url_for("checkin.public_check_in", token=token))

    return render_template("public_checkin.html", 
                         branch=branch, 
                         services=services,
                         token=token)