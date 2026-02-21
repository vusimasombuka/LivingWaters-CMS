from app.extensions import db
from datetime import datetime


class DocumentCategory(db.Model):
    __tablename__ = "document_categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)

    branch_id = db.Column(
        db.Integer,
        db.ForeignKey("branches.id", name="fk_doc_category_branch_id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    documents = db.relationship(
        "Document",
        backref="category",
        lazy=True
    )
