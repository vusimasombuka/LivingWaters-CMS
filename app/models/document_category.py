from app.extensions import db
from datetime import datetime


class DocumentCategory(db.Model):
    __tablename__ = "document_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    
    # NEW: Parent category support
    parent_id = db.Column(
        db.Integer, 
        db.ForeignKey("document_categories.id", name="fk_doc_category_parent_id"), 
        nullable=True
    )
    
    branch_id = db.Column(
        db.Integer,
        db.ForeignKey("branches.id", name="fk_doc_category_branch_id"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    parent = db.relationship("DocumentCategory", remote_side=[id], backref="children")
    
    documents = db.relationship(
        "Document",
        backref="category",
        lazy=True,
        cascade="all, delete-orphan"
    )

    @property
    def is_parent(self):
        """Check if this category has children"""
        return len(self.children) > 0

    @property
    def level(self):
        """Get nesting level (0 = root, 1 = sub, etc.)"""
        level = 0
        parent = self.parent
        while parent:
            level += 1
            parent = parent.parent
        return level

    @property
    def display_name(self):
        """Return indented name based on level"""
        indent = "  " * self.level + ("└─ " if self.level > 0 else "")
        return f"{indent}{self.name}"
    
    @property
    def total_document_count(self):
        """Count all documents in this category + all subcategories"""
        count = len(self.documents)
        for child in self.children:
            count += len(child.documents)
        return count