from datetime import date, timedelta
from app.extensions import db
from app.models.member import Member
from app.models.visitor import Visitor
from app.models.check_in import CheckIn
from app.models.sms_log import SMSLog
from app.services.sms_rotation_service import get_rotated_template


def absentees_followup_job():

    today = date.today()
    inactivity_cutoff = today - timedelta(days=14)

    def process_person(person, person_type):
        
        # SKIP IF NO PHONE
        if not person.phone:
            return

        last_checkin = (
            CheckIn.query.filter_by(**{f"{person_type}_id": person.id})
            .order_by(CheckIn.check_in_date.desc())
            .first()
        )

        # Must have checked in before AND be inactive for 14 days
        if not last_checkin or last_checkin.check_in_date > inactivity_cutoff:
            return

        # Get all previous follow-up SMS
        previous_sms = (
            SMSLog.query.filter_by(
                phone=person.phone,
                message_type="absentees_follow_up"
            )
            .order_by(SMSLog.created_at.desc())
            .all()
        )

        # Stop permanently after 3
        if len(previous_sms) >= 3:
            return

        # If already sent before, ensure 7 days spacing
        if previous_sms:
            last_sms_date = previous_sms[0].created_at.date()
            if today < last_sms_date + timedelta(days=7):
                return

        template = get_rotated_template(person.phone, "absentees_follow_up")
        if not template:
            return

        message = template.message.replace("{name}", person.first_name)

        sms = SMSLog(
            phone=person.phone,
            message=message,
            message_type="absentees_follow_up",
            related_table=person_type,
            related_id=person.id,
            status="pending",
            branch_id=1,
            template_id=template.id
        )

        db.session.add(sms)

    # Process members
    for member in Member.query.filter(Member.phone.isnot(None)).all():  # ADDED: phone filter
        process_person(member, "member")

    # Process visitors
    for visitor in Visitor.query.filter(Visitor.phone.isnot(None)).all():  # ADDED: phone filter
        process_person(visitor, "visitor")

    db.session.commit()
