from flask import Flask, request, abort, g, send_from_directory, make_response, session
from flask import Flask, request, abort, g, send_from_directory, session
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
from app.services.ai_news.scheduler import start_scheduler
#from app.routes.analytics import analytics_bp
# FIX: removed — feedparser not installed, ai_news disabled
# from app.services.ai_news.scheduler import start_scheduler
# FIX: removed — app.routes.analytics does not exist; analytics_bp is
#      already registered via the blueprints list in blueprints.py
# from app.routes.analytics import analytics_bp

WEBHOOK_SECRET = b'sFcollab_2025_secretKey!'

warnings.filterwarnings("ignore")
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

BASE_DIR           = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
UPLOAD_FOLDER      = os.path.join(BASE_DIR, 'uploads')
AVATAR_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'chat_avatars')


def get_email_service():
    return EmailService()


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP MIGRATIONS
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_MIGRATIONS = [
    # knowledge table
    ("knowledge", "file_size_mb",            "FLOAT"),
    ("knowledge", "image_buffer",            "BLOB"),
    ("knowledge", "image_content_type",      "VARCHAR(100)"),

    # startups table — lifecycle & execution (Week 1)
    ("startups",  "lifecycle_state",         "VARCHAR(50) DEFAULT 'active'"),
    ("startups",  "execution_score",         "FLOAT DEFAULT 0.0"),
    ("startups",  "milestones_completed",    "INTEGER DEFAULT 0"),
    ("startups",  "milestones_total",        "INTEGER DEFAULT 0"),
    ("startups",  "last_activity_at",        "TIMESTAMP"),
    ("startups",  "activity_score",          "FLOAT DEFAULT 0.0"),
    ("startups",  "crowdfunding_unlocked",   "BOOLEAN DEFAULT 0"),
    ("startups",  "crowdfunding_unlocked_at","TIMESTAMP"),

    # ideas table — vision system (Week 1)
    ("ideas", "vision_state",        "VARCHAR(50) DEFAULT 'public'"),
    ("ideas", "readiness_score",     "FLOAT DEFAULT 0.0"),
    ("ideas", "readiness_breakdown", "JSON"),
    ("ideas", "problem_statement",   "TEXT"),
    ("ideas", "outcome_goal",        "TEXT"),
    ("ideas", "risk_level",          "VARCHAR(20) DEFAULT 'medium'"),
    ("ideas", "required_roles",      "JSON"),
    ("ideas", "roadmap_items",       "JSON"),

    # users table — fixes missing columns needed by auth/profile flows
    ("users", "last_seen",                    "DATETIME"),
    ("users", "last_login_ip",                "VARCHAR(45)"),
    ("users", "total_revenue",                "FLOAT DEFAULT 0.0"),
    ("users", "reputation_score",             "FLOAT DEFAULT 0.0"),
    ("users", "storage_used_mb",              "FLOAT DEFAULT 0.0"),
    ("users", "stripe_connect_account_id",    "VARCHAR(255)"),
    ("users", "milestones_completed",         "INTEGER DEFAULT 0"),
    ("users", "milestones_on_time",           "INTEGER DEFAULT 0"),
    ("users", "tasks_completed",              "INTEGER DEFAULT 0"),
    ("users", "tasks_on_time",                "INTEGER DEFAULT 0"),
    ("users", "collaborations_count",         "INTEGER DEFAULT 0"),

    
    ("ideas", "activated_as_startup_id", "INTEGER"),

    # Proofs table — review system
    ("proofs", "status",         "VARCHAR(20) DEFAULT 'pending'"),
    ("proofs", "reviewed_by",    "INTEGER"),
    ("proofs", "reviewed_at",    "DATETIME"),
    ("proofs", "review_comment", "TEXT"),
    # Warnings – reference fields
    ("warnings", "reference_date", "DATE"),
    ("warnings", "reference_id", "INTEGER"),
    # ErpTask – due date
    ("erp_tasks", "due_date", "DATE"),
    # ErpTask – MVP fields for points calculation
    ("erp_tasks", "complexity",      "VARCHAR(20)"),
    ("erp_tasks", "requires_proof",  "BOOLEAN DEFAULT 0"),
    ("erp_tasks", "quality_rating",  "VARCHAR(20)"),
    ("execution_points", "approved_at",      "DATETIME"),
    ("execution_points", "approval_comment", "TEXT"),
    ("knowledge", "file_size_mb",             "FLOAT"),
    ("knowledge", "image_buffer",             "BLOB"),
    ("knowledge", "image_content_type",       "VARCHAR(100)"),

    # startups table
    ("startups",  "lifecycle_state",          "VARCHAR(50) DEFAULT 'active'"),
    ("startups",  "execution_score",          "FLOAT DEFAULT 0.0"),
    ("startups",  "milestones_completed",     "INTEGER DEFAULT 0"),
    ("startups",  "milestones_total",         "INTEGER DEFAULT 0"),
    ("startups",  "last_activity_at",         "TIMESTAMP"),
    ("startups",  "activity_score",           "FLOAT DEFAULT 0.0"),
    ("startups",  "crowdfunding_unlocked",    "BOOLEAN DEFAULT 0"),
    ("startups",  "crowdfunding_unlocked_at", "TIMESTAMP"),

    # ideas table
    ("ideas", "vision_state",           "VARCHAR(50) DEFAULT 'public'"),
    ("ideas", "readiness_score",        "FLOAT DEFAULT 0.0"),
    ("ideas", "readiness_breakdown",    "JSON"),
    ("ideas", "problem_statement",      "TEXT"),
    ("ideas", "outcome_goal",           "TEXT"),
    ("ideas", "risk_level",             "VARCHAR(20) DEFAULT 'medium'"),
    ("ideas", "required_roles",         "JSON"),
    ("ideas", "roadmap_items",          "JSON"),
    ("ideas", "activated_as_startup_id","INTEGER"),

    # users table
    ("users", "last_seen",                 "DATETIME"),
    ("users", "last_login_ip",             "VARCHAR(45)"),
    ("users", "total_revenue",             "FLOAT DEFAULT 0.0"),
    ("users", "reputation_score",          "FLOAT DEFAULT 0.0"),
    ("users", "storage_used_mb",           "FLOAT DEFAULT 0.0"),
    ("users", "stripe_connect_account_id", "VARCHAR(255)"),
    ("users", "milestones_completed",      "INTEGER DEFAULT 0"),
    ("users", "milestones_on_time",        "INTEGER DEFAULT 0"),
    ("users", "tasks_completed",           "INTEGER DEFAULT 0"),
    ("users", "tasks_on_time",             "INTEGER DEFAULT 0"),
    ("users", "collaborations_count",      "INTEGER DEFAULT 0"),
]


