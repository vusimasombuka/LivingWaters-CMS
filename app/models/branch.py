from app.extensions import db
from datetime import datetime
import uuid

class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    location = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Public token for QR code access
    public_token = db.Column(db.String(32), unique=True, index=True, nullable=True)
    
    def __init__(self, **kwargs):
        super(Branch, self).__init__(**kwargs)
        # Auto-generate token on creation if not provided
        if not self.public_token:
            self.generate_token()
    
    def generate_token(self):
        """Generate a unique public token for QR codes"""
        if not self.public_token:
            self.public_token = uuid.uuid4().hex[:16]
            return True
        return False
    
    def __repr__(self):
        return f"<Branch {self.name}>"