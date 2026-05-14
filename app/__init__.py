from flask import Flask, request, abort, g, send_from_directory, make_response
from flask_cors import CORS
from .extensions import db, migrate, jwt, sess, limiter
from app.config import Config
from app.routes import auth_routes
from .config import get_config
import os
from datetime import timedelta
import warnings
import hmac
import hashlib
from app.extensions import socketio
from app.blueprints import blueprints
import time
import json
from app.services.email_service import EmailService
from flask_session import Session
import stripe

WEBHOOK_SECRET = b'sFcollab_2025_secretKey!'

warnings.filterwarnings("ignore")
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
AVATAR_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'chat_avatars')


def get_email_service():
    return EmailService()


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP MIGRATIONS
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA_MIGRATIONS = [
    # knowledge table
    ("knowledge", "file_size_mb", "FLOAT"),
    ("knowledge", "image_buffer", "BLOB"),
    ("knowledge", "image_content_type", "VARCHAR(100)"),

    # startups table — lifecycle & execution
    ("startups", "lifecycle_state", "VARCHAR(50) DEFAULT 'active'"),
    ("startups", "execution_score", "FLOAT DEFAULT 0.0"),
    ("startups", "milestones_completed", "INTEGER DEFAULT 0"),
    ("startups", "milestones_total", "INTEGER DEFAULT 0"),
    ("startups", "last_activity_at", "TIMESTAMP"),
    ("startups", "activity_score", "FLOAT DEFAULT 0.0"),
    ("startups", "crowdfunding_unlocked", "BOOLEAN DEFAULT 0"),
    ("startups", "crowdfunding_unlocked_at", "TIMESTAMP"),

    # ideas table — vision system
    ("ideas", "vision_state", "VARCHAR(50) DEFAULT 'public'"),
    ("ideas", "readiness_score", "FLOAT DEFAULT 0.0"),
    ("ideas", "readiness_breakdown", "JSON"),
    ("ideas", "problem_statement", "TEXT"),
    ("ideas", "outcome_goal", "TEXT"),
    ("ideas", "risk_level", "VARCHAR(20) DEFAULT 'medium'"),
    ("ideas", "required_roles", "JSON"),
    ("ideas", "roadmap_items", "JSON"),

    # users table
    ("users", "last_seen", "DATETIME"),
    ("users", "last_login_ip", "VARCHAR(45)"),
    ("users", "total_revenue", "FLOAT DEFAULT 0.0"),
    ("users", "reputation_score", "FLOAT DEFAULT 0.0"),
    ("users", "storage_used_mb", "FLOAT DEFAULT 0.0"),
    ("users", "stripe_connect_account_id", "VARCHAR(255)"),
    ("users", "milestones_completed", "INTEGER DEFAULT 0"),
    ("users", "milestones_on_time", "INTEGER DEFAULT 0"),
    ("users", "tasks_completed", "INTEGER DEFAULT 0"),
    ("users", "tasks_on_time", "INTEGER DEFAULT 0"),
    ("users", "collaborations_count", "INTEGER DEFAULT 0"),

    ("ideas", "activated_as_startup_id", "INTEGER"),
]


def _run_startup_migrations(app):
    """Run on every Flask startup. Adds missing columns without touching existing data."""
    from sqlalchemy import text, inspect as sa_inspect

    with app.app_context():
        added = []
        errors = []
        column_cache = {}

        for table, column, col_def in SCHEMA_MIGRATIONS:
            if table not in column_cache:
                try:
                    inspector = sa_inspect(db.engine)
                    cols = inspector.get_columns(table)
                    column_cache[table] = {c["name"] for c in cols}
                except Exception:
                    column_cache[table] = set()

            if column in column_cache[table]:
                continue

            try:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                db.session.commit()
                column_cache[table].add(column)
                added.append(f"{table}.{column}")
            except Exception as e:
                db.session.rollback()
                msg = str(e).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    column_cache[table].add(column)
                else:
                    errors.append(f"{table}.{column}: {e}")

        if added:
            print(f"✓ Migrations: added {len(added)} column(s): {', '.join(added)}")
        if errors:
            for err in errors:
                print(f"⚠  Migration error: {err}")
# ─────────────────────────────────────────────────────────────────────────────


