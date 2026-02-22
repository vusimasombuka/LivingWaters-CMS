from flask import Flask, redirect, url_for
from config import Config
from app.extensions import db, login_manager, migrate, scheduler
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # =========================
    # Import blueprints
    # =========================
    from app.routes.auth import auth_bp
    from app.routes.bootstrap import bootstrap_bp
    from app.routes.members import members_bp
    from app.routes.visitors import visitors_bp
    from app.routes.check_in import checkin_bp
    from app.routes.giving import giving_bp
    from app.routes.documents import documents_bp
    from app.routes.reports import reports_bp
    from app.routes.events import events_bp
    from app.routes.inventory import inventory_bp
    from app.routes.sms_templates import sms_templates_bp
    from app.routes.sms_logs import sms_logs_bp
    from app.routes.overview import overview_bp
    from app.routes.services import services_bp

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(bootstrap_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(visitors_bp)
    app.register_blueprint(checkin_bp)
    app.register_blueprint(giving_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(sms_templates_bp)
    app.register_blueprint(sms_logs_bp)
    app.register_blueprint(overview_bp)
    app.register_blueprint(services_bp)

    # =========================
    # ROOT REDIRECT
    # =========================
    @app.route("/")
    def home():
        return redirect(url_for("auth.login"))

    # =========================
    # Prevent SQLite locking issues
    # =========================
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    # =========================
    # Scheduler Setup
    # =========================
    scheduler.init_app(app)

    from app.jobs.birthday_sms_job import birthday_sms_job
    from app.jobs.sms_sender_job import send_ready_sms
    from app.jobs.visitor_followup_job import visitor_followup_job
    from app.jobs.visitor_sms_jobs import mark_visitor_sms_ready
    from app.jobs.absentees_followup_job import absentees_followup_job

    def run_job_with_context(job_func):
        with app.app_context():
            job_func()

    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler.start()

    scheduler.add_job(
        id="birthday_sms_job",
        func=lambda: run_job_with_context(birthday_sms_job),
        trigger="interval",
        minutes=1,
    )

    scheduler.add_job(
        id="send_ready_sms_job",
        func=lambda: run_job_with_context(send_ready_sms),
        trigger="interval",
        minutes=1,
    )

    scheduler.add_job(
        id="visitor_followup_job",
        func=lambda: run_job_with_context(visitor_followup_job),
        trigger="interval",
        minutes=1,
    )

    scheduler.add_job(
        id="mark_visitor_sms_ready_job",
        func=lambda: run_job_with_context(mark_visitor_sms_ready),
        trigger="interval",
        minutes=1,
    )

    scheduler.add_job(
        id="absentees_followup_job",
        func=lambda: run_job_with_context(absentees_followup_job),
        trigger="interval",
        days=1,
        replace_existing=True,
    )

    return app