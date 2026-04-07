from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from app.decorators import role_required
from app.extensions import db
from app.models.mass_message import MassMessage
from app.models.audience_segment import AudienceSegment
from app.models.sms_log import SMSLog
from app.models.member import Member
from app.models.branch import Branch
from app.services.audience_builder import AudienceBuilder
from app.utils.branching import branch_query, enforce_branch_access
from datetime import datetime
from sqlalchemy import desc, exc
import logging

messaging_bp = Blueprint("messaging", __name__, url_prefix="/messaging")
logger = logging.getLogger(__name__)

def get_user_branch_filter():
    """Helper to get branch filter for current user"""
    if current_user.role == "super_admin":
        return None
    return current_user.branch_id

@messaging_bp.route("/")
@login_required
@role_required("super_admin", "admin", "branch_admin")
def index():
    """List all mass messages with pagination and filtering"""
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "all")
    
    try:
        query = MassMessage.query
        
        # Branch isolation
        branch_id = get_user_branch_filter()
        if branch_id:
            query = query.filter(MassMessage.branch_id == branch_id)
        
        if status != "all":
            query = query.filter(MassMessage.status == status)
        
        messages = query.order_by(desc(MassMessage.created_at)).paginate(
            page=page, per_page=25, error_out=False
        )
        
        return render_template("messaging/index.html", messages=messages, status=status)
    
    except Exception as e:
        logger.error(f"Error loading messages: {str(e)}")
        flash("Error loading messages. Please try again.", "error")
        return render_template("messaging/index.html", messages=None, status=status)

@messaging_bp.route("/audiences")
@login_required
@role_required("super_admin", "admin", "branch_admin")
def list_audiences():
    """Manage reusable audience segments"""
    page = request.args.get("page", 1, type=int)
    
    try:
        query = AudienceSegment.query
        
        # Branch access control
        if current_user.role != "super_admin":
            query = query.filter(
                db.or_(
                    AudienceSegment.branch_id == current_user.branch_id,
                    AudienceSegment.is_system == True
                )
            )
        
        segments = query.order_by(AudienceSegment.name).paginate(
            page=page, per_page=25, error_out=False
        )
        
        return render_template("messaging/audiences.html", segments=segments)
    
    except Exception as e:
        logger.error(f"Error loading audiences: {str(e)}")
        flash("Error loading audiences.", "error")
        return redirect(url_for("main.index"))

@messaging_bp.route("/audiences/save", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "branch_admin")
def save_audience():
    """Save a new audience segment"""
    try:
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        
        if not name:
            flash("Audience name is required.", "error")
            return redirect(url_for("messaging.list_audiences"))
        
        # Build filters from form data
        filters = {}
        
        if request.form.getlist("gender"):
            filters["gender"] = request.form.getlist("gender")
        
        if request.form.getlist("marital_status"):
            filters["marital_status"] = request.form.getlist("marital_status")
        
        if request.form.getlist("department"):
            filters["department"] = request.form.getlist("department")
        
        if request.form.get("baptized"):
            filters["baptized"] = request.form.get("baptized") == "true"
        
        if request.form.get("membership_course"):
            filters["membership_course"] = request.form.get("membership_course") == "true"
        
        if request.form.getlist("member_status"):
            filters["member_status"] = request.form.getlist("member_status")
        
        # Calculate count
        branch_id = get_user_branch_filter()
        count = AudienceBuilder.get_count(filters, branch_id)
        
        segment = AudienceSegment(
            name=name,
            description=description,
            filter_criteria=filters,
            estimated_count=count,
            created_by=current_user.id,
            branch_id=current_user.branch_id,
            is_system=(current_user.role == "super_admin" and request.form.get("is_system") == "true")
        )
        
        db.session.add(segment)
        db.session.commit()
        
        flash(f"Audience '{name}' saved with {count} people.", "success")
        
    except exc.IntegrityError as e:
        db.session.rollback()
        logger.error(f"Database integrity error saving audience: {str(e)}")
        flash("Error saving audience. Name might already exist.", "error")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving audience: {str(e)}")
        flash("Error saving audience. Please try again.", "error")
    
    return redirect(url_for("messaging.list_audiences"))

