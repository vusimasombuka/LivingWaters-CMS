from app.models.sms_template import SMSTemplate
from app.models.sms_log import SMSLog


def get_rotated_template(phone: str, message_type: str):
    """
    Returns next rotated template for a phone + message_type.
    """

    templates = SMSTemplate.query.filter_by(
        message_type=message_type.lower(),
        active=True
    ).order_by(SMSTemplate.id.asc()).all()

    if not templates:
        return None

    last_sms = SMSLog.query.filter_by(
        phone=phone,
        message_type=message_type.lower()
    ).order_by(SMSLog.id.desc()).first()

    if not last_sms or not last_sms.template_id:
        return templates[0]

    for t in templates:
        if t.id > last_sms.template_id:
            return t

    return templates[0]
