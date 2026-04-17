"""
SF Collab Auth Routes
Updated with notification triggers for account events
"""

from urllib import response
from flask import Blueprint, request, jsonify, redirect, url_for
from app.extensions import oauth, db, limiter
from flask import session
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required, 
    get_jwt_identity,
    get_jwt,
    set_access_cookies, 
    set_refresh_cookies,
    unset_jwt_cookies,
    decode_token,
)
import traceback
from app.config import Config
from app.models.user import User
from app.models.refreshToken import RefreshToken
from app.models.userPermission import UserPermission
from app.models.activity import Activity
from app.utils.helper import utc_now_str
from app.models.waitlist import Waitlist
from app.models.chatConversation import ChatConversation
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from app.services.email_service import EmailService
from app.utils.helper import success_response, error_response

# ===== NOTIFICATION IMPORTS =====
from app.notifications.helpers import (
    notify_account_created,
    notify_email_verified,
    notify_password_changed,
    notify_password_reset,
    notify_new_device_login,
    notify_account_role_updated
)

bp = Blueprint('auth', __name__)
from app.utils.email_templates.email_templates import templates
email_service = EmailService()
thank_email_template = templates.get("welcome_email")


def init_oauth(app):
    """Initialize OAuth with Flask app (SAFE + STATELESS)"""

    oauth.init_app(app)

    # =========================
    # Hard config validation
    # =========================
    if not app.config.get("GOOGLE_CLIENT_ID"):
        raise RuntimeError("GOOGLE_CLIENT_ID is not set")

    if not app.config.get("GOOGLE_CLIENT_SECRET"):
        raise RuntimeError("GOOGLE_CLIENT_SECRET is not set")

    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
            "prompt": "consent",
            "access_type": "offline",
        }
    )

    oauth.register(
        name="github",
        client_id=app.config.get("GITHUB_CLIENT_ID"),
        client_secret=app.config.get("GITHUB_CLIENT_SECRET"),
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"}
    )

# ========================== HELPER FUNCTIONS ==========================
def generate_tokens(user_id):
    """Generate access and refresh tokens"""
    access_token = create_access_token(
        identity=str(user_id),
        expires_delta=timedelta(hours=72), # Provisional, in the future we may want to shorten this and rely more on refresh tokens for security
        fresh=True
    )
    refresh_token_str = create_refresh_token(
        identity=str(user_id),
        expires_delta=timedelta(days=30) # This is not actually used for validation in the current implementation, but we set it for potential future use and to have a clear expiration time for refresh tokens
    )
    return access_token, refresh_token_str


def save_refresh_token(user_id, token):
    """Save refresh token to database"""
    try:
        # Delete old refresh tokens for this user
        RefreshToken.query.filter_by(user_id=user_id).delete()
        
        # Save new refresh token
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token
        )
        db.session.add(refresh_token)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving refresh token: {str(e)}")


def grant_default_permissions(user_id):
    """Grant default permissions to new user"""
    default_permissions = [
        'view_dashboard',
        'create_idea',
        'view_ideas',
        'create_post',
        'view_posts',
        'send_message',
        'view_profile',
        'edit_own_profile'
    ]
    
    count = 0
    for permission_name in default_permissions:
        try:
            perm = UserPermission(
                user_id=user_id,
                permission_name=permission_name,
                is_granted=True
            )
            db.session.add(perm)
            count += 1
        except Exception:
            pass
    
    db.session.commit()
    return count


def get_user_response_data(user):

    return user.to_dict(include_statistics=True, include_recent_activity=True)



