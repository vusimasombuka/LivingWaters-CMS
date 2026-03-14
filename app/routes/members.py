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
    from app.utils.branching import branch_query
    from sqlalchemy import or_, asc, desc

    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "").strip()
    sort_order = request.args.get("sort", "asc")  # Default: A-Z

    # Base query with branch isolation
    query = branch_query(Member)

    # SEARCH: Filter by name or phone
    if search:
        search_filter = or_(
            Member.first_name.ilike(f"%{search}%"),
            Member.last_name.ilike(f"%{search}%"),
            Member.phone.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    # SORT: By surname (last_name), then first_name
    if sort_order == "desc":
        query = query.order_by(desc(Member.last_name), desc(Member.first_name))
    else:
        query = query.order_by(asc(Member.last_name), asc(Member.first_name))

    members = query.paginate(page=page, per_page=25)

    return render_template(
        "members.html", 
        members=members, 
        search=search, 
        sort_order=sort_order
    )


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
    member_statuses = Lookup.query.filter_by(category="member_status").all()

    return render_template(
        "add_member.html",
        departments=departments,
        titles=titles,
        marital_statuses=marital_statuses,
        member_statuses=member_statuses
    )




@members_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def edit_member(id):

    from app.utils.branching import enforce_branch_access, branch_query

    member = Member.query.get_or_404(id)
    enforce_branch_access(member)

    if request.method == "POST":

        member.title = request.form.get("title")
        member.first_name = request.form.get("first_name")
        member.last_name = request.form.get("last_name")
        member.gender = request.form.get("gender")

        new_phone = normalize_sa_phone(request.form.get("phone"))

        # 🔒 BRANCH-AWARE DUPLICATE CHECK
        if new_phone != member.phone:

            existing_member = branch_query(Member) \
                .filter(Member.phone == new_phone, Member.id != id) \
                .first()

            existing_visitor = branch_query(Visitor) \
                .filter_by(phone=new_phone) \
                .first()

            if existing_member:
                flash(
                    f"Phone already exists on member: "
                    f"{existing_member.first_name} {existing_member.last_name}",
                    "error"
                )
                return redirect(url_for("members.edit_member", id=id))

            if existing_visitor:
                flash(
                    "Phone exists on a visitor record. Convert visitor first.",
                    "warning"
                )
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

    from app.models.lookup import Lookup

    departments = Lookup.query.filter_by(category="department").all()
    titles = Lookup.query.filter_by(category="title").all()
    marital_statuses = Lookup.query.filter_by(category="marital_status").all()
    member_statuses = Lookup.query.filter_by(category="member_status").all()

    return render_template(
        "edit_member.html",
        member=member,
        departments=departments,
        titles=titles,
        marital_statuses=marital_statuses,
        member_statuses=member_statuses
    )