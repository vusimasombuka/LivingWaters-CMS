from app.extensions import db
from datetime import datetime



class InventoryItem(db.Model):
    __tablename__ = "inventory_item"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text)
    min_stock_level = db.Column(db.Integer, default=0, nullable=False)
    is_low_stock_alert_active = db.Column(db.Boolean, default=False)
    last_replenished_at = db.Column(db.DateTime, nullable=True)
    last_sms_sent_at = db.Column(db.DateTime, nullable=True)
    last_email_sent_at = db.Column(db.DateTime, nullable=True)
    
    # CHANGED: Link to Lookup instead of Department
    department_id = db.Column(db.Integer, db.ForeignKey("lookup.id"), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id", name="fk_inventory_branch_id"), 
                         nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    # Relationship to Lookup (just like Member)
    department = db.relationship("Lookup", backref="inventory_items")
    
    responsible_persons = db.relationship("StockResponsiblePerson", backref="inventory_item", 
                                         lazy=True, cascade="all, delete-orphan")
    
    def check_stock_level(self):
        return self.quantity <= self.min_stock_level and self.min_stock_level > 0


class StockResponsiblePerson(db.Model):
    __tablename__ = "stock_responsible_person"
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey("inventory_item.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)  # For SMS
    email = db.Column(db.String(120), nullable=True)  # For Email
    notify_sms = db.Column(db.Boolean, default=True)
    notify_email = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())