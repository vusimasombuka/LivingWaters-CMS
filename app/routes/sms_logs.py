from flask import Blueprint, render_template, request, redirect, url_for

from flask_login import login_required
from app.decorators import role_required
from app.models.sms_log import SMSLog
from app.extensions import db


sms_logs_bp = Blueprint(
    "sms_logs",
    __name__,
    url_prefix="/sms-logs"
)


@sms_logs_bp.route("/", methods=["GET"])
@login_required
@role_required("super_admin", "admin", "finance")
def list_sms_logs():

    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status")

    query = SMSLog.query.order_by(SMSLog.created_at.desc())

    if status_filter:
        query = query.filter_by(status=status_filter)

    logs = query.paginate(page=page, per_page=50)

    return render_template(
        "sms_logs.html",
        logs=logs,
        status_filter=status_filter
    )


@sms_logs_bp.route("/retry/<int:sms_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def retry_sms(sms_id):

    sms = SMSLog.query.get_or_404(sms_id)

    if sms.status == "failed":
        sms.status = "pending"
        sms.error = None
        db.session.commit()

    return redirect(url_for("sms_logs.list_sms_logs"))


test_sms_bp = Blueprint("test_sms", __name__)

@test_sms_bp.route("/test-sms")
def test_sms():

    sms = SMSLog(
        phone="+2782XXXXXXX",  # <-- PUT YOUR REAL NUMBER
        message="This is a live SMS test from the CMS system.",
        message_type="test",
        related_table="test",
        related_id=1,
        status="pending"
    )

    db.session.add(sms)
    db.session.commit()
  

    return "Test SMS created as pending."