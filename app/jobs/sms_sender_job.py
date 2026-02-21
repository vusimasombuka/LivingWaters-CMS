from app.extensions import db
from app.models.sms_log import SMSLog
from app.services.clickatell_service import send_sms


def send_ready_sms():
    messages = SMSLog.query.filter_by(status="pending").all()


    for sms in messages:
        try:
            send_sms(
                phone=sms.phone,
                message=sms.message,
            )
            sms.status = "sent"
            sms.error = None

        except Exception as e:
            sms.status = "failed"
            sms.error = str(e)

    db.session.commit()