# ========================== REGISTER ==========================
@bp.route('/register', methods=['POST'])
def register():
    """Register new user"""
    try:
        data = request.get_json()
        
        required_fields = ['email', 'password', 'firstName', 'lastName']
        for field in required_fields:
            if not data.get(field):
                return error_response(f'{field} is required', 400)
        
        # Check if email already exists
        if User.query.filter_by(email=data['email'].lower()).first():
            return error_response('Email already registered', 400)
        
        # Create user
        user = User(
            first_name=data['firstName'],
            last_name=data['lastName'],
            email=data['email'].lower(),
            password=generate_password_hash(data['password']),
            role=data.get('role', 'member'),
            status='active',
            founder_plan_id="crowdfunding-founder-explorer", # Temporary default plan for new users
            builder_plan_id="crowdfunding-builder-supporter" # Temporary default plan for new users
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Grant default permissions
        grant_default_permissions(user.id)
        
        # Create wallet for new user
        from app.services.wallet_service import WalletService
        WalletService.get_wallet(user.id)
        
        # Add to general chat
        try:
            ChatConversation.add_to_general_chat(user)
        except Exception as e:
            print(f"Error adding to general chat: {e}")
        
        # ===== SEND NOTIFICATION =====
        try:
            notify_account_created(user.id)
        except Exception as e:
            print(f"Error sending account created notification: {e}")
        
        # Send welcome email
        try:
            brand_name = os.getenv("BRAND_NAME", "SFCollab")
            email_service.send_email(
                user.email, 
                f"Welcome to {brand_name}!",
                thank_email_template(
                    data={
                        "user": {
                            "name": f"{user.first_name} {user.last_name}",
                            "email": user.email
                        }
                    },
                    see_email_template=False
                )
            )
        except Exception as e:
            print(f"Error sending welcome email: {e}")
        
        # Log activity
        Activity.log(
            action="user_registered",
            user_id=user.id,
            details=f"User account created at {utc_now_str()}"
        )
        
        # Generate tokens
        access_token, refresh_token = generate_tokens(user.id)
        save_refresh_token(user.id, refresh_token)
        
        response = jsonify({
            "success": True,
            "message": "Registration successful",
            "user": get_user_response_data(user),
            "access_token": access_token,
            "refresh_token": refresh_token
        })
        
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)

        return response
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Registration failed: {str(e)}', 500)


# ========================== LOGIN ==========================
@bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")  # Rate limit to prevent brute force
def login():
    """Login user"""
    try:
        print("DEBUG: Login route called")
        data = request.get_json()
        print(f"DEBUG: Request data received: {data}")
        
        email = data.get('email')
        password = data.get('password')
        print(f"DEBUG: Email: {email}, Password provided: {bool(password)}")
        
        if not email or not password:
            print("DEBUG: Missing email or password")
            return error_response('Email and password are required', 400)
        
        user = User.query.filter_by(email=email.lower()).first()
        print(f"DEBUG: User found: {bool(user)}, Email: {email.lower()}")
        
        if not user or not check_password_hash(user.password, password):
            print("DEBUG: Invalid credentials")
            return error_response('Invalid email or password', 401)
        
        print(f"DEBUG: User status: {user.status}")
        if user.status == 'suspended':
            print("DEBUG: Account suspended")
            return error_response('Account is suspended', 403)
        
        # Check for new device login
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        print(f"DEBUG: Client IP: {client_ip}, User Agent: {user_agent}")
        
        # Update login info
        user.last_login = datetime.utcnow()
        user.last_login_ip = client_ip
        
        # Update streak via centralized service
        from app.services.streak_service import StreakService
        streak_result = StreakService.update_streak(user.id)
        print(f"DEBUG: Streak updated to {streak_result}")

        # Log activity
        Activity.log(
            action="user_login",
            user_id=user.id,
            details=f"User logged in at {utc_now_str()}"
        )
        print(f"DEBUG: Activity logged for user {user.id}")
        
        # Generate tokens
        access_token, refresh_token = generate_tokens(user.id)
        print("DEBUG: Tokens generated")
        save_refresh_token(user.id, refresh_token)
        print("DEBUG: Refresh token saved")
        
        user_response = get_user_response_data(user)
        print(f"DEBUG: User response data prepared")
        
        response = jsonify({
            "success": True,
            "message": "Login successful",
            "user": user_response,
            "access_token": access_token,
            "refresh_token": refresh_token
        })

        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)

        return response
        
    except Exception as e:
        print(f"DEBUG: Exception in login: {str(e)}")
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return error_response(f'Login failed: {str(e)}', 500)


