from app.extensions import db

class Lookup(db.Model):
    __tablename__ = "lookup"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    value = db.Column(db.String(100), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)

    __table_args__ = (
        db.UniqueConstraint("category", "value", name="uq_lookup_category_value"),
    )
