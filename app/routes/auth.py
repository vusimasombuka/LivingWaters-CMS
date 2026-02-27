from flask import Blueprint, render_template, redirect, url_for, request, abort
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app.decorators import role_required
from app.extensions import db
from flask import flash


auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/")
def index():
    """Redirect root URL to login page"""
    return redirect(url_for("auth.login"))

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

    if current_user.role == "super_admin":
        users = User.query.order_by(User.username).all()
    else:
        users = User.query.filter_by(
            branch_id=current_user.branch_id
        ).order_by(User.username).all()

    return render_template("users.html", users=users)


# ================= ADD USER =================
@auth_bp.route("/users/add", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def add_user():

    from app.models.branch import Branch
    from werkzeug.security import generate_password_hash

    # Super admin can see all branches
    if current_user.role == "super_admin":
        branches = Branch.query.order_by(Branch.name).all()
    else:
        # Admin can only assign users to their own branch
        branches = Branch.query.filter_by(
            id=current_user.branch_id
        ).all()

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        role = request.form["role"]
        branch_id = request.form.get("branch_id")

        if not branch_id:
            return "Branch is required", 400

        # 🔒 Admin cannot create super_admin
        if role == "super_admin" and current_user.role != "super_admin":
            abort(403)

        # 🔒 Admin cannot assign user to another branch
        if current_user.role != "super_admin":
            if int(branch_id) != current_user.branch_id:
                abort(403)

        existing = User.query.filter_by(username=username).first()
        if existing:
            return "Username already exists", 400

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            branch_id=int(branch_id)
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("auth.users_list"))

    return render_template("add_user.html", branches=branches)

# ================= EDIT USER =================
@auth_bp.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def edit_user(user_id):

    from app.models.branch import Branch
    from werkzeug.security import generate_password_hash

    user = User.query.get_or_404(user_id)

    # 🔒 Block cross-branch access (admin cannot edit other branches)
    if current_user.role != "super_admin":
        if user.branch_id != current_user.branch_id:
            abort(403)

    # 🔒 Admin cannot edit super_admin
    if user.role == "super_admin" and current_user.role != "super_admin":
        abort(403)

    # Super admin sees all branches
    if current_user.role == "super_admin":
        branches = Branch.query.order_by(Branch.name).all()
    else:
        # Admin only sees their own branch
        branches = Branch.query.filter_by(
            id=current_user.branch_id
        ).all()

    if request.method == "POST":
        role = request.form["role"]
        password = request.form.get("password")
        branch_id = request.form.get("branch_id")

        if not branch_id:
            return "Branch is required", 400

        # 🔒 Admin cannot assign super_admin role
        if role == "super_admin" and current_user.role != "super_admin":
            abort(403)

        # 🔒 Admin cannot move user to another branch
        if current_user.role != "super_admin":
            if int(branch_id) != current_user.branch_id:
                abort(403)

        user.role = role
        user.branch_id = int(branch_id)

        if password:
            user.password_hash = generate_password_hash(password)

        db.session.commit()
        return redirect(url_for("auth.users_list"))

    return render_template(
        "edit_user.html",
        user=user,
        branches=branches
    )


# ================= DELETE USER =================
@auth_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin", "super_admin")
def delete_user(user_id):

    user = User.query.get_or_404(user_id)

    # 🔒 Block cross-branch deletion (admin cannot delete other branches)
    if current_user.role != "super_admin":
        if user.branch_id != current_user.branch_id:
            abort(403)

    # 🔒 Super admin accounts can NEVER be deleted (by anyone)
    if user.role == "super_admin":
        flash("Super admin accounts cannot be deleted.", "error")
        return redirect(url_for("auth.users_list"))

    # 🔒 Prevent self-deletion
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("auth.users_list"))

    db.session.delete(user)
    db.session.commit()

    flash("User deleted successfully.", "success")
    return redirect(url_for("auth.users_list"))


