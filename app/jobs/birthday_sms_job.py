from datetime import date
from app.extensions import db
from app.models.member import Member
from app.models.visitor import Visitor  # ADD THIS
from app.models.sms_log import SMSLog
from app.services.sms_rotation_service import get_rotated_template


def birthday_sms_job():
    today = date.today()

    # ================= MEMBERS =================
    members = Member.query.filter(
        Member.date_of_birth.isnot(None),
        Member.phone.isnot(None)  # ADDED: Only those with phones
    ).all()

    for member in members:
        process_birthday_person(member, "member", today)

    # ================= VISITORS =================
    visitors = Visitor.query.filter(
        Visitor.date_of_birth.isnot(None),
        Visitor.phone.isnot(None)  # ADDED: Only those with phones
    ).all()

    for visitor in visitors:
        process_birthday_person(visitor, "visitor", today)

    db.session.commit()


def process_birthday_person(person, person_type, today):
    """Helper function to process birthday for both members and visitors"""
    
    # Double-check phone exists
    if not person.phone:
        return
    
    if (
        person.date_of_birth.month == today.month
        and person.date_of_birth.day == today.day
    ):

        already_sent = SMSLog.query.filter(
            SMSLog.phone == person.phone,
            SMSLog.message_type == "birthday",
            db.extract("year", SMSLog.created_at) == today.year,
        ).first()

        if already_sent:
            return

        # ===== TEMPLATE ROTATION =====
        template = get_rotated_template(person.phone, "birthday")

        if not template:
            return

        message = template.message.replace("{name}", person.first_name)

        sms = SMSLog(
            phone=person.phone,
            message=message,
            message_type="birthday",
            related_table=person_type,
            related_id=person.id,
            status="pending",
            branch_id=getattr(person, 'branch_id', 1),
            template_id=template.id
        )

        db.session.add(sms)


def process_birthday_person(person, person_type, today):
    """Helper function to process birthday for both members and visitors"""
    
    if (
        person.date_of_birth.month == today.month
        and person.date_of_birth.day == today.day
    ):

        already_sent = SMSLog.query.filter(
            SMSLog.phone == person.phone,
            SMSLog.message_type == "birthday",
            db.extract("year", SMSLog.created_at) == today.year,
        ).first()

        if already_sent:
            return

        # ===== TEMPLATE ROTATION =====
        template = get_rotated_template(person.phone, "birthday")

        if not template:
            return

        message = template.message.replace("{name}", person.first_name)

        sms = SMSLog(
            phone=person.phone,
            message=message,
            message_type="birthday",
            related_table=person_type,
            related_id=person.id,
            status="pending",
            branch_id=getattr(person, 'branch_id', 1),
            template_id=template.id
        )

        db.session.add(sms)