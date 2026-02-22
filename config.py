import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    db_url = os.getenv("DATABASE_URL")

    if db_url:
        # Fix Render postgres:// issue
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # Local development
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'cms.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    EMERGENCY_ACCESS = True