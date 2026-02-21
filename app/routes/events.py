from flask import Blueprint, render_template, request, redirect, url_for
from app.extensions import db
from app.models.event import Event
from datetime import datetime
from flask_login import login_required
from app.decorators import role_required


events_bp = Blueprint("events", __name__, url_prefix="/events")


@events_bp.route("/", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def events_admin():

    if request.method == "POST":
        event = Event(
            title=request.form["title"],
            event_date=datetime.strptime(
                request.form["event_date"], "%Y-%m-%d"
            ).date(),
            department=request.form.get("department"),
            description=request.form.get("description")
        )
        db.session.add(event)
        db.session.commit()
        return redirect(url_for("events.events_admin"))

    events = Event.query.order_by(Event.event_date).all()
    return render_template("events.html", events=events)


@events_bp.route("/api")
@login_required
def events_api():

    events = Event.query.order_by(Event.event_date).all()
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


@events_bp.route("/edit/<int:event_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")

def edit_event(event_id):
    event = Event.query.get_or_404(event_id)

    event.title = request.form["title"]
    event.event_date = datetime.strptime(
        request.form["event_date"], "%Y-%m-%d"
    ).date()

    db.session.commit()
    return {"status": "ok"}


@events_bp.route("/delete/<int:event_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")

def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return {"status": "deleted"}
