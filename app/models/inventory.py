from app.extensions import db


class Department(db.Model):
    __tablename__ = "department"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    items = db.relationship("InventoryItem", backref="department", lazy=True)


class InventoryItem(db.Model):
    __tablename__ = "inventory_item"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    notes = db.Column(db.Text)

    department_id = db.Column(
        db.Integer,
        db.ForeignKey("department.id"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, server_default=db.func.now())