# ================= BRANCH LIST =================
@auth_bp.route("/branches")
@login_required
@role_required("super_admin")
def branches_list():

    from app.models.branch import Branch

    branches = Branch.query.order_by(Branch.name).all()
    return render_template("branches.html", branches=branches)


# ================= ADD BRANCH =================
@auth_bp.route("/branches/add", methods=["GET", "POST"])
@login_required
@role_required("super_admin")
def add_branch():

    from app.models.branch import Branch

    if request.method == "POST":
        name = request.form["name"].strip()
        location = request.form["location"].strip()

        if not name:
            return "Branch name is required", 400

        existing = Branch.query.filter_by(name=name).first()
        if existing:
            return "Branch already exists", 400

        branch = Branch(name=name, location=location)
        db.session.add(branch)
        db.session.commit()

        return redirect(url_for("auth.branches_list"))

    return render_template("add_branch.html")


# ================= EDIT BRANCH =================
@auth_bp.route("/branches/edit/<int:branch_id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin")
def edit_branch(branch_id):

    from app.models.branch import Branch

    branch = Branch.query.get_or_404(branch_id)

    if request.method == "POST":
        name = request.form["name"].strip()
        location = request.form["location"].strip()

        if not name:
            return "Branch name is required", 400

        existing = Branch.query.filter(
            Branch.name == name,
            Branch.id != branch.id
        ).first()

        if existing:
            return "Another branch with this name already exists", 400

        branch.name = name
        branch.location = location

        db.session.commit()

        return redirect(url_for("auth.branches_list"))

    return render_template("edit_branch.html", branch=branch)


# ================= DELETE BRANCH =================
@auth_bp.route("/branches/delete/<int:branch_id>", methods=["POST"])
@login_required
@role_required("super_admin")
def delete_branch(branch_id):

    from app.models.branch import Branch
    from app.models.user import User

    branch = Branch.query.get_or_404(branch_id)

    # Safety check: prevent deletion if users exist
    users_count = User.query.filter_by(branch_id=branch.id).count()

    if users_count > 0:
        return "Cannot delete branch with assigned users", 400

    db.session.delete(branch)
    db.session.commit()

    return redirect(url_for("auth.branches_list"))


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    from app.models.user import User
    from app.models.branch import Branch
    from app.extensions import db
    from werkzeug.security import generate_password_hash
    from flask import abort, flash, render_template, redirect, url_for, request

    # Block if any user already exists
    if User.query.count() > 0:
        abort(403)

    if request.method == "POST":
        branch_name = request.form["branch_name"].strip()
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if not branch_name or not username or not password:
            flash("All fields are required.", "error")
            return render_template("setup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("setup.html")

        # Create branch
        branch = Branch(name=branch_name)
        db.session.add(branch)
        db.session.commit()

        # Create super admin - EXPLICITLY SET ROLE
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="super_admin",  # <-- MAKE SURE THIS IS HERE
            branch_id=branch.id
        )

        db.session.add(user)
        db.session.commit()

        flash("Setup complete! Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("setup.html")

# Add to auth.py or create admin.py

@auth_bp.route("/branches/<int:branch_id>/qr-code")
@login_required
@role_required("super_admin", "admin")
def branch_qr_code(branch_id):
    """Generate QR code for branch public check-in"""
    from app.models.branch import Branch
    
    branch = Branch.query.get_or_404(branch_id)
    
    # Security check
    if current_user.role != "super_admin" and branch.id != current_user.branch_id:
        abort(403)
    
    # Generate token if missing
    if not branch.public_token:
        branch.generate_token()
        db.session.commit()
    
    public_url = url_for('checkin.public_check_in', 
                        token=branch.public_token, 
                        _external=True)
    
    return render_template("admin/branch_qr.html", 
                         branch=branch, 
                         public_url=public_url,
                         qr_code_url=f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={public_url}")