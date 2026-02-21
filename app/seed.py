from app.extensions import db
from app.models.lookup import Lookup

def seed_lookup():
    if Lookup.query.count() == 0:
        default_data = [
            ("department", "Administration"),
            ("department", "Music"),
            ("department", "Media"),
            ("department", "Ushering"),
            ("department", "Finance"),
            ("department", "Children"),
            ("department", "Security"),
            ("title", "Mr"),
            ("title", "Mrs"),
            ("title", "Miss"),
            ("title", "Pastor"),
            ("title", "Bishop"),
            ("marital_status", "Single"),
            ("marital_status", "Married"),
            ("marital_status", "Divorced"),
            ("marital_status", "Widowed"),
            ("offering_type", "Tithe"),
            ("offering_type", "Offering"),
            ("offering_type", "Donation"),
        ]

        for category, value in default_data:
            db.session.add(Lookup(category=category, value=value))

        db.session.commit()