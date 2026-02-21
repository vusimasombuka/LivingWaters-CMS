from app.models.sms_template import SMSTemplate
from app.models.sms_log import SMSLog
from app.extensions import db

def get_next_sms_template(phone: str, category: str):
    """
    Returns next SMS template for a phone + category (rotation safe)
    """

    templates = SMSTemplate.query.filter_by(
        category=category,
        active=True
    ).order_by(SMSTemplate.id.asc()).all()

    if not templates:
        return None

    last_log = SMSLog.query.filter_by(
        phone=phone,
        category=category
    ).order_by(SMSLog.id.desc()).first()

    if not last_log:
        return templates[0]

    for template in templates:
        if template.id > last_log.template_id:
            return template

    # Loop back to first
    return templates[0]
