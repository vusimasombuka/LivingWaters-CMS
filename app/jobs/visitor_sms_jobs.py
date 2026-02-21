from datetime import datetime, timedelta
from app.extensions import db
from app.models.sms_log import SMSLog

def mark_visitor_sms_ready():
    """
    Marks visitor SMS as ready after 4 hours
    """

    four_hours_ago = datetime.utcnow() - timedelta(hours=4)

    sms_list = SMSLog.query.filter(
        SMSLog.message_type == "visitor_thank_you",
        SMSLog.status == "pending",
        SMSLog.created_at <= four_hours_ago
    ).all()

    for sms in sms_list:
        sms.status = "pending"

    if sms_list:
        db.session.commit()
