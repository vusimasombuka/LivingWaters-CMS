import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.decorators import role_required
from app.extensions import db
from app.models.sermon import Sermon
from app.utils.branching import branch_query, enforce_branch_access
from datetime import datetime
from flask import current_app

sermons_bp = Blueprint("sermons", __name__, url_prefix="/sermons")

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'aac', 'ogg'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 50MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_upload_folder():
    """Get upload folder from config"""
    return current_app.config.get('SERMON_FOLDER', os.path.join("instance", "uploads", "sermons"))

@sermons_bp.route("/")
@login_required
@role_required("super_admin", "admin")
def list_sermons():
    search = request.args.get("search", "").strip()
    pastor_filter = request.args.get("pastor", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    group_by = request.args.get("group_by", "pastor")  # 'pastor' or 'date'
    
    # Base query with branch isolation
    query = branch_query(Sermon).order_by(Sermon.sermon_date.desc())
    
    # Apply filters
    if search:
        query = query.filter(Sermon.title.ilike(f"%{search}%"))
    
    if pastor_filter:
        query = query.filter(Sermon.pastor_name.ilike(f"%{pastor_filter}%"))
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.filter(Sermon.sermon_date >= from_date)
        except:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.filter(Sermon.sermon_date <= to_date)
        except:
            pass
    
    sermons = query.all()
    
    # Get unique pastors for filter dropdown
    pastors_query = branch_query(Sermon).with_entities(Sermon.pastor_name).distinct().all()
    pastors = [p[0] for p in pastors_query]
    
    # Group sermons for collapsible view
    grouped_sermons = {}
    if group_by == "pastor":
        for sermon in sermons:
            key = sermon.pastor_name
            if key not in grouped_sermons:
                grouped_sermons[key] = []
            grouped_sermons[key].append(sermon)
    else:  # group by date (Year-Month)
        for sermon in sermons:
            key = sermon.sermon_date.strftime("%B %Y")
            if key not in grouped_sermons:
                grouped_sermons[key] = []
            grouped_sermons[key].append(sermon)
    
    return render_template(
        "sermons.html",
        grouped_sermons=grouped_sermons,
        pastors=pastors,
        search=search,
        pastor_filter=pastor_filter,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by
    )

@sermons_bp.route("/upload", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def upload_sermon():
    if request.method == "POST":
        # Check if file present
        if 'file' not in request.files:
            flash("No file selected", "error")
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash("No file selected", "error")
            return redirect(request.url)
        
        # Validate file type
        if not allowed_file(file.filename):
            flash("Invalid file type. Allowed: MP3, WAV, M4A, AAC, OGG", "error")
            return redirect(request.url)
        
        # Check file size (approximate from request content length)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)     # Reset to beginning

        if file_size > MAX_FILE_SIZE:
            flash(f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB", "error")
            return redirect(request.url)
        
        # Get form data
        title = request.form.get("title", "").strip()
        pastor_name = request.form.get("pastor_name", "").strip()
        sermon_date_str = request.form.get("sermon_date", "").strip()
        
        if not title or not pastor_name or not sermon_date_str:
            flash("Title, Pastor Name, and Date are required", "error")
            return redirect(request.url)
        
        try:
            sermon_date = datetime.strptime(sermon_date_str, "%Y-%m-%d").date()
        except:
            flash("Invalid date format", "error")
            return redirect(request.url)
        
        # Secure filename with timestamp to avoid collisions
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{original_filename}"
        
        # Save file
        upload_folder = get_upload_folder()
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Create database record
        sermon = Sermon(
            title=title,
            pastor_name=pastor_name,
            sermon_date=sermon_date,
            filename=filename,
            file_size=file_size,
            branch_id=current_user.branch_id
        )
        
        db.session.add(sermon)
        db.session.commit()
        
        flash(f"Sermon '{title}' uploaded successfully", "success")
        return redirect(url_for("sermons.list_sermons"))
    
    return render_template("upload_sermon.html")

@sermons_bp.route("/download/<int:sermon_id>")
@login_required
@role_required("super_admin", "admin")
def download_sermon(sermon_id):
    sermon = Sermon.query.get_or_404(sermon_id)
    enforce_branch_access(sermon)
    
    upload_folder = get_upload_folder()
    
    return send_from_directory(
        upload_folder,
        sermon.filename,
        as_attachment=True,
        download_name=f"{sermon.title.replace(' ', '_')}_{sermon.sermon_date}.mp3"
    )

@sermons_bp.route("/delete/<int:sermon_id>", methods=["POST"])
@login_required
@role_required("super_admin", "admin")
def delete_sermon(sermon_id):
    sermon = Sermon.query.get_or_404(sermon_id)
    enforce_branch_access(sermon)
    
    # Delete file from disk
    upload_folder = get_upload_folder()
    file_path = os.path.join(upload_folder, sermon.filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    db.session.delete(sermon)
    db.session.commit()
    
    flash("Sermon deleted successfully", "success")
    return redirect(url_for("sermons.list_sermons"))