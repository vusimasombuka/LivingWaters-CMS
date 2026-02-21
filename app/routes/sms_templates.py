from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.decorators import role_required
from app.extensions import db
from app.models.sms_template import SMSTemplate
from app.models.lookup import Lookup  # make sure this import exists at top



sms_templates_bp = Blueprint(
    "sms_templates",
    __name__,
    url_prefix="/sms-templates"
)


# =========================
# LIST TEMPLATES
# =========================
from app.models.lookup import Lookup


@sms_templates_bp.route("/")
@login_required
@role_required("admin", "super_admin")
def list_templates():
    
    templates = SMSTemplate.query.order_by(SMSTemplate.id.desc()).all()

    # Count active templates per message type
    from sqlalchemy import func

    counts = dict(
        db.session.query(
            SMSTemplate.message_type,
            func.count(SMSTemplate.id)
        )
        .filter(SMSTemplate.active == True)
        .group_by(SMSTemplate.message_type)
        .all()
    )

    offering_types = Lookup.query.filter_by(category="offering_type").all()
    sms_types = Lookup.query.filter_by(category="sms_type").all()
    message_types = offering_types + sms_types

    return render_template(
        "sms_templates.html",
        templates=templates,
        template_counts=counts,
        message_types=message_types
    )




# =========================
# ADD TEMPLATE
# =========================
@sms_templates_bp.route("/add", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def add_template():

    message_type = request.form.get("message_type").lower()
    message = request.form.get("message")

    if not message_type or not message:
        flash("Message type and message are required.", "error")
        return redirect(url_for("sms_templates.list_templates"))

    template = SMSTemplate(
        message_type=message_type,
        message=message,
        active=True
    )

    db.session.add(template)
    db.session.commit()

    flash("SMS template added.", "success")
    return redirect(url_for("sms_templates.list_templates"))


# =========================
# TOGGLE ACTIVE
# =========================
@sms_templates_bp.route("/toggle/<int:template_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def toggle_template(template_id):

    template = SMSTemplate.query.get_or_404(template_id)
    template.active = not template.active
    db.session.commit()

    return redirect(url_for("sms_templates.list_templates"))



# =========================
# DELETE TEMPLATE
# =========================
@sms_templates_bp.route("/delete/<int:template_id>", methods=["POST"])
@login_required
@role_required("admin", "super_admin")
def delete_template(template_id):

    template = SMSTemplate.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()

    flash("Template deleted successfully.", "success")
    return redirect(url_for("sms_templates.list_templates"))



@sms_templates_bp.route("/edit/<int:template_id>", methods=["GET", "POST"])
@login_required
@role_required("admin", "super_admin")
def edit_template(template_id):

    template = SMSTemplate.query.get_or_404(template_id)

    if request.method == "POST":
        template.message = request.form.get("message")
        db.session.commit()
        flash("Template updated successfully.", "success")
        return redirect(url_for("sms_templates.list_templates"))

    return render_template(
        "sms_templates_edit.html",
        template=template
    )
