from app import create_app
from app.extensions import db
from app.models.sms_template import SMSTemplate
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


app = create_app()

with app.app_context():

    templates = [
        # TITHE (Malachi 3:10)
        ("tithe", "Thank you for honoring God with your tithe.", "Malachi 3:10"),
        ("tithe", "We appreciate your faithfulness in giving.", "Malachi 3:10"),
        ("tithe", "Your tithe makes ministry possible.", "Malachi 3:10"),

        # OFFERING (2 Corinthians 9:7)
        ("offering", "Thank you for your generous offering.", "2 Corinthians 9:7"),
        ("offering", "Your giving makes a difference.", "2 Corinthians 9:7"),
        ("offering", "We appreciate your cheerful giving.", "2 Corinthians 9:7"),

        # DONATION (Proverbs 19:17)
        ("donation", "Thank you for your kind donation.", "Proverbs 19:17"),
        ("donation", "Your generosity is appreciated.", "Proverbs 19:17"),
        ("donation", "Thank you for supporting the work of God.", "Proverbs 19:17"),
    ]

    for category, message, scripture in templates:
        exists = SMSTemplate.query.filter_by(
            category=category,
            message=message
        ).first()

        if not exists:
            db.session.add(SMSTemplate(
                category=category,
                message=message,
                scripture=scripture
            ))

    db.session.commit()
    print("✅ SMS templates seeded")
