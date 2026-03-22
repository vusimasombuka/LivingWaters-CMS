from datetime import datetime, timedelta
from app.extensions import db
from app.models.inventory import InventoryItem, StockResponsiblePerson
from app.models.sms_log import SMSLog
from app.services.clickatell_service import send_sms
from flask import current_app
from flask_mail import Message
import logging

logger = logging.getLogger(__name__)


def stock_alert_job():
    """
    Runs daily at 8:00 AM.
    - Mondays: Send SMS (once/week) + Email (1st of 2/week)
    - Thursdays: Send Email (2nd of 2/week) only
    Checks all branches for low stock items and notifies responsible persons.
    """
    today = datetime.utcnow()
    is_monday = today.weekday() == 0  # Monday
    is_thursday = today.weekday() == 3  # Thursday
    
    # Only run on Monday or Thursday
    if not (is_monday or is_thursday):
        logger.info("Stock alert job: Not Monday or Thursday, skipping")
        return
    
    logger.info(f"Running stock alert job - {today.strftime('%A %Y-%m-%d')}")
    
    # Find all items with active low stock alerts (not yet replenished)
    low_stock_items = InventoryItem.query.filter_by(is_low_stock_alert_active=True).all()
    
    if not low_stock_items:
        logger.info("No low stock items pending replenishment")
        return
    
    total_sms = 0
    total_emails = 0
    
    for item in low_stock_items:
        # Double-check quantity hasn't been fixed manually
        if item.quantity > item.min_stock_level:
            logger.info(f"Item {item.name} quantity restored, deactivating alert")
            item.is_low_stock_alert_active = False
            item.last_replenished_at = today
            continue
        
        # Get active responsible persons
        persons = StockResponsiblePerson.query.filter_by(
            inventory_item_id=item.id, 
            is_active=True
        ).all()
        
        if not persons:
            logger.warning(f"No responsible persons for low stock item: {item.name}")
            continue
        
        for person in persons:
            # Send SMS on Mondays only (once per week)
            if is_monday and person.notify_sms and person.phone:
                should_send_sms = True
                if item.last_sms_sent_at:
                    # Ensure 6 days have passed (prevent duplicates)
                    days_since_last = (today - item.last_sms_sent_at).days
                    if days_since_last < 6:
                        should_send_sms = False
                
                if should_send_sms:
                    if send_stock_sms(item, person):
                        total_sms += 1
                        # Update last sent time for the item (not per person to simplify)
                        if not item.last_sms_sent_at or (today - item.last_sms_sent_at).days >= 6:
                            item.last_sms_sent_at = today
            
            # Send Email on Mondays AND Thursdays (twice per week)
            if person.notify_email and person.email:
                should_send_email = True
                if item.last_email_sent_at:
                    hours_since_last = (today - item.last_email_sent_at).total_seconds() / 3600
                    # Ensure at least 60 hours between emails (prevents spam, allows Mon+Thu)
                    if hours_since_last < 60:
                        should_send_email = False
                
                if should_send_email:
                    if send_stock_email(item, person):
                        total_emails += 1
                        item.last_email_sent_at = today
    
    db.session.commit()
    logger.info(f"Stock alert job complete: {total_sms} SMS, {total_emails} emails sent")

def send_stock_sms(item, person):
    """Send low stock SMS notification"""
    try:
        message = (
            f"LOW STOCK ALERT: {item.name} is below minimum level. "
            f"Current: {item.quantity}, Minimum: {item.min_stock_level}. "
            f"Please replenish. Reply DONE when restocked. - Living Waters"
        )
        
        # Use existing SMS service
        sms = SMSLog(
            phone=person.phone,
            message=message,
            message_type="stock_alert",
            related_table="inventory_item",
            related_id=item.id,
            status="pending",
            branch_id=item.branch_id
        )
        db.session.add(sms)
        logger.info(f"Queued stock alert SMS for {item.name} to {person.phone}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to queue SMS for {item.name}: {str(e)}")
        return False

def send_stock_email(item, person):
    """Send low stock email notification from info@livingwaters.africa"""
    try:
        # Import mail here to avoid circular import
        from app import mail
        
        msg = Message(
            subject=f"URGENT: Low Stock Alert - {item.name}",
            sender=("Living Waters Inventory", "info@livingwaters.africa"),
            recipients=[person.email],
            body=f"""
Dear {person.name},

This is an automated notification regarding low stock levels:

Item: {item.name}
Current Quantity: {item.quantity}
Minimum Required: {item.min_stock_level}
Department: {item.department.value if item.department else 'N/A'}
Branch ID: {item.branch_id}

Please arrange for replenishment as soon as possible.

To stop these notifications, please log into the CMS and mark this item as "Replenished":
https://your-cms-domain.com/inventory

Best regards,
Living Waters Inventory System
            """,
            html=f"""
            <h3>Low Stock Alert</h3>
            <p>Dear {person.name},</p>
            <p>This is an automated notification regarding low stock levels:</p>
            <table border="1" cellpadding="10" style="border-collapse: collapse; margin: 20px 0;">
                <tr><td><strong>Item</strong></td><td>{item.name}</td></tr>
                <tr><td><strong>Current Quantity</strong></td><td style="color: red; font-weight: bold;">{item.quantity}</td></tr>
                <tr><td><strong>Minimum Required</strong></td><td>{item.min_stock_level}</td></tr>
                <tr><td><strong>Department</strong></td><td>{item.department.value if item.department else 'N/A'}</td></tr>
            </table>
            <p>Please arrange for replenishment as soon as possible.</p>
            <p>To stop these notifications, <a href="https://your-cms-domain.com/inventory">log into the CMS</a> and mark this item as "Replenished".</p>
            <p>Best regards,<br>Living Waters Inventory System</p>
            <hr>
            <small>Sent from info@livingwaters.africa</small>
            """
        )
        
        mail.send(msg)
        logger.info(f"Sent stock alert email for {item.name} to {person.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email for {item.name} to {person.email}: {str(e)}")
        return False