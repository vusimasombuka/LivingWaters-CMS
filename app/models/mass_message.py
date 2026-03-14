from app.extensions import db
from datetime import datetime

class MassMessage(db.Model):
    __tablename__ = "mass_messages"
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    # Either use a saved segment OR ad-hoc filters
    audience_segment_id = db.Column(db.Integer, db.ForeignKey("audience_segments.id"), nullable=True)
    ad_hoc_filters = db.Column(db.JSON, nullable=True)
    
    # 🎯 ADDED: Track who this message targets (members, visitors, or all)
    audience_type = db.Column(db.String(20), default="members")  # 'members', 'visitors', 'all'
    
    # Scheduling
    status = db.Column(db.String(20), default="draft")  # draft, scheduled, sending, sent, cancelled, failed
    scheduled_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    
    # Branch targeting
    target_branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=True)
    
    # Stats
    total_recipients = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    
    # Foreign keys
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    audience_segment = db.relationship("AudienceSegment", backref="mass_messages")
    creator = db.relationship("User", backref="mass_messages")
    branch = db.relationship("Branch", foreign_keys=[branch_id], backref="messages")
    target_branch = db.relationship("Branch", foreign_keys=[target_branch_id])
    
    def __repr__(self):
        return f"<MassMessage {self.title}>"
    
    @property
    def is_editable(self):
        """Check if message can still be edited/cancelled"""
        return self.status in ['draft', 'scheduled']
    
    @property
    def progress_percentage(self):
        """Calculate sending progress"""
        if self.total_recipients == 0:
            return 0
        return ((self.sent_count + self.failed_count) / self.total_recipients) * 100