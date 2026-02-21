from datetime import date, timedelta
from app.extensions import db
from app.models.sms_log import SMSLog
from app.models.service import Service
from app.models.check_in import CheckIn


def visitor_followup_job():
    """
    Sends one follow-up SMS per visitor per week
    """

    today = date.today()

    # Only run on Mondays
    if today.weekday() != 0:
        return

    # Get active services
    services = Service.query.filter_by(active=True).all()

    if not services:
        return

    services_text = "; ".join(
        f"{s.name}: {s.day_of_week} {s.time}" for s in services
    )

    # Visitors who checked in last 7 days AND have phone
    recent_checkins = CheckIn.query.filter(
        CheckIn.visitor_id.isnot(None),
        CheckIn.phone.isnot(None),  # ADDED: Only with phone
        CheckIn.created_at >= today - timedelta(days=7)
    ).all()

    for checkin in recent_checkins:

        # Avoid duplicate weekly follow-ups
        already_sent = SMSLog.query.filter(
            SMSLog.phone == checkin.phone,
            SMSLog.message_type == "visitor_followup",
            SMSLog.created_at >= today - timedelta(days=7)
        ).first()

        if already_sent:
            continue

        sms = SMSLog(
            phone=checkin.phone,
            message=f"We would love to see you again! Upcoming services: {services_text}",
            message_type="visitor_followup",
            related_table="check_in",
            related_id=checkin.id,
            status="pending"
        )

        db.session.add(sms)

    db.session.commit()