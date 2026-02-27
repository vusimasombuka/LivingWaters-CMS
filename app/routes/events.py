from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models.event import Event
from datetime import datetime
from flask_login import login_required, current_user
from app.decorators import role_required
from app.utils.branching import branch_query, enforce_branch_access

events_bp = Blueprint("events", __name__, url_prefix="/events")


@events_bp.route("/", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def events_admin():
    if request.method == "POST":
        # Branch assignment
        if current_user.role == "super_admin":
            branch_id = request.form.get("branch_id") or current_user.branch_id
        else:
            branch_id = current_user.branch_id

        # Create event with SMS settings
        event = Event(
            title=request.form["title"],
            event_date=datetime.strptime(request.form["event_date"], "%Y-%m-%d").date(),
            department=request.form.get("department"),
            description=request.form.get("description"),
            branch_id=branch_id,
            
            # SMS Settings
            sms_reminder_enabled=True if request.form.get("sms_reminder_enabled") else False,
            sms_reminder_90=True if request.form.get("sms_reminder_90") else False,
            sms_reminder_60=True if request.form.get("sms_reminder_60") else False,
            sms_reminder_30=True if request.form.get("sms_reminder_30") else False,
            sms_reminder_7=True if request.form.get("sms_reminder_7") else False,
        )

        db.session.add(event)
        db.session.commit()
        flash("Event added successfully.", "success")
        return redirect(url_for("events.events_admin"))

        # LIST EVENTS (Branch Isolated)
    from app.models.lookup import Lookup
    events = branch_query(Event).order_by(Event.event_date).all()
    departments = Lookup.query.filter_by(category="department", is_active=True).all()
    return render_template("events.html", events=events, departments=departments)


@events_bp.route("/edit/<int:event_id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def edit_event(event_id):
    """Edit event - handles both form display (GET) and update (POST)"""
    
    event = Event.query.get_or_404(event_id)
    enforce_branch_access(event)

    if request.method == "POST":
        # Update event details
        event.title = request.form["title"]
        event.event_date = datetime.strptime(request.form["event_date"], "%Y-%m-%d").date()
        event.department = request.form.get("department")
        event.description = request.form.get("description")
        
        # Update SMS settings
        event.sms_reminder_enabled = True if request.form.get("sms_reminder_enabled") else False
        event.sms_reminder_90 = True if request.form.get("sms_reminder_90") else False
        event.sms_reminder_60 = True if request.form.get("sms_reminder_60") else False
        event.sms_reminder_30 = True if request.form.get("sms_reminder_30") else False
        event.sms_reminder_7 = True if request.form.get("sms_reminder_7") else False
        
        db.session.commit()
        flash("Event updated successfully.", "success")
        return redirect(url_for("events.events_admin"))

        # GET request - show edit form
    from app.models.lookup import Lookup
    departments = Lookup.query.filter_by(category="department", is_active=True).all()
    return render_template("edit_event.html", event=event, departments=departments)


@events_bp.route("/delete/<int:event_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    enforce_branch_access(event)

    db.session.delete(event)
    db.session.commit()
    flash("Event deleted successfully.", "success")
    return redirect(url_for("events.events_admin"))


@events_bp.route("/api")
@login_required
def events_api():
    """API endpoint for calendar"""
    events = branch_query(Event).order_by(Event.event_date).all()

    data = {}
    for e in events:
        key = e.event_date.strftime("%Y-%m-%d")
        data.setdefault(key, []).append({
            "id": e.id,
            "title": e.title,
            "department": e.department,
            "description": e.description
        })

    return data