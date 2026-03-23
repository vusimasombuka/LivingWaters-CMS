import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.decorators import role_required
from app.extensions import db
from app.models.sermon import Sermon
from app.utils.branching import branch_query, enforce_branch_access
from app.utils.s3_storage import upload_file_to_s3, delete_file_from_s3
from datetime import datetime

sermons_bp = Blueprint("sermons", __name__, url_prefix="/sermons")

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'aac', 'ogg'}
MAX_FILE_SIZE = 100 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@sermons_bp.route("/")
@login_required
@role_required("super_admin", "admin")
def list_sermons():
    search = request.args.get("search", "").strip()
    pastor_filter = request.args.get("pastor", "").strip()
    group_by = request.args.get("group_by", "pastor")
    
    query = branch_query(Sermon).order_by(Sermon.sermon_date.desc())
    
    if search:
        query = query.filter(Sermon.title.ilike(f"%{search}%"))
    if pastor_filter:
        query = query.filter(Sermon.pastor_name.ilike(f"%{pastor_filter}%"))
    
    sermons = query.all()
    pastors = [p[0] for p in branch_query(Sermon).with_entities(Sermon.pastor_name).distinct().all()]
    
    grouped = {}
    for s in sermons:
        key = s.pastor_name if group_by == "pastor" else s.sermon_date.strftime("%B %Y")
        grouped.setdefault(key, []).append(s)
    
    return render_template("sermons.html", grouped_sermons=grouped, pastors=pastors, **request.args)

@sermons_bp.route("/upload", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def upload_sermon():
    if request.method == "POST":
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            flash("Invalid file", "error")
            return redirect(request.url)
        
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            flash(f"File too large. Max {MAX_FILE_SIZE//(1024*1024)}MB", "error")
            return redirect(request.url)
        
        title = request.form.get("title", "").strip()
        pastor = request.form.get("pastor_name", "").strip()
        date_str = request.form.get("sermon_date", "").strip()
        
        if not all([title, pastor, date_str]):
            flash("All fields required", "error")
            return redirect(request.url)
        
        try:
            sermon_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
            
            s3_url = upload_file_to_s3(file, filename)
            
            db.session.add(Sermon(
                title=title, pastor_name=pastor, sermon_date=sermon_date,
                s3_url=s3_url, filename=filename, file_size=file_size,
                branch_id=current_user.branch_id
            ))
            db.session.commit()
            
            flash(f"'{title}' uploaded", "success")
            return redirect(url_for("sermons.list_sermons"))
        except Exception as e:
            flash(f"Upload failed: {str(e)}", "error")
    
    return render_template("upload_sermon.html")

@sermons_bp.route("/download/<int:sermon_id>")
@login_required
@role_required("super_admin", "admin")
def download_sermon(sermon_id):
    sermon = Sermon.query.get_or_404(sermon_id)
    enforce_branch_access(sermon)
    
    try:
        r = requests.get(sermon.s3_url, stream=True)
        return send_file(r.raw, as_attachment=True, 
                        download_name=f"{sermon.title.replace(' ', '_')}.mp3",
                        mimetype='audio/mpeg')
    except Exception as e:
        flash(f"Download failed: {str(e)}", "error")
        return redirect(url_for("sermons.list_sermons"))

@sermons_bp.route("/delete/<int:sermon_id>", methods=["POST"])
@login_required
@role_required("super_admin")
def delete_sermon(sermon_id):
    sermon = Sermon.query.get_or_404(sermon_id)
    enforce_branch_access(sermon)
    delete_file_from_s3(sermon.filename)
    db.session.delete(sermon)
    db.session.commit()
    flash("Deleted", "success")
    return redirect(url_for("sermons.list_sermons"))

@sermons_bp.route("/edit/<int:sermon_id>", methods=["GET", "POST"])
@login_required
@role_required("super_admin", "admin")
def edit_sermon(sermon_id):
    sermon = Sermon.query.get_or_404(sermon_id)
    enforce_branch_access(sermon)
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        pastor = request.form.get("pastor_name", "").strip()
        date_str = request.form.get("sermon_date", "").strip()
        
        if not all([title, pastor, date_str]):
            flash("All fields are required", "error")
            return redirect(request.url)
        
        try:
            sermon.title = title
            sermon.pastor_name = pastor
            sermon.sermon_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # Optional: Handle file replacement if user wants to update the audio
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']
                if allowed_file(file.filename):
                    # Delete old file from S3
                    delete_file_from_s3(sermon.filename)
                    
                    # Upload new file
                    file.seek(0, 2)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > MAX_FILE_SIZE:
                        flash(f"File too large. Max {MAX_FILE_SIZE//(1024*1024)}MB", "error")
                        return redirect(request.url)
                    
                    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
                    s3_url = upload_file_to_s3(file, filename)
                    
                    sermon.s3_url = s3_url
                    sermon.filename = filename
                    sermon.file_size = file_size
                else:
                    flash("Invalid file type", "error")
                    return redirect(request.url)
            
            db.session.commit()
            flash("Sermon updated successfully", "success")
            return redirect(url_for("sermons.list_sermons"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Update failed: {str(e)}", "error")
    
    return render_template("edit_sermon.html", sermon=sermon, MAX_FILE_SIZE=MAX_FILE_SIZE)