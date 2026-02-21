from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required
from app.decorators import role_required
from app.extensions import db
from app.models.inventory import Department, InventoryItem
from app.models.lookup import Lookup
from app.models.member import Member
from app.models.giving import Giving
from flask import flash


inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/")
@login_required
@role_required("super_admin", "admin", "finance")
def inventory_home():

    from app.models.lookup import Lookup
    from app.models.inventory import InventoryItem

    departments = Lookup.query.filter_by(category="department").all()
    items = InventoryItem.query.order_by(InventoryItem.name).all()

    return render_template(
        "inventory.html",
        departments=departments,
        items=items
    )





@inventory_bp.route("/add", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def add_inventory():

    name = request.form.get("name")
    quantity = request.form.get("quantity")
    notes = request.form.get("notes")
    department_id = request.form.get("department_id")

    new_item = InventoryItem(
        name=name,
        quantity=int(quantity),
        notes=notes,
        department_id=int(department_id)
    )

    db.session.add(new_item)
    db.session.commit()

    return redirect(url_for("inventory.inventory_home"))

# =========================
# MASTER DATA (LOOKUP)
# =========================
@inventory_bp.route("/lookup", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def manage_lookup():

    from app.models.lookup import Lookup
    from app.models.member import Member
    from app.models.giving import Giving
    from flask import flash

    if request.method == "POST":
        category = request.form.get("category")
        value = request.form.get("value")

        if not category or not value:
            flash("Category and value are required.", "error")
            return redirect(url_for("inventory.manage_lookup"))

        value = value.strip()

        # Normalize offering_type to lowercase
        if category == "offering_type":
            value = value.lower()

        # Prevent duplicate values
        existing = Lookup.query.filter_by(
            category=category,
            value=value
        ).first()

        if existing:
            flash("This value already exists.", "error")
            return redirect(url_for("inventory.manage_lookup"))

        db.session.add(Lookup(category=category, value=value))
        db.session.commit()

        flash("Value added successfully.", "success")
        return redirect(url_for("inventory.manage_lookup"))

    categories = ["department", "title", "marital_status", "offering_type", "sms_type"]

    lookup_data = {
        cat: Lookup.query.filter_by(category=cat)
        .order_by(Lookup.value)
        .all()
        for cat in categories
    }

    return render_template(
        "lookup.html",
        categories=categories,
        lookup_data=lookup_data
    )


# =========================
# EDIT LOOKUP VALUE
# =========================
@inventory_bp.route("/lookup/edit/<int:lookup_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def edit_lookup(lookup_id):

    from app.models.lookup import Lookup
    from flask import flash

    lookup = Lookup.query.get_or_404(lookup_id)

    new_value = request.form.get("value")

    if not new_value:
        flash("Value cannot be empty.", "error")
        return redirect(url_for("inventory.manage_lookup"))

    new_value = new_value.strip()

    # Normalize offering_type
    if lookup.category == "offering_type":
        new_value = new_value.lower()

    # Prevent duplicate update
    duplicate = Lookup.query.filter_by(
        category=lookup.category,
        value=new_value
    ).first()

    if duplicate and duplicate.id != lookup.id:
        flash("This value already exists.", "error")
        return redirect(url_for("inventory.manage_lookup"))

    lookup.value = new_value
    db.session.commit()

    flash("Updated successfully.", "success")
    return redirect(url_for("inventory.manage_lookup"))


# =========================
# DELETE LOOKUP VALUE
# =========================
@inventory_bp.route("/lookup/delete/<int:lookup_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def delete_lookup(lookup_id):

    from app.models.lookup import Lookup
    from app.models.member import Member
    from app.models.giving import Giving
    from flask import flash

    lookup = Lookup.query.get_or_404(lookup_id)

    # Prevent deletion if in use
    member_usage = Member.query.filter_by(title=lookup.value).first() or \
                   Member.query.filter_by(marital_status=lookup.value).first()

    giving_usage = Giving.query.filter_by(giving_type=lookup.value).first()

    if member_usage or giving_usage:
        flash("Cannot delete. This value is currently in use.", "error")
        return redirect(url_for("inventory.manage_lookup"))

    db.session.delete(lookup)
    db.session.commit()

    flash("Deleted successfully.", "success")
    return redirect(url_for("inventory.manage_lookup"))