def _run_startup_migrations(app):
    """Run on every Flask startup. Adds missing columns without touching existing data."""
    from sqlalchemy import text, inspect as sa_inspect

    with app.app_context():
        added        = []
        errors       = []
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
                db.session.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
                )
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
    """Create and configure Flask application"""

    app = Flask(__name__, instance_relative_config=True)
    #app.register_blueprint(analytics_bp)
    # REMOVED BROKEN PREFLIGHT HANDLER - Flask-CORS handles this automatically
    
    # FIX: app.register_blueprint(analytics_bp) removed — analytics_bp import
    #      was deleted above; it is already in the blueprints list

    config_class = get_config(config_name)
    app.config.from_object(config_class)
    app.config.from_pyfile('config.py', silent=True)

    # ── JWT ──────────────────────────────────────────────────────────────────
    app.config["JWT_SECRET_KEY"]          = os.getenv("JWT_SECRET_KEY") or app.config.get("SECRET_KEY")
    app.config["JWT_TOKEN_LOCATION"]      = ["headers", "cookies"]
    app.config["JWT_COOKIE_SECURE"]       = False
    app.config["JWT_COOKIE_SAMESITE"]     = "Lax"
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_ACCESS_COOKIE_PATH"]  = "/"
    app.config["JWT_REFRESH_COOKIE_PATH"] = "/api/auth/refresh"
    app.config["JWT_COOKIE_DOMAIN"]       = None
    app.config["JWT_ACCESS_TOKEN_EXPIRES"]  = timedelta(minutes=15)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=7)

    is_production = os.getenv("FLASK_ENV") == "production"
    if is_production:
        app.config["JWT_TOKEN_LOCATION"]      = ["headers", "cookies"]
        app.config["JWT_COOKIE_SECURE"]       = True
        app.config["JWT_COOKIE_SAMESITE"]     = "None"
        app.config["JWT_COOKIE_CSRF_PROTECT"] = True
        app.config["JWT_COOKIE_DOMAIN"]       = ".sfcollab.com"
    else:
        app.config["JWT_TOKEN_LOCATION"]      = ["headers", "cookies"]
        app.config["JWT_COOKIE_SECURE"]       = False
        app.config["JWT_COOKIE_SAMESITE"]     = "Lax"
        app.config["JWT_COOKIE_CSRF_PROTECT"] = False
        app.config["JWT_COOKIE_DOMAIN"]       = None

    # ── Session ──────────────────────────────────────────────────────────────
    print(f"SESSION_TYPE from config: {app.config.get('SESSION_TYPE')}")

    app.config['SESSION_PERMANENT']       = True
    app.config['SESSION_USE_SIGNER']      = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_PATH']     = '/'
    app.config['SESSION_KEY_PREFIX']      = 'flask_session:'

    if is_production:
        app.config["SESSION_COOKIE_SAMESITE"] = "None"
        app.config["SESSION_COOKIE_SECURE"]   = True
    else:
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        app.config["SESSION_COOKIE_SECURE"]   = False

    app.config.setdefault("GITHUB_CLIENT_ID",     os.getenv("GITHUB_CLIENT_ID"))
    app.config.setdefault("GITHUB_CLIENT_SECRET", os.getenv("GITHUB_CLIENT_SECRET"))

    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config['PROOF_UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads', 'proofs')
    os.makedirs(app.config['PROOF_UPLOAD_FOLDER'], exist_ok=True)
    
    # AWS S3 Configuration
    app.config["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID")

    # ── AWS ──────────────────────────────────────────────────────────────────
    app.config["AWS_ACCESS_KEY_ID"]     = os.getenv("AWS_ACCESS_KEY_ID")
    app.config["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY")
    app.config["AWS_REGION"]            = os.getenv("AWS_REGION", "us-east-1")
    app.config["AWS_S3_BUCKET"]         = os.getenv("AWS_S3_BUCKET")
    app.config["BACKEND_URL"]           = Config.BACKEND_URL

    # ── Email ─────────────────────────────────────────────────────────────────
    app.config['SMTP_SERVER']         = os.getenv('MAIL_SERVER', 'smtp.example.com')
    app.config['SMTP_USE_TLS']        = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    app.config['SMTP_PORT']           = int(os.getenv('MAIL_PORT', 587))
    app.config['SMTP_USERNAME']       = os.getenv('MAIL_USERNAME', 'your_username')
    app.config['SMTP_PASSWORD']       = os.getenv('MAIL_PASSWORD', 'your_password')
    app.config['SMTP_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'your_default_sender')

    # ── AI services ──────────────────────────────────────────────────────────
    app.config['OPENAI_API_KEY']      = os.getenv('OPENAI_API_KEY', '')
    app.config['GROQ_API_KEY']        = os.getenv('GROQ_API_KEY', '')
    app.config['HUGGINGFACE_API_KEY'] = os.getenv('HUGGINGFACE_API_KEY', '')
    app.config['CORS_ORIGINS']        = Config.CORS_ORIGINS
    app.config['HF_PROXY_URL']        = os.getenv("HF_PROXY_URL")
    app.config['HF_PROXY_KEY']        = os.getenv("HF_PROXY_KEY")

    # ── Stripe ───────────────────────────────────────────────────────────────
    stripe.api_key                      = os.getenv('STRIPE_SECRET_KEY', '')
    app.config['STRIPE_SECRET_KEY']     = os.getenv('STRIPE_SECRET_KEY', '')
    app.config['STRIPE_WEBHOOK_SECRET'] = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    print("Initializing CORS with origins:", app.config.get('CORS_ORIGINS', []))

    # ── CORS ─────────────────────────────────────────────────────────────────
    # FIX: original had two half-merged CORS() calls (SyntaxError).
    # Collapsed into one clean call. Config.CORS_ORIGINS is the single source
    # of truth — never hardcode origins here.
    allowed_origins = app.config.get('CORS_ORIGINS', [])
    print(f"🚀 CORS ACTIVE FOR: {allowed_origins}")

    CORS(
        app,
        resources={r"/*": {"origins": allowed_origins}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-TOKEN"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    # CORS initialization – only once, using the origins from config
    allowed_origins = app.config.get('CORS_ORIGINS', [])
    print(f"🚀 CORS ACTIVE FOR: {allowed_origins}")
    CORS(app, resources={r"/*": {"origins": allowed_origins}}, 
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-CSRF-TOKEN"],
         methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])

    @app.after_request
    def handle_cors(response):
        # FIX: removed all hardcoded 'staging.sfcollab.com' header overrides.
        # They were forcing a single origin on every response and breaking all
        # other allowed origins. Flask-CORS above handles this correctly.
        return response

    @app.route('/<path:path>', methods=['OPTIONS'])
    def options_handler(path):
        return '', 200

    # ── Request logging ──────────────────────────────────────────────────────
    @app.before_request
    def start_request_timer():
        g.start_time = time.time()

    @app.after_request
    def log_response(response):
        if request.path in ("/favicon.ico", "/health"):
            return response
        if request.method == "OPTIONS" and not response.headers.get("Access-Control-Allow-Origin"):
            print("CORS WARNING: Missing Access-Control-Allow-Origin header")

        duration       = round(time.time() - g.start_time, 4)
        method         = request.method
        path           = request.path
        status         = response.status_code
        ip             = request.headers.get("X-Forwarded-For", request.remote_addr)
        origin         = request.headers.get("Origin")
        user_agent     = request.headers.get("User-Agent")
        has_auth       = "Authorization" in request.headers
        has_cookie     = bool(request.headers.get("Cookie"))
        content_length = request.content_length or 0

        if response.is_json:
            try:
                response_preview = json.dumps(response.get_json())[:1000]
            except Exception:
                response_preview = "<invalid json>"
        else:
            response_preview = "<non-json response>"

        print(f"""
================= API REQUEST =================
{method} {path}
Status: {status}  Duration: {duration}s
Client IP: {ip}  Origin: {origin}
Auth Header: {has_auth}  Cookie: {has_cookie}  Size: {content_length}b
Response: {response_preview}
=============================================
""")
        return response

    # ── Extensions ───────────────────────────────────────────────────────────
    db.init_app(app)
    from app import models
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    if app.config.get("SESSION_TYPE") == "filesystem":
        app.config["SESSION_FILE_DIR"] = os.path.join(BASE_DIR, "flask_session")
        os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

    sess = Session()
    if app.config.get("SESSION_TYPE") == "sqlalchemy":
        app.config["SESSION_SQLALCHEMY"]       = db
        app.config["SESSION_SQLALCHEMY_TABLE"] = "sessions"

    try:
        sess.init_app(app)
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

    _run_startup_migrations(app)

    socketio.init_app(app)

    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        auth_routes.init_oauth(app)
        print("✓ OAuth initialized")
    else:
        print("⚠  OAuth not initialized (missing GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET)")

    for blueprint in blueprints:
        app.register_blueprint(blueprint["blueprint"], url_prefix=blueprint["url_prefix"])

    # AI news scheduler disabled — needs feedparser: pip install feedparser
    # start_scheduler(app)

    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/health')
    def health():
        return {'status': 'healthy', 'database': 'connected'}

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/socket.io"):
            return e
        return {"success": False, "error": "Resource not found"}, 404

    import traceback

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        print("🔥 500 ERROR:", error)
        traceback.print_exc()
        return {'success': False, 'error': str(error)}, 500

    @app.route('/api/webhook/github', methods=['POST'])
    def github_webhook():
        signature = request.headers.get('X-Hub-Signature-256')
        if signature is None:
            abort(400, "No signature provided")
        sha_name, signature = signature.split('=')
        mac = hmac.new(os.getenv('WEBHOOK'), msg=request.data, digestmod=hashlib.sha256)
        if not hmac.compare_digest(mac.hexdigest(), signature):
            abort(403, "Invalid signature")
        event   = request.headers.get('X-GitHub-Event')
        payload = request.json
        print(event, payload)
        return '', 200    
    return app
        return '', 200

    return app  # FIX: removed duplicate `return app` that followed this line