@messaging_bp.route("/compose", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin", "branch_admin")
def compose():
    """Compose and schedule new message"""
    if request.method == "POST":
        try:
            # Validation
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            
            if not title or not content:
                flash("Title and content are required.", "error")
                return redirect(url_for("messaging.compose"))
            
            # 🎯 FIXED: Extract audience_type from form
            audience_type = request.form.get("audience_type", "members")
            
            use_segment = request.form.get("use_segment") == "true"
            segment_id = request.form.get("segment_id")
            schedule_type = request.form.get("schedule_type", "now")
            schedule_datetime = request.form.get("schedule_datetime")
            
            # Build filters if not using saved segment
            filters = None
            if not use_segment:
                filters = {}
                if request.form.getlist("gender"):
                    filters["gender"] = request.form.getlist("gender")
                if request.form.getlist("marital_status"):
                    filters["marital_status"] = request.form.getlist("marital_status")
                if request.form.getlist("department"):
                    filters["department"] = request.form.getlist("department")
                if request.form.get("baptized"):
                    filters["baptized"] = request.form.get("baptized") == "true"
                if request.form.get("membership_course"):
                    filters["membership_course"] = request.form.get("membership_course") == "true"
                if request.form.getlist("member_status"):
                    filters["member_status"] = request.form.getlist("member_status")
                
                # 🎯 UPDATED: Allow empty filters for visitors, but require audience_type
                if not filters and audience_type == 'members':
                    flash("Please select at least one filter criteria for members.", "error")
                    return redirect(url_for("messaging.compose"))
            
            # Determine target branch
            target_branch_id = None
            if current_user.role == "super_admin" and request.form.get("target_branch_id"):
                try:
                    target_branch_id = int(request.form.get("target_branch_id"))
                except ValueError:
                    pass
            
            # Calculate recipient count
            if use_segment and segment_id:
                segment = AudienceSegment.query.get(segment_id)
                if not segment:
                    flash("Selected audience not found.", "error")
                    return redirect(url_for("messaging.compose"))
                
                # Check access to segment
                if current_user.role != "super_admin":
                    if not segment.is_system and segment.branch_id != current_user.branch_id:
                        flash("You don't have access to this audience.", "error")
                        return redirect(url_for("messaging.compose"))
                
                recipient_count = segment.estimated_count
            else:
                branch_id = target_branch_id or get_user_branch_filter()
                # 🎯 FIXED: Pass audience_type to get count
                recipient_count = AudienceBuilder.get_count(
                    filters, 
                    branch_id, 
                    audience_type=audience_type
                )
            
            if recipient_count == 0:
                flash("No recipients match your criteria.", "warning")
                return redirect(url_for("messaging.compose"))
            
            # Create message
            msg = MassMessage(
                title=title,
                content=content,
                audience_segment_id=segment_id if use_segment else None,
                ad_hoc_filters=filters if not use_segment else None,
                target_branch_id=target_branch_id,
                total_recipients=recipient_count,
                created_by=current_user.id,
                branch_id=current_user.branch_id,
                # 🎯 FIXED: Store audience type (remove underscore prefix when saving)
                audience_type=audience_type if not use_segment else 'members'
            )
            
            # Handle scheduling
            if schedule_type == "now":
                msg.status = "scheduled"
                msg.scheduled_at = datetime.utcnow()
            else:
                if not schedule_datetime:
                    flash("Please select a date and time for scheduling.", "error")
                    return redirect(url_for("messaging.compose"))
                
                try:
                    scheduled_time = datetime.strptime(schedule_datetime, "%Y-%m-%dT%H:%M")
                    if scheduled_time < datetime.utcnow():
                        flash("Schedule time must be in the future.", "error")
                        return redirect(url_for("messaging.compose"))
                    
                    msg.status = "scheduled"
                    msg.scheduled_at = scheduled_time
                except ValueError:
                    flash("Invalid date format.", "error")
                    return redirect(url_for("messaging.compose"))
            
            db.session.add(msg)
            db.session.commit()
            
            flash(f"Message scheduled for {recipient_count} recipients.", "success")
            return redirect(url_for("messaging.index"))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating message: {str(e)}")
            flash("Error creating message. Please try again.", "error")
            return redirect(url_for("messaging.compose"))
    
    # GET request - show compose form
    try:
        # Get available segments
        if current_user.role == "super_admin":
            segments = AudienceSegment.query.all()
        else:
            segments = AudienceSegment.query.filter(
                db.or_(
                    AudienceSegment.branch_id == current_user.branch_id,
                    AudienceSegment.is_system == True
                )
            ).all()
        
        # Get branches (for super admin)
        branches = Branch.query.all() if current_user.role == "super_admin" else []
        
        # Get filter options
        filter_config = AudienceBuilder.get_available_filters()
        
        return render_template(
            "messaging/compose.html",
            segments=segments,
            branches=branches,
            filter_config=filter_config,
            is_super_admin=(current_user.role == "super_admin")
        )
    except Exception as e:
        logger.error(f"Error loading compose form: {str(e)}")
        flash("Error loading form.", "error")
        return redirect(url_for("messaging.index"))

@messaging_bp.route("/preview-count", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "branch_admin")
def preview_count():
    """AJAX endpoint to get recipient count based on filters"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        filters = data.get("filters", {})
        
        # Get audience type (members, visitors, or all)
        audience_type = data.get("audience_type", "members")
        
        branch_id = get_user_branch_filter()
        if current_user.role == "super_admin" and data.get("branch_id"):
            try:
                branch_id = int(data.get("branch_id"))
            except ValueError:
                pass
        
        # Pass audience_type to both methods
        count = AudienceBuilder.get_count(
            filters, 
            branch_id, 
            audience_type=audience_type
        )
        
        # Get sample recipients (first 5)
        recipients = AudienceBuilder.get_recipients_paginated(
            filters, 
            page=1, 
            per_page=5, 
            branch_id=branch_id,
            audience_type=audience_type  # Add this parameter
        )
        
        sample = [{
            "name": f"{r.first_name or ''} {r.last_name or ''}".strip(),
            "phone": r.phone,
            "department": getattr(r, 'department', None)  # Use getattr for visitors
        } for r in recipients.items]
        
        return jsonify({
            "count": count,
            "sample": sample,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error in preview count: {str(e)}")
        return jsonify({"error": "Server error", "success": False}), 500

@messaging_bp.route("/cancel/<int:id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "branch_admin")
def cancel_message(id):
    """Cancel a scheduled message"""
    try:
        msg = MassMessage.query.get_or_404(id)
        
        # Branch access check
        if current_user.role != "super_admin":
            enforce_branch_access(msg)
        
        if msg.status in ["draft", "scheduled"]:
            msg.status = "cancelled"
            db.session.commit()
            flash("Message cancelled successfully.", "success")
        else:
            flash("Cannot cancel message that has already been sent.", "error")
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cancelling message: {str(e)}")
        flash("Error cancelling message.", "error")
    
    return redirect(url_for("messaging.index"))

@messaging_bp.route("/report/<int:id>")
@login_required
@role_required("super_admin", "admin", "branch_admin")
def report(id):
    """View delivery report"""
    try:
        msg = MassMessage.query.get_or_404(id)
        
        # Branch access check
        if current_user.role != "super_admin":
            enforce_branch_access(msg)
        
        page = request.args.get("page", 1, type=int)
        status_filter = request.args.get("status")
        
        from app.models.member import Member
        from app.models.visitor import Visitor
        from sqlalchemy import desc
        
        query = SMSLog.query.filter_by(mass_message_id=id)
        
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        logs = query.order_by(desc(SMSLog.created_at)).paginate(
            page=page, per_page=50, error_out=False
        )
        
        # 🎯 GET NAMES FOR ALL RECIPIENTS
        member_ids = [log.related_id for log in logs.items if log.related_table == 'member' and log.related_id]
        visitor_ids = [log.related_id for log in logs.items if log.related_table == 'visitor' and log.related_id]
        
        members = {m.id: m for m in Member.query.filter(Member.id.in_(member_ids)).all()} if member_ids else {}
        visitors = {v.id: v for v in Visitor.query.filter(Visitor.id.in_(visitor_ids)).all()} if visitor_ids else {}
        
        return render_template(
            "messaging/report.html",
            message=msg,
            logs=logs,
            status_filter=status_filter,
            members=members,
            visitors=visitors
        )
        
    except Exception as e:
        logger.error(f"Error loading report: {str(e)}")
        flash("Error loading report.", "error")
        return redirect(url_for("messaging.index"))

@messaging_bp.route("/edit-segment/<int:id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "branch_admin")
def edit_segment(id):
    """Edit an audience segment"""
    try:
        segment = AudienceSegment.query.get_or_404(id)
        
        # Access control
        if current_user.role != "super_admin":
            enforce_branch_access(segment)
            if segment.is_system:
                flash("Cannot edit system-wide segments.", "error")
                return redirect(url_for("messaging.list_audiences"))
        
        # Update basic info
        name = request.form.get("name", "").strip()
        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("messaging.list_audiences"))
        
        segment.name = name
        segment.description = request.form.get("description", "").strip()
        
        # Rebuild filters
        filters = {}
        if request.form.getlist("gender"):
            filters["gender"] = request.form.getlist("gender")
        if request.form.getlist("marital_status"):
            filters["marital_status"] = request.form.getlist("marital_status")
        if request.form.getlist("department"):
            filters["department"] = request.form.getlist("department")
        if request.form.get("baptized"):
            filters["baptized"] = request.form.get("baptized") == "true"
        if request.form.get("membership_course"):
            filters["membership_course"] = request.form.get("membership_course") == "true"
        if request.form.getlist("member_status"):
            filters["member_status"] = request.form.getlist("member_status")
        
        # Recalculate count
        branch_id = None if current_user.role == "super_admin" else current_user.branch_id
        segment.estimated_count = AudienceBuilder.get_count(filters, branch_id)
        segment.filter_criteria = filters
        segment.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash(f"Audience '{segment.name}' updated successfully.", "success")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating segment: {str(e)}")
        flash("Error updating audience.", "error")
    
    return redirect(url_for("messaging.list_audiences"))

@messaging_bp.route("/delete-segment/<int:id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin", "branch_admin")
def delete_segment(id):
    """Delete an audience segment"""
    try:
        segment = AudienceSegment.query.get_or_404(id)
        
        # Access control
        if current_user.role != "super_admin":
            enforce_branch_access(segment)
            if segment.is_system:
                flash("Cannot delete system-wide segments.", "error")
                return redirect(url_for("messaging.list_audiences"))
        
        # Check if used in any messages
        if segment.mass_messages:
            flash("Cannot delete segment that is used in messages.", "error")
            return redirect(url_for("messaging.list_audiences"))
        
        db.session.delete(segment)
        db.session.commit()
        flash("Audience segment deleted.", "success")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting segment: {str(e)}")
        flash("Error deleting audience.", "error")
    
    return redirect(url_for("messaging.list_audiences"))