from app.extensions import db
from datetime import date, datetime

class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    phone = db.Column(db.String(20), nullable=False)
    
    check_in_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    visitor_id = db.Column(db.Integer, db.ForeignKey("visitor.id"))
    member_id = db.Column(db.Integer, db.ForeignKey("member.id"))
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    service = db.relationship("Service")



    __table_args__ = (
    db.UniqueConstraint(
        "phone",
        "service_id",
        "check_in_date",
        name="unique_checkin_per_service_per_day"
    ),
)

