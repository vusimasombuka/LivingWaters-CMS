from flask import Blueprint, render_template, redirect, url_for, request, abort
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app.decorators import role_required
from app.extensions import db
from flask import flash


auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    from flask import current_app

    if User.query.count() == 0:
        return redirect(url_for("auth.setup"))

    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()

        if not user or not check_password_hash(
            user.password_hash,
            request.form["password"]
        ):
            return "Invalid credentials", 401

        login_user(user)

        # ROLE-BASED REDIRECT
        if user.role in ("super_admin", "admin"):
            return redirect(url_for("auth.dashboard"))

        if user.role == "usher":
            return redirect(url_for("checkin.check_in"))

        if user.role == "finance":
            return redirect(url_for("giving.giving_dashboard"))

        # Unknown role = block
        abort(403)

    return render_template("login.html")


@auth_bp.route("/dashboard")
@login_required
@role_required("super_admin", "admin", "finance")
def dashboard():
    return render_template(
        "dashboard.html",
        user=current_user
    )


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user


# ================= USERS LIST =================
@auth_bp.route("/users", methods=["GET"])
@login_required
@role_required("super_admin", "admin")
def users_list():
    users = User.query.order_by(User.username).all()
    return render_template("users.html", users=users)


# ================= ADD USER =================
@auth_bp.route("/users/add", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def add_user():

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        role = request.form["role"]

        if role == "super_admin":
            abort(403)

        existing = User.query.filter_by(username=username).first()
        if existing:
            return "Username already exists", 400

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("auth.users_list"))

    return render_template("add_user.html")


# ================= EDIT USER =================
@auth_bp.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def edit_user(user_id):

    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        role = request.form["role"]
        password = request.form.get("password")

        # Prevent super_admin changes
        if user.role == "super_admin":
            abort(403)

        # Update role
        user.role = role

        # Update password only if provided
        if password:
            user.password_hash = generate_password_hash(password)

        db.session.commit()
        return redirect(url_for("auth.users_list"))

    return render_template("edit_user.html", user=user)


# ================= DELETE USER =================
@auth_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin", "super_admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.username == "superadmin":
        flash("Superadmin cannot be deleted", "error")
        return redirect(url_for("auth.users_list"))

    if user.id == current_user.id:
        flash("You cannot delete your own account", "error")
        return redirect(url_for("auth.users_list"))

    db.session.delete(user)
    db.session.commit()

    flash("User deleted successfully", "success")
    return redirect(url_for("auth.users_list"))

@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():

    from app.models.user import User
    from werkzeug.security import generate_password_hash
    from app.extensions import db

    # Block access if a user already exists
    if User.query.count() > 0:
        abort(403)

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # Basic validation
        if not username or not password:
            flash("All fields are required.", "error")
            return render_template("setup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("setup.html")

        # Create super admin
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="super_admin"
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("auth.login"))

    return render_template("setup.html")