# ========================== VERIFY EMAIL ==========================
@bp.route('/send-verification-code', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
def send_verification_code():
    """Send email verification code"""
    import random
    from flask_jwt_extended import create_access_token

    
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user or not user.email:
            return error_response('User or email not found', 404)
        
        code = random.randint(100000, 999999)
        verification_token = create_access_token(
            identity=str(user.id),
            expires_delta=timedelta(minutes=10),
            fresh=True,
            additional_claims={'code': code}
        )
        print(f"DEBUG: Generated verification code: {code} for user_id: {user.id}")
        email_service.send_email_verification_code(user, code)
        decoded_verification = decode_token(verification_token)
        print("DEBUG: Verification token claims:", decoded_verification)     
        return success_response({
            'message': 'Verification code sent to email',
            'verification_token': verification_token
        })
        
    except Exception as e:
        print(f"DEBUG: Exception in send_verification_code: {str(e)}")
        return error_response(str(e), 500)

@bp.route('/verify-code', methods=['POST'])
@limiter.limit("10 per minute")
def verify_code():
    data = request.get_json()

    email = data.get("email")
    submitted_code = data.get("code")

    if not email or not submitted_code:
        return error_response("Email and code are required", 400)

    user = User.query.filter_by(email=email).first()

    if not user:
        return error_response("User not found", 404)

    print(f"DEBUG: Stored code: {user.verification_code}, Submitted: {submitted_code}")

    if str(user.verification_code) != str(submitted_code):
        return error_response("Invalid code", 400)

    user.is_verified = True
    user.verification_code = None
    db.session.commit()

    try:
        notify_email_verified(user.id)
    except Exception as e:
        print(f"Error sending email verified notification: {e}")

    return success_response({
        "verified": True
    })




# ========================== PASSWORD RESET ==========================
@bp.route('/forgot-password', methods=['POST'])
@limiter.limit("5 per hour")  # Limit to prevent abuse
def forgot_password():
    """Request password reset"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return error_response('Email is required', 400)
        
        user = User.query.filter_by(email=email.lower()).first()
        
        if user:
            # ===== SEND NOTIFICATION =====
            try:
                notify_password_reset(user.id)
            except Exception as e:
                print(f"Error sending password reset notification: {e}")
            
            # TODO: Implement actual password reset email
        
        # Always return success to prevent email enumeration
        return success_response({
            'message': 'If an account exists with this email, you will receive password reset instructions.'
        })
        
    except Exception as e:
        return error_response('Failed to process request', 500)


@bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per hour")  # Limit to prevent abuse
def reset_password():
    """Reset password with token"""
    try:
        data = request.get_json()
        token = data.get('access_token')
        new_password = data.get('new_password')
        
        if not token or not new_password:
            return error_response('Token and new password are required', 400)
        
        # TODO: Implement proper token verification
        # For now, return not implemented
        
        return error_response('Password reset not yet implemented', 501)
        
    except Exception as e:
        return error_response(str(e), 500)


@bp.route('/change-password', methods=['POST'])
@jwt_required()
@limiter.limit("10 per hour")
def change_password():
    """Change password for logged in user"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return error_response('Current and new password are required', 400)
        
        user = User.query.get(int(user_id))
        
        if not check_password_hash(user.password, current_password):
            return error_response('Current password is incorrect', 400)
        
        user.password = generate_password_hash(new_password)
        db.session.commit()
        
        # ===== SEND NOTIFICATION =====
        try:
            notify_password_changed(user.id)
        except Exception as e:
            print(f"Error sending password changed notification: {e}")
        
        # Log activity
        Activity.log(
            action="password_changed",
            user_id=user.id,
            details=f"Password changed at {utc_now_str()}"
        )
        
        return success_response({
            'message': 'Password changed successfully'
        })
        
    except Exception as e:
        return error_response(f'Failed to change password: {str(e)}', 500)


# ========================== REFRESH TOKEN ==========================
@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
@limiter.limit("10 per hour")
def refresh():
    """Refresh access token"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return error_response('User not found', 404)
        

        new_access_token = create_access_token(identity=str(user_id))
        
        response = jsonify({"message": "Token refreshed"})
        set_access_cookies(response, new_access_token)
        
        return response
        
    except Exception as e:
        return error_response(f'Token refresh failed: {str(e)}', 500)


# ========================== LOGOUT ==========================
@bp.route('/logout', methods=['POST'])
@limiter.limit("10 per hour")
@jwt_required()
def logout():
    """Logout user"""
    try:
        user_id = get_jwt_identity()
        
        # Delete refresh tokens
        RefreshToken.query.filter_by(user_id=int(user_id)).delete()
        db.session.commit()
        
        # Log activity
        # Activity.log(
        #     action="user_logout",
        #     user_id=int(user_id),
        #     details=f"User logged out at {utc_now_str()}"
        # )
        

        response = jsonify({"message": "Logged out successfully"})
        unset_jwt_cookies(response)
        
        return response
        
    except Exception as e:
        return error_response(f'Logout failed: {str(e)}', 500)


# ========================== GET CURRENT USER ==========================
@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current authenticated user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        if not user:
            return error_response('User not found', 404)
        # Update streak via centralized service
        from app.services.streak_service import StreakService
        StreakService.update_streak(user.id)
        return success_response({
            'user': get_user_response_data(user)
        })
        
    except Exception as e:
        return error_response(f'Failed to get user: {str(e)}', 500)


# ========================== GOOGLE OAUTH ==========================
@bp.route('/google', methods=['GET'])
@limiter.limit("10 per hour")
def google_login():
    """Initiate Google OAuth"""
    session.pop('google_token', None)
    session.pop('_oauth_token_google', None)
    session.pop('_oauth_state_google', None)
    redirect_uri = Config.GOOGLE_REDIRECT_URI
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route('/google/callback', methods=['GET'])
@limiter.limit("10 per hour")
def google_callback():
    """Handle Google OAuth callback"""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            return _oauth_error_response('google', 'Failed to get user info')
        
        email = user_info.get('email')
        if not email:
            return _oauth_error_response('google', 'Email not provided')
        
        # Check if user exists
        user = User.query.filter_by(email=email.lower()).first()
        is_new_user = False
        
        if not user:
            is_new_user = True
            user = User(
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
                email=email.lower(),
                password=generate_password_hash(
                    f"oauth_google_{user_info.get('sub')}_{os.urandom(16).hex()}"
                ),
                is_email_verified=True,
                status='active',
                role='member',
                profile_picture=user_info.get('picture'),
                founder_plan_id="crowdfunding-founder-explorer", # Temporary default plan for OAuth users
                builder_plan_id="crowdfunding-builder-supporter" # Temporary default plan for OAuth users
            )
            db.session.add(user)
            db.session.commit()
            
            # Grant permissions
            grant_default_permissions(user.id)
            
            # Add to general chat
            try:
                ChatConversation.add_to_general_chat(user)
            except:
                pass
        
        # Update last login
        user.last_login = datetime.utcnow()
        user.last_activity_date = datetime.utcnow().date()
        db.session.commit()
        
        # ===== SEND NOTIFICATION FOR NEW ACCOUNT =====
        if is_new_user:
            try:
                notify_account_created(user.id)
            except Exception as e:
                print(f"Error sending account created notification: {e}")
            
            # Send welcome email
            try:
                brand_name = os.getenv("BRAND_NAME", "SFCollab")
                email_service.send_email(
                    user.email,
                    f"Welcome to {brand_name}!",
                    thank_email_template(
                        data={
                            "user": {
                                "name": f"{user.first_name} {user.last_name}",
                                "email": user.email
                            }
                        },
                        see_email_template=False
                    )
                )
            except:
                pass
        
        # Log activity
        # Activity.log(
        #     action="user_registered" if is_new_user else "user_login",
        #     user_id=user.id,
        #     details=f"OAuth login via Google at {utc_now_str()}"
        # )
        
        # Generate tokens
        access_token, refresh_token = generate_tokens(user.id)
        save_refresh_token(user.id, refresh_token)
        
        # Return success to popup
        user_json = jsonify(get_user_response_data(user)).get_data(as_text=True)
        return f"""
            <html>
                <script>
                    window.opener.postMessage({{
                        type: 'oauth_success',
                        provider: 'google',
                        access_token: '{access_token}',
                        refreshToken: '{refresh_token}',
                        user: {user_json}
                    }}, '*');
                    window.close();
                </script>
            </html>
        """
        
    except Exception as e:
        print(f"Google OAuth error: {str(e)}")
        return _oauth_error_response('google', str(e))


# ========================== GITHUB OAUTH ==========================
@bp.route('/github', methods=['GET'])
@limiter.limit("10 per hour")
def github_login():
    """Initiate GitHub OAuth"""
    redirect_uri = Config.GITHUB_REDIRECT_URI
    return oauth.github.authorize_redirect(redirect_uri)


@bp.route('/github/callback', methods=['GET'])
@limiter.limit("10 per hour")
def github_callback():
    """Handle GitHub OAuth callback"""
    try:
        token = oauth.github.authorize_access_token()
        
        # Get user info
        resp = oauth.github.get('user')
        user_info = resp.json()
        
        # Get emails
        emails_resp = oauth.github.get('user/emails')
        emails = emails_resp.json()
        
        # Find primary email
        primary_email = None
        for email_obj in emails:
            if email_obj.get('primary') and email_obj.get('verified'):
                primary_email = email_obj.get('email')
                break
        
        if not primary_email:
            for email_obj in emails:
                if email_obj.get('verified'):
                    primary_email = email_obj.get('email')
                    break
        
        if not primary_email:
            username = user_info.get('login')
            if username:
                primary_email = f"{username}@github.oauth"
            else:
                return _oauth_error_response('github', 'No email found')
        
        # Check if user exists
        user = User.query.filter_by(email=primary_email.lower()).first()
        is_new_user = False
        
        if not user:
            is_new_user = True
            user = User(
                first_name=user_info.get('name', '').split()[0] if user_info.get('name') else '',
                last_name=' '.join(user_info.get('name', '').split()[1:]) if user_info.get('name') else '',
                email=primary_email.lower(),
                password=generate_password_hash(
                    f"oauth_github_{user_info['id']}_{os.urandom(16).hex()}"
                ),
                is_email_verified=('@github.oauth' not in primary_email),
                status='active',
                role='member',
                profile_picture=user_info.get('avatar_url'),
                founder_plan_id="crowdfunding-founder-explorer", # Temporary default plan for OAuth users
                builder_plan_id="crowdfunding-builder-supporter" # Temporary default plan for OAuth users
            )
            db.session.add(user)
            db.session.commit()
            
            # Grant permissions
            grant_default_permissions(user.id)
            
            # Add to general chat
            try:
                ChatConversation.add_to_general_chat(user)
            except:
                pass
        
        # Update last login
        user.last_login = datetime.utcnow()
        user.last_activity_date = datetime.utcnow().date()
        db.session.commit()
        
        # ===== SEND NOTIFICATION FOR NEW ACCOUNT =====
        if is_new_user:
            try:
                notify_account_created(user.id)
            except Exception as e:
                print(f"Error sending account created notification: {e}")
            
            # Send welcome email
            try:
                brand_name = os.getenv("BRAND_NAME", "SFCollab")
                email_service.send_email(
                    user.email,
                    f"Welcome to {brand_name}!",
                    thank_email_template(
                        data={
                            "user": {
                                "name": f"{user.first_name} {user.last_name}",
                                "email": user.email
                            }
                        },
                        see_email_template=False
                    )
                )
            except:
                pass
        
        # Log activity
        # Activity.log(
        #     action="user_registered" if is_new_user else "user_login",
        #     user_id=user.id,
        #     details=f"OAuth login via GitHub at {utc_now_str()}"
        # )
        
        # Generate tokens
        access_token, refresh_token = generate_tokens(user.id)
        save_refresh_token(user.id, refresh_token)
        
        # Return success to popup
        user_json = jsonify(get_user_response_data(user)).get_data(as_text=True)
        return f"""
            <html>
                <script>
                    window.opener.postMessage({{
                        type: 'oauth_success',
                        provider: 'github',
                        access_token: '{access_token}',
                        refreshToken: '{refresh_token}',
                        user: {user_json}
                    }}, '*');
                    window.close();
                </script>
            </html>
        """
        
    except Exception as e:
        print(f"GitHub OAuth error: {str(e)}")
        return _oauth_error_response('github', str(e))


def _oauth_error_response(provider, error_message):
    """Helper function to return OAuth error response"""
    return f"""
        <html>
            <script>
                window.opener.postMessage({{
                    type: 'oauth_error',
                    provider: '{provider}',
                    error: '{error_message}'
                }}, '*');
                window.close();
            </script>
        </html>
    """
