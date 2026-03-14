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
    
    logger.info(f"Found {len(messages)} scheduled mass messages to process")
    
    for msg in messages:
        try:
            logger.info(f"Processing message ID {msg.id}: '{msg.title}'")
            
            # Determine filters
            if msg.audience_segment_id:
                segment = AudienceSegment.query.get(msg.audience_segment_id)
                filters = segment.filter_criteria if segment else {}
                audience_type = 'members'  # Saved segments are always members
                logger.info(f"  Using saved segment {msg.audience_segment_id} - forced audience_type: 'members'")
            else:
                filters = msg.ad_hoc_filters or {}
                # ✅ FIXED: Use audience_type from message object (not filters)
                audience_type = msg.audience_type or 'members'
                logger.info(f"  Using ad-hoc filters - stored audience_type: '{msg.audience_type}', resolved to: '{audience_type}'")
                logger.debug(f"  Filter criteria: {filters}")
            
            # Determine branch
            branch_id = msg.target_branch_id
            if not branch_id and msg.branch_id:
                branch_id = msg.branch_id
                logger.info(f"  Using creator branch_id: {branch_id}")
            else:
                logger.info(f"  Using target branch_id: {branch_id}")
            
            # 🎯 NEW: Get all recipients with audience_type
            logger.info(f"  Fetching recipients with audience_type='{audience_type}'")
            recipients = AudienceBuilder.get_recipients(
                filters, 
                branch_id=branch_id,
                audience_type=audience_type
            )
            
            recipient_count = len(recipients)
            logger.info(f"  Found {recipient_count} recipients")
            
            # Show first few recipients for verification
            if recipients:
                sample = recipients[:3]
                sample_details = [f"{getattr(r, 'first_name', 'Unknown')} ({getattr(r, 'phone', 'no-phone')})" for r in sample]
                logger.info(f"  Sample recipients: {', '.join(sample_details)}")
            
            # Update message with actual count
            msg.total_recipients = recipient_count
            msg.status = "sending"
            db.session.commit()
            logger.info(f"  Status updated to 'sending'")
            
            # Create SMSLog records in batches
            batch_size = 100
            total_created = 0
            for i in range(0, len(recipients), batch_size):
                batch = recipients[i:i+batch_size]
                logs = []
                
                for person in batch:
                    if not person.phone:
                        logger.warning(f"    Skipping person without phone: {getattr(person, 'first_name', 'Unknown')}")
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
                    total_created += len(logs)
                    logger.info(f"  Created batch of {len(logs)} SMS logs (total: {total_created}/{recipient_count})")
            
            msg.status = "sent"
            msg.sent_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"✅ Message {msg.id} completed successfully. Total SMS created: {total_created}")
            
        except Exception as e:
            msg.status = "draft"  # Reset to draft on error
            db.session.commit()
            logger.error(f"❌ Error processing mass message {msg.id}: {str(e)}", exc_info=True)

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