def create_app(config_name=None):
    """Create and configure Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    config_class = get_config(config_name)
    app.config.from_object(config_class)
    app.config.from_pyfile('config.py', silent=True)

    # JWT Configuration
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY") or app.config.get("SECRET_KEY")
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=7)

    is_production = os.getenv("FLASK_ENV") == "production"
    if is_production:
        app.config["JWT_COOKIE_SECURE"] = True
        app.config["JWT_COOKIE_SAMESITE"] = "None"
        app.config["JWT_COOKIE_CSRF_PROTECT"] = True
        app.config["JWT_COOKIE_DOMAIN"] = ".sfcollab.com"
    else:
        app.config["JWT_COOKIE_SECURE"] = False
        app.config["JWT_COOKIE_SAMESITE"] = "Lax"
        app.config["JWT_COOKIE_CSRF_PROTECT"] = False
        app.config["JWT_COOKIE_DOMAIN"] = None

    # Session configuration
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_PATH'] = '/'
    app.config['SESSION_KEY_PREFIX'] = 'flask_session:'

    if is_production:
        app.config["SESSION_COOKIE_SAMESITE"] = "None"
        app.config["SESSION_COOKIE_SECURE"] = True
    else:
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        app.config["SESSION_COOKIE_SECURE"] = False

    app.config.setdefault("GITHUB_CLIENT_ID", os.getenv("GITHUB_CLIENT_ID"))
    app.config.setdefault("GITHUB_CLIENT_SECRET", os.getenv("GITHUB_CLIENT_SECRET"))

    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # AWS S3
    app.config["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID")
    app.config["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY")
    app.config["AWS_REGION"] = os.getenv("AWS_REGION", "us-east-1")
    app.config["AWS_S3_BUCKET"] = os.getenv("AWS_S3_BUCKET")
    app.config["BACKEND_URL"] = Config.BACKEND_URL

    # Email
    app.config['SMTP_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.example.com')
    app.config['SMTP_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    app.config['SMTP_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['SMTP_USERNAME'] = os.getenv('MAIL_USERNAME', 'your_username')
    app.config['SMTP_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your_password')
    app.config['SMTP_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'your_default_sender')

    # AI services
    app.config['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')
    app.config['GROQ_API_KEY'] = os.getenv('GROQ_API_KEY', '')
    app.config['HUGGINGFACE_API_KEY'] = os.getenv('HUGGINGFACE_API_KEY', '')
    app.config['CORS_ORIGINS'] = Config.CORS_ORIGINS
    app.config['HF_PROXY_URL'] = os.getenv("HF_PROXY_URL")
    app.config['HF_PROXY_KEY'] = os.getenv("HF_PROXY_KEY")

    # Stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
    app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY', '')
    app.config['STRIPE_WEBHOOK_SECRET'] = os.getenv('STRIPE_WEBHOOK_SECRET', '')

    # CORS
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://staging.sfcollab.com",
        "https://sfcollab.com",
        "https://sfclb.netlify.app"
    ]
    print(f"🚀 CORS ACTIVE FOR: {allowed_origins}")

    CORS(app,
         resources={r"/*": {"origins": allowed_origins}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-TOKEN"],
         methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])

    # ─── Before request: start timer ─────────────────────────────────────────
    @app.before_request
    def start_request_timer():
        g.start_time = time.time()

    # ─── After request: CORS headers + logging ──────────────────────────────
    @app.after_request
    def after_request_handler(response):
        # CORS headers (dynamic origin check)
        request_origin = request.headers.get("Origin")
        if request_origin and request_origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = request_origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Credentials"] = "true"

        # Request logging (skip noise)
        if request.path not in ("/favicon.ico", "/health") and request.method != "OPTIONS":
            duration = round(time.time() - g.start_time, 4) if hasattr(g, 'start_time') else 0
            method = request.method
            path = request.path
            status = response.status_code
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            origin = request_origin
            has_auth = "Authorization" in request.headers
            has_cookie = bool(request.headers.get("Cookie"))
            content_length = request.content_length or 0

            response_preview = ""
            if response.is_json:
                try:
                    data = response.get_json()
                    response_preview = json.dumps(data)[:1000]
                except Exception:
                    response_preview = "<invalid json>"
            else:
                response_preview = "<non-json response>"

            # Clean, working log message
            print(f"[REQUEST] {method} {path} → {status} ({duration}s) | IP: {ip} | "
                  f"Origin: {origin} | Auth: {has_auth} | Cookie: {has_cookie} | "
                  f"Length: {content_length} | Preview: {response_preview}")

        return response

    # OPTIONS handler for preflight
    @app.route('/<path:path>', methods=['OPTIONS'])
    def options_handler(path):
        return '', 200

    # Initialize extensions
    db.init_app(app)
    from app import models  # ensure models loaded for migration
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    # Session backend (filesystem or sqlalchemy)
    if app.config.get("SESSION_TYPE") == "filesystem":
        app.config["SESSION_FILE_DIR"] = os.path.join(BASE_DIR, "flask_session")
        os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
    if app.config.get("SESSION_TYPE") == "sqlalchemy":
        app.config["SESSION_SQLALCHEMY"] = db
        app.config["SESSION_SQLALCHEMY_TABLE"] = "sessions"

    _sess = Session()
    try:
        _sess.init_app(app)
    except Exception as e:
        if "already exists" in str(e):
            print(f"⚠ Sessions table race (harmless): {type(e).__name__}: {e}")
        else:
            raise

    with app.app_context():
        from app.models.marketplace_category import seed_categories
        try:
            seed_categories()
        except Exception:
            pass

    # Run startup schema migrations
    _run_startup_migrations(app)

    # Socket.IO
    socketio.init_app(app)

    # OAuth (Google)
    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        auth_routes.init_oauth(app)
        print("✓ OAuth initialized")
    else:
        print("⚠  OAuth not initialized (missing GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET)")

    # Register blueprints
    for blueprint in blueprints:
        app.register_blueprint(blueprint["blueprint"], url_prefix=blueprint["url_prefix"])

    # AI news scheduler (commented as in original)
    # print("Starting AI news scheduler...")
    # start_scheduler(app)
    # print("✓ Scheduler started")

    # Static file serving for uploads
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # Health check
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'database': 'connected'}

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/socket.io"):
            return e  # let Socket.IO handle it
        return {"success": False, "error": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        print("🔥 500 ERROR:", error)
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(error)}, 500

    # GitHub webhook
    @app.route('/api/webhook/github', methods=['POST'])
    def github_webhook():
        signature = request.headers.get('X-Hub-Signature-256')
        if not signature:
            abort(400, "No signature provided")

        sha_name, signature = signature.split('=')
        mac = hmac.new(os.getenv('WEBHOOK', b''), msg=request.data, digestmod=hashlib.sha256)

        if not hmac.compare_digest(mac.hexdigest(), signature):
            abort(403, "Invalid signature")

        event = request.headers.get('X-GitHub-Event')
        payload = request.json
        print(event, payload)
        return '', 200

    return app