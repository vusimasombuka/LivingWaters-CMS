import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # Existing Clickatell settings
    CLICKATELL_API_KEY = os.getenv("CLICKATELL_API_KEY")
    CLICKATELL_SENDER_ID = os.getenv("CLICKATELL_SENDER_ID")
    
    # NEW: Email Configuration for info@livingwaters.africa
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")  # or your provider
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "info@livingwaters.africa")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")  # App-specific password
    MAIL_DEFAULT_SENDER = ("Living Waters Inventory", "info@livingwaters.africa")
    
    # Database configuration (keep existing)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if "sslmode=" not in db_url:
            db_url += "?sslmode=require"
        SQLALCHEMY_DATABASE_URI = db_url
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 10,
            "max_overflow": 20
        }
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'cms.db')}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False