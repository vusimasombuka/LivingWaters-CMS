"""
One-time import script for Living Waters Bible Church – 2026 Calendar
Mode: PREVIEW first, then COMMIT manually
"""
import sys
import os
from datetime import date

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, BASE_DIR)

from app import create_app
from app.extensions import db
from app.models.event import Event


# =========================
# CONFIGURATION
# =========================

YEAR = 2026
DEPARTMENT = "Church"

MODE = "COMMIT"  # change to "COMMIT" only after review


# =========================
# CALENDAR DATA (APPROVED)
# =========================

CALENDAR_2026 = {
    # JANUARY
    "2026-01-01": "New Year’s Day",
    "2026-01-04": "Communion Sunday",
    "2026-01-11": "Membership Class",
    "2026-01-18": "Fasting & Prayer",
    "2026-01-19": "Fasting & Prayer",
    "2026-01-20": "Fasting & Prayer",
    "2026-01-21": "Fasting & Prayer",
    "2026-01-22": "Fasting & Prayer",
    "2026-01-23": "Fasting & Prayer",
    "2026-01-24": "Fasting & Prayer",
    "2026-01-25": "Fasting & Prayer",
    "2026-01-25": "Youth Sunday",
    "2026-01-31": "Workers Prayer",

    # FEBRUARY
    "2026-02-01": "Communion Sunday",
    "2026-02-08": "Membership Class",
    "2026-02-14": "Valentine’s Day",
    "2026-02-15": "Youth Sunday",
    "2026-02-22": "Baptism",

    # MARCH
    "2026-03-01": "Communion Sunday",
    "2026-03-08": "Membership Class",
    "2026-03-15": "Youth Sunday",
    "2026-03-21": "Human Rights Day",
    "2026-03-22": "Baptism",

    # APRIL
    "2026-04-03": "Good Friday",
    "2026-04-04": "Passover Conference",
    "2026-04-05": "Passover Conference",
    "2026-04-06": "Passover Conference",
    "2026-04-06": "Family Day",
    "2026-04-12": "Membership Class",
    "2026-04-19": "Youth Sunday",

    # MAY
    "2026-05-01": "Workers Day",
    "2026-05-03": "Communion Sunday",
    "2026-05-10": "Mother’s Day",
    "2026-05-17": "Youth Sunday",
    "2026-05-24": "Membership Class",

    # JUNE
    "2026-06-07": "Communion Sunday",
    "2026-06-14": "Youth Sunday",
    "2026-06-16": "Youth Day",
    "2026-06-21": "Father’s Day",
    "2026-06-28": "Baptism",

    # JULY
    "2026-07-05": "Communion Sunday",
    "2026-07-12": "Membership Class",
    "2026-07-18": "Mandela Day",
    "2026-07-19": "Youth Sunday",
    "2026-07-26": "Workers Prayer",

    # AUGUST
    "2026-08-02": "Communion Sunday",
    "2026-08-09": "Women’s Day",
    "2026-08-09": "Membership Class",
    "2026-08-16": "Youth Sunday",
    "2026-08-30": "Women’s Month Celebration",

    # SEPTEMBER
    "2026-09-06": "Communion Sunday",
    "2026-09-13": "Membership Class",
    "2026-09-16": "Youth Sunday",
    "2026-09-24": "Heritage Day",
    "2026-09-27": "Baptism",

    # OCTOBER
    "2026-10-04": "Communion Sunday",
    "2026-10-11": "Membership Class",
    "2026-10-18": "Youth Sunday",

    # NOVEMBER
    "2026-11-01": "Communion Sunday",
    "2026-11-08": "Membership Class",
    "2026-11-15": "Youth Sunday",
    "2026-11-16": "Fasting & Prayer",
    "2026-11-17": "Fasting & Prayer",
    "2026-11-18": "Fasting & Prayer",
    "2026-11-19": "Fasting & Prayer",
    "2026-11-20": "Fasting & Prayer",
    "2026-11-21": "Fasting & Prayer",
    "2026-11-22": "Fasting & Prayer",
    "2026-11-29": "Thanksgiving Sunday",

    # DECEMBER
    "2026-12-06": "Communion Sunday",
    "2026-12-13": "Youth Sunday",
    "2026-12-16": "Day of Reconciliation",
    "2026-12-20": "Carol Service",
    "2026-12-25": "Christmas Day",
    "2026-12-27": "Year End Thanksgiving",
}


# =========================
# IMPORT LOGIC
# =========================

def run_import():
    app = create_app()

    with app.app_context():
        to_create = []

        for d, title in CALENDAR_2026.items():
            yyyy, mm, dd = map(int, d.split("-"))
            event_date = date(yyyy, mm, dd)

            exists = Event.query.filter_by(
                event_date=event_date,
                title=title
            ).first()

            if exists:
                continue

            to_create.append(Event(
                title=title,
                event_date=event_date,
                department=DEPARTMENT
            ))

        print(f"\nCalendar Year: {YEAR}")
        print(f"Mode: {MODE}")
        print(f"Events to create: {len(to_create)}\n")

        for e in to_create[:10]:
            print(f"{e.event_date} → {e.title}")

        if MODE == "PREVIEW":
            print("\nPREVIEW MODE — no data written.")
            print("Change MODE = 'COMMIT' to insert events.")
            return

        if MODE == "COMMIT":
            db.session.add_all(to_create)
            db.session.commit()
            print("\nIMPORT COMPLETE — events inserted safely.")


if __name__ == "__main__":
    run_import()
