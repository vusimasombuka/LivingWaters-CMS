from app.extensions import db
from datetime import datetime

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(20))
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(20))

    phone = db.Column(db.String(15), nullable=True, index=True)  # CHANGED: nullable=True
    email = db.Column(db.String(120))
    
    # ADD THESE FIELDS
    alternative_contact = db.Column(db.String(100))  # Email, WhatsApp, relative's phone
    id_number = db.Column(db.String(20), unique=True, nullable=True)  # SA ID/Passport

    street_address = db.Column(db.Text)
    section = db.Column(db.String(100))

    date_of_birth = db.Column(db.Date)
    marital_status = db.Column(db.String(50))
    occupation = db.Column(db.String(100))

    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(15))

    membership_course = db.Column(db.Boolean, default=False)
    baptized = db.Column(db.Boolean, default=False)

    department = db.Column(db.String(100))
    member_status = db.Column(db.String(20), default="active")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_birthday_sms_year = db.Column(db.Integer)

    branch_id = db.Column(
        db.Integer,
        db.ForeignKey("branches.id", name="fk_member_branch_id"),
        nullable=True  # ADDED: nullable for phone-less members
    )