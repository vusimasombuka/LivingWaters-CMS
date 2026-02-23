from app.extensions import db
from datetime import datetime

class Giving(db.Model):
    __tablename__ = "giving"

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(
    db.Integer,
    db.ForeignKey("branches.id", name="fk_giving_branch_id"),
    nullable=False
)


    phone = db.Column(db.String(20), nullable=True, index=True)
    giver_name = db.Column(db.String(150), nullable=True)

    member_id = db.Column(
        db.Integer,
        db.ForeignKey("member.id"),
        nullable=True
    )

    visitor_id = db.Column(
        db.Integer,
        db.ForeignKey("visitor.id"),
        nullable=True
    )

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    giving_type = db.Column(db.String(50), nullable=False, index=True)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ RELATIONSHIPS (THIS IS THE KEY)
    member = db.relationship("Member", backref="givings")
    visitor = db.relationship("Visitor", backref="givings")
    