from functools import wraps
from flask import abort
from flask_login import current_user

SUPER_ADMIN_ROLE = "super_admin"

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            # SUPER ADMIN BYPASS
            if current_user.role == SUPER_ADMIN_ROLE:
                return f(*args, **kwargs)

            if current_user.role not in roles:
                abort(403)

            return f(*args, **kwargs)
        return wrapped
    return decorator
