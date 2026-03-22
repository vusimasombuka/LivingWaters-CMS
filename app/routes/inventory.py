from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.decorators import role_required
from app.extensions import db
from app.models.inventory import InventoryItem, StockResponsiblePerson
from app.models.lookup import Lookup
from datetime import datetime

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/")
@login_required
@role_required("super_admin", "admin", "finance")
def inventory_home():
    from app.utils.branching import branch_query
    
    departments = Lookup.query.filter_by(category="department", is_active=True).all()
    items = branch_query(InventoryItem).order_by(InventoryItem.name).all()
    
    # Group items by department
    items_by_department = {}
    for item in items:
        dept_name = item.department.value if item.department else "Uncategorized"
        if dept_name not in items_by_department:
            items_by_department[dept_name] = []
        items_by_department[dept_name].append(item)
        
        # Auto-activate low stock alerts
        if item.check_stock_level() and not item.is_low_stock_alert_active:
            item.is_low_stock_alert_active = True
    
    db.session.commit()
    
    return render_template("inventory.html", 
                         departments=departments, 
                         items_by_department=items_by_department)

@inventory_bp.route("/add", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def add_inventory():
    name = request.form.get("name")
    quantity = int(request.form.get("quantity", 0))
    notes = request.form.get("notes")
    department_id = int(request.form.get("department_id"))
    min_stock = int(request.form.get("min_stock_level", 0))
    
    if current_user.role == "super_admin":
        branch_id = request.form.get("branch_id", current_user.branch_id)
    else:
        branch_id = current_user.branch_id
    
    # Check if initial quantity triggers low stock
    is_low = quantity <= min_stock and min_stock > 0
    
    new_item = InventoryItem(
        name=name,
        quantity=quantity,
        notes=notes,
        department_id=department_id,
        branch_id=branch_id,
        min_stock_level=min_stock,
        is_low_stock_alert_active=is_low,
        last_replenished_at=datetime.utcnow() if not is_low else None
    )
    
    db.session.add(new_item)
    db.session.commit()
    
    # Handle responsible persons if provided
    responsible_names = request.form.getlist("responsible_name[]")
    responsible_phones = request.form.getlist("responsible_phone[]")
    responsible_emails = request.form.getlist("responsible_email[]")
    
    for i in range(len(responsible_names)):
        if responsible_names[i]:
            person = StockResponsiblePerson(
                inventory_item_id=new_item.id,
                name=responsible_names[i],
                phone=responsible_phones[i] if i < len(responsible_phones) else None,
                email=responsible_emails[i] if i < len(responsible_emails) else None,
                notify_sms=bool(responsible_phones[i]) if i < len(responsible_phones) else False,
                notify_email=bool(responsible_emails[i]) if i < len(responsible_emails) else False
            )
            db.session.add(person)
    
    db.session.commit()
    flash("Item added successfully.", "success")
    return redirect(url_for("inventory.inventory_home"))

@inventory_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def edit_inventory(item_id):
    from app.utils.branching import enforce_branch_access
    
    item = InventoryItem.query.get_or_404(item_id)
    enforce_branch_access(item)
    
    if request.method == "POST":
        item.name = request.form.get("name")
        item.quantity = int(request.form.get("quantity", 0))
        item.notes = request.form.get("notes")
        item.department_id = int(request.form.get("department_id"))
        item.min_stock_level = int(request.form.get("min_stock_level", 0))
        
        # Auto-update alert status
        if item.quantity > item.min_stock_level:
            item.is_low_stock_alert_active = False
            item.last_replenished_at = datetime.utcnow()
        else:
            if item.min_stock_level > 0:
                item.is_low_stock_alert_active = True
        
        db.session.commit()
        flash(f"{item.name} updated successfully.", "success")
        return redirect(url_for("inventory.inventory_home"))
    
    # GET - show edit form
    departments = Lookup.query.filter_by(category="department", is_active=True).all()
    return render_template("edit_inventory.html", item=item, departments=departments)


@inventory_bp.route("/replenished/<int:item_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def mark_replenished(item_id):
    """Admin marks item as replenished to stop notifications"""
    from app.utils.branching import enforce_branch_access
    
    item = InventoryItem.query.get_or_404(item_id)
    enforce_branch_access(item)
    
    item.is_low_stock_alert_active = False
    item.last_replenished_at = datetime.utcnow()
    db.session.commit()
    
    flash(f"{item.name} marked as replenished. Notifications stopped.", "success")
    return redirect(url_for("inventory.inventory_home"))

@inventory_bp.route("/responsible-persons/<int:item_id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def manage_responsible_persons(item_id):
    from app.utils.branching import enforce_branch_access
    
    item = InventoryItem.query.get_or_404(item_id)
    enforce_branch_access(item)
    
    if request.method == "POST":
        # Add new person
        name = request.form.get("name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        notify_sms = request.form.get("notify_sms") == "on"
        notify_email = request.form.get("notify_email") == "on"
        
        person = StockResponsiblePerson(
            inventory_item_id=item_id,
            name=name,
            phone=phone,
            email=email,
            notify_sms=notify_sms,
            notify_email=notify_email
        )
        db.session.add(person)
        db.session.commit()
        flash("Responsible person added.", "success")
        return redirect(url_for("inventory.manage_responsible_persons", item_id=item_id))
    
    persons = StockResponsiblePerson.query.filter_by(inventory_item_id=item_id).all()
    return render_template("responsible_persons.html", item=item, persons=persons)

@inventory_bp.route("/responsible-persons/delete/<int:person_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def delete_responsible_person(person_id):
    person = StockResponsiblePerson.query.get_or_404(person_id)
    item_id = person.inventory_item_id
    
    # Verify access via the item
    from app.utils.branching import enforce_branch_access
    enforce_branch_access(person.inventory_item)
    
    db.session.delete(person)
    db.session.commit()
    flash("Responsible person removed.", "success")
    return redirect(url_for("inventory.manage_responsible_persons", item_id=item_id))


@inventory_bp.route("/delete/<int:item_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def delete_inventory(item_id):

    from app.models.inventory import InventoryItem
    from app.utils.branching import enforce_branch_access

    item = InventoryItem.query.get_or_404(item_id)
    enforce_branch_access(item)

    db.session.delete(item)
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

    categories = ["department", "title", "marital_status", "member_status", "offering_type", "sms_type"]

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


