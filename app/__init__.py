from flask import Flask
from config import Config
from app.extensions import db, login_manager, migrate, scheduler
import os
import logging
from app.jobs.event_reminder_job import event_reminder_job



# Setup logging for jobs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Import models here to avoid circular imports
    from app.models.branch import Branch
    
    # ========================================================
    # Import blueprints
    # ========================================================
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
    from app.routes.messaging import messaging_bp
    from app.models.audience_segment import AudienceSegment
    from app.models.mass_message import MassMessage
    # Register blueprints
    
    app.register_blueprint(messaging_bp)
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

    # Load authentication utilities
    from app import auth_utils

    # Prevent SQLite locking issues
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    # ================= SCHEDULER CONFIGURATION =================
    scheduler.init_app(app)
    
    # Only start scheduler in production or main process (not reloader)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler.start()
        
        # Import jobs here to avoid circular imports
        from app.jobs.birthday_sms_job import birthday_sms_job
        from app.jobs.sms_sender_job import run_messaging_jobs
        from app.jobs.visitor_followup_job import visitor_followup_job
        from app.jobs.visitor_sms_jobs import mark_visitor_sms_ready
        from app.jobs.absentees_followup_job import absentees_followup_job
        
        def run_with_context(func):
            """Wrapper to provide app context for jobs"""
            def wrapper():
                with app.app_context():
                    try:
                        func()
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"Job {func.__name__} failed: {str(e)}")
                        raise
            return wrapper
        
        # Clear existing jobs (in case of reloads)
        scheduler.remove_all_jobs()
        
        # Birthday SMS - Daily at 8:00 AM
        scheduler.add_job(
            id="birthday_sms_job",
            func=run_with_context(birthday_sms_job),
            trigger="cron",
            hour=8,
            minute=0,
            replace_existing=True
        )
        
        # SMS Sender - Every 5 minutes (batched)
        scheduler.add_job(
        id="messaging_jobs",
        func=run_with_context(run_messaging_jobs),  # This does EVERYTHING
        trigger="interval",
        minutes=5,
        replace_existing=True
        )
        
        # Visitor Follow-up - Mondays at 9:00 AM
        scheduler.add_job(
            id="visitor_followup_job",
            func=run_with_context(visitor_followup_job),
            trigger="cron",
            day_of_week="mon",
            hour=9,
            minute=0,
            replace_existing=True
        )
        
        # Visitor SMS 4-hour delay check - Every 15 minutes
        scheduler.add_job(
            id="mark_visitor_sms_ready_job",
            func=run_with_context(mark_visitor_sms_ready),
            trigger="interval",
            minutes=15,
            replace_existing=True
        )
        
        # Absentees Follow-up - Daily at 10:00 AM
        scheduler.add_job(
            id="absentees_followup_job",
            func=run_with_context(absentees_followup_job),
            trigger="cron",
            hour=10,
            minute=0,
            replace_existing=True
        )

        scheduler.add_job(
        id="event_reminder_job",
        func=run_with_context(event_reminder_job),
        trigger="cron",
        hour=8,  # Run at 8am daily
        minute=0,
        replace_existing=True
        )


        # ================= DATABASE SETUP =================
    with app.app_context():
        # For new deployments: run migrations automatically
        # This ensures database is always at latest schema
        try:
            from flask_migrate import upgrade
            upgrade()
            logger.info("Database migrations applied successfully")
        except Exception as e:
            # If migrations fail (fresh DB), create tables
            logger.warning(f"Migration failed ({e}), creating tables...")
            db.create_all()
            logger.info("Database tables created (initial setup)")
        
        # Check if setup needed
        if Branch.query.count() == 0:
            logger.info("No branches found. Ready for /setup")
    
    # ================= CLI COMMANDS =================
    @app.cli.command("init-db")
    def init_db():
        """Initialize database for new organization"""
        with app.app_context():
            db.create_all()
            print("Database tables created. Run 'flask db upgrade' to apply migrations.")
            print("Then visit /setup to create your first branch and super admin.")

    @app.cli.command("reset-db")
    def reset_db():
        """⚠️ DANGER: Drop and recreate all tables"""
        with app.app_context():
            confirm = input("This will DELETE ALL DATA. Type 'yes' to confirm: ")
            if confirm == "yes":
                db.drop_all()
                db.create_all()
                print("Database reset complete.")
            else:
                print("Cancelled.")


    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403            
    
    return app
