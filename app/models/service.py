from app.extensions import db

class Service(db.Model):
    __tablename__ = "services"

    __table_args__ = (
        db.UniqueConstraint(
            'name',
            'day_of_week',
            'time',
            name='unique_service_per_day_time'
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    day_of_week = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, default=True)
