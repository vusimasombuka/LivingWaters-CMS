from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.decorators import role_required
from app.extensions import db
from app.models.member import Member
from app.models.visitor import Visitor
from datetime import datetime
from app.utils import normalize_sa_phone

members_bp = Blueprint("members", __name__, url_prefix="/members")

@members_bp.route("/")
@login_required
@role_required("super_admin", "admin")
def list_members():

    page = request.args.get("page", 1, type=int)

    members = Member.query.filter_by(
        branch_id=current_user.branch_id
).order_by(Member.created_at.desc()).paginate(page=page, per_page=25)


    return render_template("members.html", members=members)


@members_bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def add_member():

    if request.method == "POST":

        from app.utils import normalize_sa_phone
        from datetime import datetime

        phone = normalize_sa_phone(request.form.get("phone"))
        if not phone:
            return "Phone number is required", 400

        # 🔒 CHECK IF VISITOR WITH THIS PHONE EXISTS
        existing_visitor = Visitor.query.filter_by(phone=phone).first()
        if existing_visitor:
            flash(
                f'A visitor with this phone already exists. '
                f'<a href="{url_for("visitors.visitors_list")}" style="color: #856404; text-decoration: underline;">Click here to convert visitor</a>',
                "error"
            )
            return redirect(url_for("members.add_member"))

        # 🔒 CHECK IF MEMBER WITH THIS PHONE EXISTS
        existing_member = Member.query.filter_by(phone=phone).first()
        if existing_member:
            flash(
                f"A member with this phone number already exists: {existing_member.first_name} {existing_member.last_name}.",
                "error"
            )
            return redirect(url_for("members.add_member"))

        member = Member(
            title=request.form.get("title"),
            first_name=request.form.get("first_name"),
            last_name=request.form.get("last_name"),
            gender=request.form.get("gender"),
            phone=phone,
            email=request.form.get("email"),
            street_address=request.form.get("street_address"),
            section=request.form.get("section"),

            # ✅ FIXED FIELDS
            marital_status=request.form.get("marital_status"),
            occupation=request.form.get("occupation"),

            date_of_birth=(
                datetime.strptime(request.form.get("date_of_birth"), "%Y-%m-%d").date()
                if request.form.get("date_of_birth")
                else None
            ),

            department=request.form.get("department"),
            member_status=request.form.get("member_status"),

            membership_course=True if request.form.get("membership_course") else False,
            baptized=True if request.form.get("baptized") else False,

            emergency_contact_name=request.form.get("emergency_contact_name"),
            emergency_contact_phone=request.form.get("emergency_contact_phone"),
            branch_id=current_user.branch_id

        )

        db.session.add(member)
        db.session.commit()

        flash(f"Member {member.first_name} {member.last_name} added successfully.", "success")
        return redirect(url_for("members.list_members"))

    from app.models.lookup import Lookup

    departments = Lookup.query.filter_by(category="department").all()
    titles = Lookup.query.filter_by(category="title").all()
    marital_statuses = Lookup.query.filter_by(category="marital_status").all()

    return render_template(
    "add_member.html",
    departments=departments,
    titles=titles,
    marital_statuses=marital_statuses
)




@members_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def edit_member(id):

    member = Member.query.get_or_404(id)

    if request.method == "POST":

        member.title = request.form.get("title")
        member.first_name = request.form.get("first_name")
        member.last_name = request.form.get("last_name")
        member.gender = request.form.get("gender")
        
        new_phone = normalize_sa_phone(request.form.get("phone"))
        
        # 🔒 CHECK IF NEW PHONE EXISTS ON ANOTHER MEMBER OR VISITOR (excluding current member)
        if new_phone != member.phone:
            existing_member = Member.query.filter(Member.phone == new_phone, Member.id != id).first()
            existing_visitor = Visitor.query.filter_by(phone=new_phone).first()
            
            if existing_member:
                flash(f"Phone number already exists on another member: {existing_member.first_name} {existing_member.last_name}", "error")
                return redirect(url_for("members.edit_member", id=id))
            
            if existing_visitor:
                flash(f"Phone number exists on a visitor record. Please convert the visitor first.", "warning")
                return redirect(url_for("visitors.visitors_list"))
        
        member.phone = new_phone
        member.email = request.form.get("email")
        member.street_address = request.form.get("street_address")
        member.section = request.form.get("section")

        member.date_of_birth = (
            datetime.strptime(request.form.get("date_of_birth"), "%Y-%m-%d").date()
            if request.form.get("date_of_birth")
            else None
        )

        member.marital_status = request.form.get("marital_status")
        member.occupation = request.form.get("occupation")
        member.department = request.form.get("department")
        member.member_status = request.form.get("member_status")
        member.membership_course = bool(request.form.get("membership_course"))
        member.baptized = bool(request.form.get("baptized"))
        member.emergency_contact_name = request.form.get("emergency_contact_name")
        member.emergency_contact_phone = normalize_sa_phone(
            request.form.get("emergency_contact_phone")
        )

        db.session.commit()
        flash("Member updated successfully.", "success")
        return redirect(url_for("members.list_members"))

    # ✅ ADD THIS PART (lookup data for dropdowns)
    from app.models.lookup import Lookup

    departments = Lookup.query.filter_by(category="department").all()
    titles = Lookup.query.filter_by(category="title").all()
    marital_statuses = Lookup.query.filter_by(category="marital_status").all()

    return render_template(
        "edit_member.html",
        member=member,
        departments=departments,
        titles=titles,
        marital_statuses=marital_statuses
    )