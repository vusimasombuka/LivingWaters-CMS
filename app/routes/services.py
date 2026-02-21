from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.extensions import db
from app.models.service import Service
from app.decorators import role_required


services_bp = Blueprint("services", __name__, url_prefix="/services")




@services_bp.route("/")
@login_required
@role_required("admin", "super_admin")
def list_services():
    services = Service.query.order_by(Service.id.desc()).all()
    return render_template("services/list.html", services=services)


@services_bp.route("/add", methods=["POST"])
@login_required
@role_required("admin", "super_admin")
def add_service():

    name = request.form.get("name")
    day_of_week = request.form.get("day_of_week")
    time = request.form.get("time")

    if not name or not day_of_week or not time:
        flash("All fields are required.", "error")
        return redirect(url_for("services.list_services"))

    # 🔒 DUPLICATE CHECK (ADD THIS SECTION)
    existing = Service.query.filter_by(
        name=name,
        day_of_week=day_of_week,
        time=time
    ).first()

    if existing:
        flash("This service already exists.", "warning")
        return redirect(url_for("services.list_services"))

    # ✅ CREATE SERVICE
    service = Service(
        name=name,
        day_of_week=day_of_week,
        time=time,
        active=True
    )

    db.session.add(service)
    db.session.commit()

    flash("Service added successfully.", "success")
    return redirect(url_for("services.list_services"))



@services_bp.route("/services/toggle/<int:service_id>", methods=["POST"])
@login_required
@role_required("admin", "super_admin")
def toggle_service(service_id):

    service = Service.query.get_or_404(service_id)
    service.active = not service.active
    db.session.commit()

    flash("Service status updated successfully.", "success")
    return redirect(url_for("services.list_services"))



@services_bp.route("/services/delete/<int:service_id>", methods=["POST"])
@login_required
@role_required("admin", "super_admin")
def delete_service(service_id):

    service = Service.query.get_or_404(service_id)

    db.session.delete(service)
    db.session.commit()

    flash("Service deleted successfully.", "success")
    return redirect(url_for("services.list_services"))


