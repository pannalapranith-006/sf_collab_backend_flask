from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from authlib.integrations.flask_client import OAuth
from flask_session import Session
from app.config import Config
from flask_socketio import SocketIO
from flask_limiter import Limiter
from celery import Celery
import os

oauth = OAuth()
jwt = JWTManager()

# ✅ FIXED CORS (handles preflight + all routes)
cors = CORS(
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True
)

db = SQLAlchemy()
migrate = Migrate()
sess = Session()

socketio = SocketIO(
    async_mode="gevent",
    cors_allowed_origins="*",  # ✅ allow all for now (safe for testing)
    ping_timeout=60,
    ping_interval=25,
    logger=True,
    engineio_logger=True,
)

# ---------------------------------------------------------------------------
# Celery — currently NOT used (kept for compatibility, not initialized)
# ---------------------------------------------------------------------------
def make_celery(app=None):
    celery.conf.update(
        broker_url=os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
        result_backend=os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
        timezone="UTC",
    )
    if app:
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        celery.Task = ContextTask
    return celery

celery = Celery(__name__)

from flask_jwt_extended import get_jwt_identity
from flask import request

def user_or_ip():
    try:
        user = get_jwt_identity()
        if user:
            return f"user:{user}"
    except:
        pass
    return request.remote_addr


limiter = Limiter(
    key_func=user_or_ip,
    default_limits=["1000 per day"],
    storage_uri=os.getenv("REDIS_URL", "memory://"),
    storage_options={"socket_connect_timeout": 1},
    strategy="fixed-window",
)
