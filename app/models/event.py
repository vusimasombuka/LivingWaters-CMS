from app.extensions import db
from datetime import date

class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    department = db.Column(db.String(100))
    description = db.Column(db.Text)

    def __repr__(self):
        return f"<Event {self.title} on {self.event_date}>"
