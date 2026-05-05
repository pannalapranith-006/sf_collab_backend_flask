from gevent import monkey
monkey.patch_all()

import os
import warnings
from werkzeug.middleware.proxy_fix import ProxyFix
from app.extensions import socketio
from app import create_app
from flask_cors import CORS

# =====================================================
# ENV SETUP
# =====================================================
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

ENV = os.getenv("FLASK_ENV", "development")
PORT = int(os.getenv("PORT", 5001))
DEBUG = ENV != "production"

print("=" * 60)
print("SF COLLAB API STARTING")
print(f"ENV: {ENV}")
print(f"PORT: {PORT}")
print("=" * 60)

# =====================================================
# CREATE APP
# =====================================================
app = create_app(ENV)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

print("DB URI:", app.config["SQLALCHEMY_DATABASE_URI"])
# =====================================================
# PROXY FIX (PRODUCTION ONLY)
# =====================================================
if ENV == "production":
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_proto=1,
        x_host=1,
        x_for=1,
    )

# =====================================================
# MAIN (Configured in Dockerfile to use gunicorn in production)
# =====================================================

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=PORT,
        debug=DEBUG,
        use_reloader=False,  # important on Windows sometimes
    )

