import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    CLICKATELL_API_KEY = os.getenv("CLICKATELL_API_KEY")
    CLICKATELL_SENDER_ID = os.getenv("CLICKATELL_SENDER_ID")
    
    db_url = os.getenv("DATABASE_URL")

    if db_url:
        # Fix postgres:// to postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

        # 👇 FORCE SSL
        if "sslmode=" not in db_url:
            db_url += "?sslmode=require"

        SQLALCHEMY_DATABASE_URI = db_url
        
        # 👇 ADD THESE POOL SETTINGS TO FIX SSL ERRORS
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 10,
            "max_overflow": 20
        }
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'cms.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False