from app.extensions import db
from datetime import datetime

class Sermon(db.Model):
    __tablename__ = "sermons"
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    pastor_name = db.Column(db.String(100), nullable=False)
    sermon_date = db.Column(db.Date, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)  # Size in bytes
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id", name="fk_sermon_branch_id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    branch = db.relationship("Branch", backref="sermons")
    
    def get_file_size_mb(self):
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0