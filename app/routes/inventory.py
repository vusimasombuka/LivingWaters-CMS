from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.decorators import role_required
from app.extensions import db
from app.models.inventory import InventoryItem, StockResponsiblePerson, InventoryTransaction
from app.models.lookup import Lookup
from datetime import datetime, timedelta
from calendar import monthrange
from flask_weasyprint import HTML, render_pdf

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


def get_month_boundaries(year, month):
    """Get start and end dates for a month"""
    start_date = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)
    return start_date, end_date


def get_inventory_snapshot(item_id, branch_id, as_of_date):
    """Calculate inventory quantity as of a specific date"""
    result = db.session.query(
        db.func.coalesce(db.func.sum(InventoryTransaction.quantity_change), 0)
    ).filter(
        InventoryTransaction.inventory_item_id == item_id,
        InventoryTransaction.branch_id == branch_id,
        InventoryTransaction.created_at <= as_of_date
    ).scalar()
    return result


@inventory_bp.route("/")
@login_required
@role_required("super_admin", "admin", "finance")
def inventory_home():
    from app.utils.branching import branch_query
    
    # Check if we should show report view
    view = request.args.get("view", "list")  # 'list' or 'report'
    
    if view == "report":
        return render_report_view()
    
    # Default: Inventory List View
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
                         items_by_department=items_by_department,
                         view="list")


def render_report_view():
    """Simple department report - with item selection"""
    from app.utils.branching import branch_query
    
    # Get filter parameters
    department_id = request.args.get("department_id")
    month = request.args.get("month", datetime.now().month)
    year = request.args.get("year", datetime.now().year)
    selected_item_ids = request.args.getlist("item_ids")  # Get selected items
    
    # Get departments for dropdown
    all_departments = Lookup.query.filter_by(category="department", is_active=True).all()
    
    # If department selected, get its items for the checkbox list
    department_items = []
    if department_id:
        dept_items_query = branch_query(InventoryItem).filter(
            InventoryItem.department_id == department_id
        ).order_by(InventoryItem.name).all()
        department_items = dept_items_query
        
        selected_dept = Lookup.query.get(int(department_id))
        dept_name = selected_dept.value if selected_dept else "All Departments"
    else:
        dept_name = "All Departments"
    
    # Filter items for report
    if selected_item_ids:
        # Show only selected items
        query = branch_query(InventoryItem).filter(
            InventoryItem.id.in_([int(id) for id in selected_item_ids])
        )
        report_items = query.order_by(InventoryItem.name).all()
    elif department_id:
        # Show all items in department if none selected
        report_items = department_items
    else:
        # Show all items if no department selected
        report_items = branch_query(InventoryItem).order_by(InventoryItem.name).all()
    
    # Calculate summary stats
    total_items = len(report_items)
    low_stock_count = sum(1 for item in report_items if item.is_low_stock_alert_active)
    total_quantity = sum(item.quantity for item in report_items)
    
    return render_template("inventory.html",
                         departments=all_departments,
                         department_items=department_items,  # Items for checkbox list
                         items_by_department={},
                         view="report",
                         report_items=report_items,
                         dept_name=dept_name,
                         selected_month=int(month),
                         selected_year=int(year),
                         selected_dept=department_id,
                         selected_item_ids=selected_item_ids,
                         total_items=total_items,
                         low_stock_count=low_stock_count,
                         total_quantity=total_quantity)


@inventory_bp.route("/report/pdf")
@login_required
@role_required("super_admin", "admin", "finance")
def department_report_pdf():
    """Print-friendly HTML report - selected items only"""
    from app.utils.branching import branch_query
    
    department_id = request.args.get("department_id")
    month = int(request.args.get("month", datetime.now().month))
    year = int(request.args.get("year", datetime.now().month))
    selected_item_ids = request.args.getlist("item_ids")
    
    # Get items - either selected or all in department
    query = branch_query(InventoryItem)
    
    if selected_item_ids:
        query = query.filter(InventoryItem.id.in_([int(id) for id in selected_item_ids]))
        dept_name = "Selected Items"
    elif department_id:
        query = query.filter(InventoryItem.department_id == department_id)
        selected_dept = Lookup.query.get(int(department_id))
        dept_name = selected_dept.value if selected_dept else "All Departments"
    else:
        dept_name = "All Departments"
    
    items = query.order_by(InventoryItem.name).all()
    
    # Summary stats
    total_items = len(items)
    low_stock_count = sum(1 for item in items if item.is_low_stock_alert_active)
    total_quantity = sum(item.quantity for item in items)
    
    branch_name = current_user.branch.name if current_user.branch else "All Branches"
    month_name = datetime(year, month, 1).strftime("%B")
    
    return render_template("inventory_report_print.html",
                          items=items,
                          dept_name=dept_name,
                          month_name=month_name,
                          year=year,
                          branch_name=branch_name,
                          total_items=total_items,
                          low_stock_count=low_stock_count,
                          total_quantity=total_quantity,
                          generated_at=datetime.now())


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
    db.session.flush()
    
    # Log initial stock transaction
    if quantity > 0:
        transaction = InventoryTransaction(
            inventory_item_id=new_item.id,
            transaction_type="initial",
            quantity_change=quantity,
            previous_quantity=0,
            new_quantity=quantity,
            notes="Initial stock entry",
            created_by=current_user.id,
            branch_id=branch_id
        )
        db.session.add(transaction)
    
    db.session.commit()
    
    # Handle responsible persons
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
        new_quantity = int(request.form.get("quantity", 0))
        old_quantity = item.quantity
        
        item.name = request.form.get("name")
        item.notes = request.form.get("notes")
        item.department_id = int(request.form.get("department_id"))
        item.min_stock_level = int(request.form.get("min_stock_level", 0))
        
        # Only log transaction if quantity changed
        if new_quantity != old_quantity:
            change = new_quantity - old_quantity
            transaction_type = "purchase" if change > 0 else "consumption"
            
            transaction = InventoryTransaction(
                inventory_item_id=item.id,
                transaction_type=transaction_type,
                quantity_change=change,
                previous_quantity=old_quantity,
                new_quantity=new_quantity,
                notes=request.form.get("transaction_notes", "Stock adjustment"),
                created_by=current_user.id,
                branch_id=item.branch_id
            )
            db.session.add(transaction)
            
            item.quantity = new_quantity
        
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
    
    departments = Lookup.query.filter_by(category="department", is_active=True).all()
    return render_template("edit_inventory.html", item=item, departments=departments)


@inventory_bp.route("/replenished/<int:item_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "finance")
def mark_replenished(item_id):
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
    from app.utils.branching import enforce_branch_access

    item = InventoryItem.query.get_or_404(item_id)
    enforce_branch_access(item)

    db.session.delete(item)
    db.session.commit()
    flash("Item deleted successfully.", "success")

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

        if category == "offering_type":
            value = value.lower()

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

    if lookup.category == "offering_type":
        new_value = new_value.lower()

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


@inventory_bp.route("/lookup/delete/<int:lookup_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def delete_lookup(lookup_id):
    from app.models.lookup import Lookup
    from app.models.member import Member
    from app.models.giving import Giving
    from flask import flash

    lookup = Lookup.query.get_or_404(lookup_id)

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