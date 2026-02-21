from flask import Blueprint, current_app
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models.user import User
from flask import abort
from flask_login import login_required
from app.decorators import role_required


bootstrap_bp = Blueprint("bootstrap", __name__)

@bootstrap_bp.route("/bootstrap-super-admin")
@login_required
@role_required("super_admin")
def bootstrap_super_admin():


    if not current_app.config.get("EMERGENCY_ACCESS"):
        abort(403)


    existing = User.query.filter_by(username="superadmin").first()
    if existing:
        return "Super admin already exists"

    user = User(
        username="superadmin",
        password_hash=generate_password_hash("ChangeMeNow123!"),
        role="super_admin"
    )

    db.session.add(user)
    db.session.commit()

    return "Super admin created"
