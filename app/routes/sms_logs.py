from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.decorators import role_required
from app.models.sms_log import SMSLog  # Import the model, don't define it here
from app.extensions import db
from app.utils.branching import branch_query, enforce_branch_access

sms_logs_bp = Blueprint("sms_logs", __name__, url_prefix="/sms-logs")

@sms_logs_bp.route("/", methods=["GET"])
@login_required
@role_required("super_admin", "admin", "finance")
def list_sms_logs():
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status")
    
    # Use branch_query for isolation
    query = branch_query(SMSLog).order_by(SMSLog.created_at.desc())

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
    enforce_branch_access(sms)  # Ensure user owns this SMS

    if sms.status == "failed":
        sms.status = "pending"
        sms.error = None
        db.session.commit()

    return redirect(url_for("sms_logs.list_sms_logs"))