from app.extensions import db

class SMSTemplate(db.Model):
    __tablename__ = "sms_templates"

    id = db.Column(db.Integer, primary_key=True)
    message_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint("message_type", "message", name="uq_sms_type_message"),
    )

