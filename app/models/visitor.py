from app.extensions import db

class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    
    alternative_contact = db.Column(db.String(100))
    email = db.Column(db.String(120))
    
    branch_id = db.Column(
        db.Integer,
        db.ForeignKey("branches.id", name="fk_visitor_branch_id"),
        nullable=False
    )

    @property
    def visit_count(self):
        from app.models.check_in import CheckIn
        return CheckIn.query.filter_by(visitor_id=self.id).count()

    @property
    def last_visit(self):
        from app.models.check_in import CheckIn
        last = (
            CheckIn.query
            .filter_by(visitor_id=self.id)
            .order_by(CheckIn.check_in_date.desc())
            .first()
        )
        return last.check_in_date if last else None

    @property
    def last_service(self):
        from app.models.check_in import CheckIn
        last = (
            CheckIn.query
            .filter_by(visitor_id=self.id)
            .order_by(CheckIn.check_in_date.desc())
            .first()
        )
        return last.service.name if last and last.service else None