from app.extensions import db
from app.models.sms_log import SMSLog
from app.services.clickatell_service import send_sms
import logging
from datetime import datetime
from app.models.audience_segment import AudienceSegment
logger = logging.getLogger(__name__)

def send_ready_sms():
    """
    Sends pending SMS in batches to avoid memory issues and API rate limits.
    Runs every 5 minutes. Processes ALL pending SMS across all branches.
    """
    BATCH_SIZE = 50  # Process max 50 per run
    
    # Get all pending SMS across all branches, limited to batch size
    messages = SMSLog.query.filter_by(status="pending").limit(BATCH_SIZE).all()
    
    if not messages:
        return
        
    logger.info(f"Processing {len(messages)} pending SMS")
    sent_count = 0
    failed_count = 0
    
    for sms in messages:
        try:
            send_sms(
                phone=sms.phone,
                message=sms.message,
            )
            sms.status = "sent"
            sms.error = None
            sent_count += 1
            
        except Exception as e:
            sms.status = "failed"
            sms.error = str(e)[:500]  # Limit error message length
            failed_count += 1
            logger.error(f"SMS failed for {sms.phone}: {str(e)}")
    
    db.session.commit()
    logger.info(f"SMS Sender Job Complete: {sent_count} sent, {failed_count} failed")


def process_mass_messages():
    """
    Checks for scheduled mass messages and creates SMSLog records.
    Run this before send_ready_sms() in your cron job.
    """
    from app.models.mass_message import MassMessage
    from app.services.audience_builder import AudienceBuilder
    
    now = datetime.utcnow()
    
    # Get messages that are scheduled and due
    messages = MassMessage.query.filter(
        MassMessage.status == "scheduled",
        MassMessage.scheduled_at <= now
    ).all()
    
    for msg in messages:
        try:
            # Determine filters
            if msg.audience_segment_id:
                segment = AudienceSegment.query.get(msg.audience_segment_id)
                filters = segment.filter_criteria if segment else {}
                audience_type = 'members'  # Saved segments are always members
            else:
                filters = msg.ad_hoc_filters or {}
                # 🎯 NEW: Extract audience type from filters (default to members)
                audience_type = filters.pop('_audience_type', 'members') if filters else 'members'
            
            # Determine branch
            branch_id = msg.target_branch_id
            if not branch_id and msg.branch_id:
                # Use creator's branch if no specific target
                branch_id = msg.branch_id
            
            # 🎯 NEW: Get all recipients with audience_type
            recipients = AudienceBuilder.get_recipients(
                filters, 
                branch_id=branch_id,
                audience_type=audience_type
            )
            
            # Update message with actual count
            msg.total_recipients = len(recipients)
            msg.status = "sending"
            db.session.commit()
            
            # Create SMSLog records in batches
            batch_size = 100
            for i in range(0, len(recipients), batch_size):
                batch = recipients[i:i+batch_size]
                logs = []
                
                for person in batch:  # Changed from 'member' to 'person'
                    if not person.phone:
                        continue
                    
                    personalized = AudienceBuilder.personalize_message(msg.content, person)
                    
                    logs.append(SMSLog(
                        phone=person.phone,
                        message=personalized,
                        message_type="mass_message",
                        mass_message_id=msg.id,
                        status="pending",
                        branch_id=person.branch_id
                    ))
                
                if logs:
                    db.session.bulk_save_objects(logs)
                    db.session.commit()
            
            msg.status = "sent"
            msg.sent_at = datetime.utcnow()
            db.session.commit()
            
        except Exception as e:
            msg.status = "draft"  # Reset to draft on error
            db.session.commit()
            # Log error
            print(f"Error processing mass message {msg.id}: {str(e)}")

# Update your existing send_ready_sms to update MassMessage stats
def update_mass_message_stats():
    """Update sent/failed counts on MassMessage based on SMSLog"""
    from app.models.mass_message import MassMessage
    from sqlalchemy import func
    
    # Get messages that are in 'sent' status but not fully processed
    messages = MassMessage.query.filter_by(status="sent").all()
    
    for msg in messages:
        sent = SMSLog.query.filter_by(
            mass_message_id=msg.id, 
            status="sent"
        ).count()
        
        failed = SMSLog.query.filter_by(
            mass_message_id=msg.id,
            status="failed"
        ).count()
        
        msg.sent_count = sent
        msg.failed_count = failed
        db.session.commit()

def run_messaging_jobs():
    process_mass_messages()  # Create pending SMS logs
    send_ready_sms()         # Your existing function
    update_mass_message_stats()  # Update counts