from app.extensions import db
from datetime import datetime

class SMSLog(db.Model):
    __tablename__ = "sms_logs"

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    message_type = db.Column(db.String(50), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), default="pending", index=True)  # pending | sent | failed
    error = db.Column(db.Text, nullable=True)

    related_table = db.Column(db.String(50), nullable=True)  # giving | check_in
    related_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id", name="fk_sms_logs_branch_id"))
    template_id = db.Column(db.Integer, db.ForeignKey("sms_templates.id"), nullable=True)
