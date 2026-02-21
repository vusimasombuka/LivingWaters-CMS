from app.extensions import db
from datetime import datetime


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)

    uploaded_by = db.Column(db.String(50))

    branch_id = db.Column(
        db.Integer,
        db.ForeignKey("branches.id", name="fk_document_branch_id"),
        nullable=False
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("document_categories.id", name="fk_document_category_id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
