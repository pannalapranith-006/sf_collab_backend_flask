"""
Marketplace Routes — SF Marketplace Foundation
================================================
Blueprint mounted at /api/marketplace

Endpoints:
  GET  /marketplace/categories              — list all categories
  GET  /marketplace/listings                — browse published listings
  GET  /marketplace/listings/<id>           — get single listing detail
  POST /marketplace/seller/register         — register as a seller
  GET  /marketplace/seller/me               — get my seller profile
  POST /marketplace/listings                — create a new listing (draft)
  PUT  /marketplace/listings/<id>           — update a listing
  POST /marketplace/listings/<id>/publish   — publish a draft listing
  POST /marketplace/listings/<id>/archive   — archive a listing
  POST /marketplace/listings/<id>/upload    — upload the main product file
  POST /marketplace/listings/<id>/previews  — upload preview images
  GET  /marketplace/my-listings             — get my listings as seller
  POST /marketplace/listings/<id>/boost     — boost visibility with crystals (future)

Admin:
  POST /marketplace/admin/listings/<id>/reject  — admin rejects listing
  GET  /marketplace/admin/listings              — admin: all listings (any status)
  PUT  /marketplace/admin/seller/<id>/verify    — admin verifies a seller
"""

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.user import User
from app.models.marketplace_seller import Seller
from app.models.marketplace_category import MarketplaceCategory
from app.models.marketplace_listing import MarketplaceListing, ALLOWED_PRODUCT_EXTENSIONS
from app.models.marketplace_purchase import MarketplacePurchase
from app.models.Balance import Balance, BalanceTransaction
from app.models.Crystal import CrystalWallet, CRYSTAL_SPEND_TYPES
from app.notifications.service import notification_service
from sqlalchemy import desc, or_

marketplace_bp = Blueprint('marketplace', __name__)

# ------------------------------------------------------------------
# Upload folder setup — mirrors the pattern in user_routes.py
# ------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
MARKETPLACE_UPLOAD_DIR   = os.path.join(BASE_DIR, 'uploads', 'marketplace', 'files')
MARKETPLACE_PREVIEW_DIR  = os.path.join(BASE_DIR, 'uploads', 'marketplace', 'previews')

os.makedirs(MARKETPLACE_UPLOAD_DIR,  exist_ok=True)
os.makedirs(MARKETPLACE_PREVIEW_DIR, exist_ok=True)

MAX_FILE_SIZE    = 50  * 1024 * 1024   # 50MB for product files
MAX_PREVIEW_SIZE = 5   * 1024 * 1024   # 5MB per preview image
MAX_PREVIEWS     = 5                    # max preview images per listing

ALLOWED_PREVIEW_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


# ------------------------------------------------------------------
# Helpers — same pattern as user_routes.py
# ------------------------------------------------------------------

def allowed_product_file(filename: str) -> bool:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_PRODUCT_EXTENSIONS


def allowed_preview(filename: str) -> bool:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_PREVIEW_EXTENSIONS


def validate_file_size(file, max_size: int) -> bool:
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size <= max_size


def save_product_file(file, seller_id: int):
    """
    Save the main downloadable product file.
    Returns a dict with url, name, size, type — same shape as user_routes.save_uploaded_file.
    """
    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    unique_name = f"{timestamp}_{seller_id}_{uuid.uuid4().hex[:8]}_{filename}"
    file_path   = os.path.join(MARKETPLACE_UPLOAD_DIR, unique_name)
    file.save(file_path)
    return {
        'url':       f"/uploads/marketplace/files/{unique_name}",
        'name':      filename,
        'size':      os.path.getsize(file_path),
        'type':      file.content_type or filename.rsplit('.', 1)[-1].lower(),
        'path':      file_path,
    }


def save_preview_image(file, seller_id: int):
    """Save a single preview image. Returns the URL string."""
    filename  = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    unique_name = f"{timestamp}_{seller_id}_{uuid.uuid4().hex[:6]}_{filename}"
    file_path   = os.path.join(MARKETPLACE_PREVIEW_DIR, unique_name)
    file.save(file_path)
    return f"/uploads/marketplace/previews/{unique_name}"


def require_admin(user_id: int) -> bool:
    user = User.query.get(user_id)
    return bool(user and getattr(user, 'is_admin', lambda: False)())


def get_or_404(model, id_):
    obj = model.query.get(id_)
    if not obj:
        return None, jsonify({'success': False, 'error': f'{model.__name__} not found'}), 404
    return obj, None, None


# ------------------------------------------------------------------
# CATEGORY ENDPOINTS
# ------------------------------------------------------------------

@marketplace_bp.route('/categories', methods=['GET'])
def get_categories():
    """List all active marketplace categories."""
    cats = MarketplaceCategory.query.filter_by(is_active=True)\
                                    .order_by(MarketplaceCategory.sort_order).all()
    return jsonify({'success': True, 'categories': [c.to_dict() for c in cats]}), 200


# ------------------------------------------------------------------
# LISTING BROWSE ENDPOINTS
# ------------------------------------------------------------------

@marketplace_bp.route('/listings', methods=['GET'])
def get_listings():
    """
    Browse published marketplace listings.
    Query params:
      category_slug, item_type, search, min_price, max_price,
      sort (newest|price_asc|price_desc|rating|popular),
      page, per_page
    """
    try:
        page         = request.args.get('page', 1, type=int)
        per_page     = min(request.args.get('per_page', 20, type=int), 100)
        category_slug = request.args.get('category_slug')
        item_type    = request.args.get('item_type')
        search       = request.args.get('search', '').strip()
        min_price    = request.args.get('min_price', type=float)
        max_price    = request.args.get('max_price', type=float)
        sort         = request.args.get('sort', 'newest')

        query = MarketplaceListing.query.filter_by(status='published', is_active=True)

        if category_slug:
            cat = MarketplaceCategory.query.filter_by(slug=category_slug).first()
            if cat:
                query = query.filter_by(category_id=cat.id)

        if item_type:
            query = query.filter_by(item_type=item_type)

        if search:
            like = f'%{search}%'
            query = query.filter(
                or_(
                    MarketplaceListing.title.ilike(like),
                    MarketplaceListing.description.ilike(like),
                )
            )

        if min_price is not None:
            query = query.filter(MarketplaceListing.price_cents >= int(min_price * 100))
        if max_price is not None:
            query = query.filter(MarketplaceListing.price_cents <= int(max_price * 100))

        sort_map = {
            'newest':     desc(MarketplaceListing.created_at),
            'price_asc':  MarketplaceListing.price_cents,
            'price_desc': desc(MarketplaceListing.price_cents),
            'rating':     desc(MarketplaceListing.rating),
            'popular':    desc(MarketplaceListing.downloads_count),
        }
        query = query.order_by(
            desc(MarketplaceListing.is_boosted),   # boosted listings float to top
            sort_map.get(sort, desc(MarketplaceListing.created_at))
        )

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'listings': [l.to_dict() for l in pagination.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/listings/<int:listing_id>', methods=['GET'])
def get_listing(listing_id):
    """Get single listing detail and increment view count."""
    try:
        listing = MarketplaceListing.query.get(listing_id)
        if not listing or not listing.is_active:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        if listing.status != 'published':
            return jsonify({'success': False, 'error': 'Listing not available'}), 404

        listing.increment_views()

        return jsonify({'success': True, 'listing': listing.to_dict()}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# SELLER REGISTRATION & PROFILE
# ------------------------------------------------------------------

@marketplace_bp.route('/seller/register', methods=['POST'])
@jwt_required()
def register_seller():
    """Register the current user as a marketplace seller."""
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json() or {}

        # Check already registered
        existing = Seller.query.filter_by(user_id=user_id).first()
        if existing:
            return jsonify({
                'success': True,
                'seller': existing.to_dict(),
                'message': 'Already registered as a seller'
            }), 200

        seller = Seller(
            user_id=user_id,
            bio=data.get('bio', ''),
            specialization_categories=data.get('specialization_categories', []),
        )
        db.session.add(seller)
        db.session.commit()

        return jsonify({'success': True, 'seller': seller.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/seller/me', methods=['GET'])
@jwt_required()
def get_my_seller_profile():
    """Get current user's seller profile."""
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        if not seller:
            return jsonify({'success': False, 'error': 'Not registered as a seller'}), 404

        return jsonify({'success': True, 'seller': seller.to_dict()}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# LISTING CRUD
# ------------------------------------------------------------------

@marketplace_bp.route('/listings', methods=['POST'])
@jwt_required()
def create_listing():
    """
    Create a new listing in DRAFT status.
    The seller can upload files and then publish separately.
    """
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        if not seller:
            return jsonify({
                'success': False,
                'error': 'You must register as a seller first'
            }), 403

        if not seller.is_active:
            return jsonify({'success': False, 'error': 'Seller account is suspended'}), 403

        data = request.get_json() or {}

        # Validate required fields
        required = ['title', 'description', 'price', 'category_id']
        missing  = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing)}'
            }), 400

        # Validate category exists
        category = MarketplaceCategory.query.get(data['category_id'])
        if not category or not category.is_active:
            return jsonify({'success': False, 'error': 'Invalid category'}), 400

        # Convert price to cents
        try:
            price_cents = int(round(float(data['price']) * 100))
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid price'}), 400

        if price_cents <= 0:
            return jsonify({'success': False, 'error': 'Price must be greater than zero'}), 400

        # Validate item_type if provided
        item_type = data.get('item_type', '')
        if item_type and category.allowed_types:
            if item_type not in category.allowed_types:
                return jsonify({
                    'success': False,
                    'error': f'item_type "{item_type}" not allowed in {category.name}. '
                             f'Allowed: {", ".join(category.allowed_types)}'
                }), 400

        listing = MarketplaceListing(
            seller_id=seller.id,
            category_id=category.id,
            title=data['title'].strip(),
            description=data['description'].strip(),
            item_type=item_type,
            price_cents=price_cents,
            tags=data.get('tags', []),
            status='draft',
        )
        db.session.add(listing)
        db.session.commit()

        return jsonify({'success': True, 'listing': listing.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/listings/<int:listing_id>', methods=['PUT'])
@jwt_required()
def update_listing(listing_id):
    """Update a draft or published listing (seller only)."""
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        if not seller:
            return jsonify({'success': False, 'error': 'Not registered as a seller'}), 403

        listing = MarketplaceListing.query.get(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        if listing.seller_id != seller.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        if listing.status == 'archived':
            return jsonify({'success': False, 'error': 'Cannot edit an archived listing'}), 400

        data = request.get_json() or {}

        updatable = ['title', 'description', 'item_type', 'tags']
        for field in updatable:
            if field in data:
                setattr(listing, field, data[field])

        if 'price' in data:
            try:
                listing.price_cents = int(round(float(data['price']) * 100))
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': 'Invalid price'}), 400

        if 'category_id' in data:
            cat = MarketplaceCategory.query.get(data['category_id'])
            if not cat or not cat.is_active:
                return jsonify({'success': False, 'error': 'Invalid category'}), 400
            listing.category_id = cat.id

        listing.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'listing': listing.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/listings/<int:listing_id>/publish', methods=['POST'])
@jwt_required()
def publish_listing(listing_id):
    """Publish a draft listing — makes it visible in the marketplace."""
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        if not seller:
            return jsonify({'success': False, 'error': 'Not registered as a seller'}), 403

        listing = MarketplaceListing.query.get(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        if listing.seller_id != seller.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        listing.publish()

        return jsonify({'success': True, 'listing': listing.to_dict()}), 200

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/listings/<int:listing_id>/archive', methods=['POST'])
@jwt_required()
def archive_listing(listing_id):
    """Seller archives their listing."""
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        listing = MarketplaceListing.query.get(listing_id)
        if not listing or listing.seller_id != seller.id:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404

        listing.archive()
        return jsonify({'success': True, 'listing': listing.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# FILE UPLOAD ENDPOINTS
# ------------------------------------------------------------------

@marketplace_bp.route('/listings/<int:listing_id>/upload', methods=['POST'])
@jwt_required()
def upload_product_file(listing_id):
    """
    Upload the main downloadable product file.
    Accepts multipart/form-data with field name 'file'.
    Max size: 50MB.
    """
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        if not seller:
            return jsonify({'success': False, 'error': 'Not registered as a seller'}), 403

        listing = MarketplaceListing.query.get(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        if listing.seller_id != seller.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'success': False, 'error': 'Empty filename'}), 400

        if not allowed_product_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'File type not allowed. Allowed: {", ".join(sorted(ALLOWED_PRODUCT_EXTENSIONS))}'
            }), 400

        if not validate_file_size(file, MAX_FILE_SIZE):
            return jsonify({
                'success': False,
                'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB'
            }), 400

        # Delete old file if replacing
        if listing.file_url:
            old_path = os.path.join(BASE_DIR, listing.file_url.lstrip('/'))
            if os.path.exists(old_path):
                os.remove(old_path)

        file_info = save_product_file(file, seller.id)

        listing.file_url        = file_info['url']
        listing.file_name       = file_info['name']
        listing.file_size_bytes = file_info['size']
        listing.file_type       = file_info['type']
        listing.updated_at      = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'file': {
                'url':  file_info['url'],
                'name': file_info['name'],
                'size': file_info['size'],
                'type': file_info['type'],
            },
            'listing': listing.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/listings/<int:listing_id>/previews', methods=['POST'])
@jwt_required()
def upload_preview_images(listing_id):
    """
    Upload preview images for a listing.
    Accepts multipart/form-data with field name 'images' (multiple allowed).
    Max 5 previews total. Max 5MB each.
    """
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        if not seller:
            return jsonify({'success': False, 'error': 'Not registered as a seller'}), 403

        listing = MarketplaceListing.query.get(listing_id)
        if not listing or listing.seller_id != seller.id:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404

        files = request.files.getlist('images')
        if not files:
            return jsonify({'success': False, 'error': 'No images provided'}), 400

        current_previews = listing.preview_images or []
        remaining_slots  = MAX_PREVIEWS - len(current_previews)

        if remaining_slots <= 0:
            return jsonify({
                'success': False,
                'error': f'Maximum {MAX_PREVIEWS} preview images allowed'
            }), 400

        new_urls = []
        for file in files[:remaining_slots]:
            if not file.filename:
                continue
            if not allowed_preview(file.filename):
                return jsonify({
                    'success': False,
                    'error': f'Preview must be an image (png, jpg, jpeg, webp, gif)'
                }), 400
            if not validate_file_size(file, MAX_PREVIEW_SIZE):
                return jsonify({
                    'success': False,
                    'error': f'Preview image too large. Max {MAX_PREVIEW_SIZE // (1024*1024)}MB'
                }), 400
            url = save_preview_image(file, seller.id)
            new_urls.append(url)

        listing.preview_images = current_previews + new_urls
        listing.updated_at     = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'preview_images': listing.preview_images,
            'listing': listing.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/listings/<int:listing_id>/previews/<int:preview_index>', methods=['DELETE'])
@jwt_required()
def delete_preview_image(listing_id, preview_index):
    """Remove a specific preview image by its index."""
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        listing = MarketplaceListing.query.get(listing_id)
        if not listing or listing.seller_id != seller.id:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404

        previews = list(listing.preview_images or [])
        if preview_index < 0 or preview_index >= len(previews):
            return jsonify({'success': False, 'error': 'Invalid preview index'}), 400

        # Delete file from disk
        url = previews[preview_index]
        old_path = os.path.join(BASE_DIR, url.lstrip('/'))
        if os.path.exists(old_path):
            os.remove(old_path)

        previews.pop(preview_index)
        listing.preview_images = previews
        db.session.commit()

        return jsonify({'success': True, 'preview_images': listing.preview_images}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# MY LISTINGS (SELLER VIEW)
# ------------------------------------------------------------------

@marketplace_bp.route('/my-listings', methods=['GET'])
@jwt_required()
def get_my_listings():
    """Get all listings belonging to the current seller."""
    try:
        user_id = int(get_jwt_identity())
        seller  = Seller.query.filter_by(user_id=user_id).first()

        if not seller:
            return jsonify({'success': False, 'error': 'Not registered as a seller'}), 404

        status = request.args.get('status')   # optional filter
        query  = MarketplaceListing.query.filter_by(seller_id=seller.id)
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(desc(MarketplaceListing.created_at))

        listings = query.all()
        return jsonify({
            'success': True,
            'listings': [l.to_dict(include_seller=False) for l in listings]
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# ADMIN ENDPOINTS
# ------------------------------------------------------------------

@marketplace_bp.route('/admin/listings', methods=['GET'])
@jwt_required()
def admin_get_all_listings():
    """Admin: get all listings regardless of status."""
    try:
        user_id = int(get_jwt_identity())
        if not require_admin(user_id):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        page     = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status   = request.args.get('status')

        query = MarketplaceListing.query
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(desc(MarketplaceListing.created_at))

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            'success': True,
            'listings': [l.to_dict() for l in pagination.items],
            'pagination': {
                'page': page, 'per_page': per_page,
                'total': pagination.total, 'pages': pagination.pages
            }
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/admin/listings/<int:listing_id>/reject', methods=['POST'])
@jwt_required()
def admin_reject_listing(listing_id):
    """Admin rejects a listing that doesn't meet marketplace rules."""
    try:
        user_id = int(get_jwt_identity())
        if not require_admin(user_id):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        listing = MarketplaceListing.query.get(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404

        data   = request.get_json() or {}
        reason = data.get('reason', 'Does not meet marketplace content guidelines')
        listing.reject(reason)

        # Notify the seller
        if listing.seller:
            notification_service.create_notification(
                user_id=listing.seller.user_id,
                template_key='MARKETPLACE_LISTING_REJECTED',
                entity_type='marketplace_listing',
                entity_id=listing_id,
                variables={
                    'listing_title': listing.title,
                    'reason': reason,
                },
                link_url='/marketplace',
            )

        return jsonify({'success': True, 'listing': listing.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/admin/seller/<int:seller_id>/verify', methods=['PUT'])
@jwt_required()
def admin_verify_seller(seller_id):
    """Admin verifies or suspends a seller account."""
    try:
        user_id = int(get_jwt_identity())
        if not require_admin(user_id):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        seller = Seller.query.get(seller_id)
        if not seller:
            return jsonify({'success': False, 'error': 'Seller not found'}), 404

        data   = request.get_json() or {}
        status = data.get('status')
        if status not in ('verified', 'suspended', 'unverified', 'pending'):
            return jsonify({
                'success': False,
                'error': 'status must be one of: verified, suspended, unverified, pending'
            }), 400

        seller.verification_status = status
        db.session.commit()

        return jsonify({'success': True, 'seller': seller.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# PURCHASE ENDPOINT
# ------------------------------------------------------------------

@marketplace_bp.route('/listings/<int:listing_id>/purchase', methods=['POST'])
@jwt_required()
def purchase_listing(listing_id):
    """
    Purchase a marketplace listing using real Balance (not Crystals).

    Flow:
      1. Validate listing is published and buyer has enough Balance
      2. Check buyer hasn't already purchased this listing
      3. Debit buyer's Balance (full price)
      4. Credit seller's Balance (90%)
      5. Record platform fee (10%) — stays in platform
      6. Create MarketplacePurchase record
      7. Increment listing download count
      8. Record seller delivery
    """
    try:
        buyer_id = int(get_jwt_identity())

        listing = MarketplaceListing.query.get(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        if listing.status != 'published' or not listing.is_active:
            return jsonify({'success': False, 'error': 'Listing is not available'}), 400

        # Cannot buy your own listing
        seller = Seller.query.get(listing.seller_id)
        if seller and seller.user_id == buyer_id:
            return jsonify({'success': False, 'error': 'Cannot purchase your own listing'}), 400

        # Idempotency — prevent double purchase
        existing = MarketplacePurchase.query.filter_by(
            buyer_id=buyer_id,
            listing_id=listing_id,
            status='completed'
        ).first()
        if existing:
            return jsonify({
                'success': True,
                'already_purchased': True,
                'purchase': existing.to_dict(),
                'download_url': listing.file_url,
                'message': 'You already own this resource'
            }), 200

        # Digital products have unlimited stock — no stock check needed

        # Get or create buyer Balance
        buyer_balance = Balance.query.filter_by(user_id=buyer_id).first()
        if not buyer_balance:
            buyer_balance = Balance(user_id=buyer_id)
            db.session.add(buyer_balance)
            db.session.flush()

        price_cents    = listing.price_cents
        fee_cents      = listing.platform_fee_cents    # 10%
        seller_cents   = listing.seller_receives_cents  # 90%

        # Check buyer has enough
        if buyer_balance.available < price_cents:
            return jsonify({
                'success': False,
                'error': 'Insufficient Balance',
                'available': buyer_balance.available / 100,
                'required': price_cents / 100,
                'shortfall': (price_cents - buyer_balance.available) / 100,
            }), 400

        # --- Debit buyer ---
        buyer_tx = buyer_balance.pay(
            cents=price_cents,
            reference_type='marketplace_purchase',
            reference_id=str(listing_id),
            description=f'Purchase: {listing.title}'
        )

        # --- Credit seller (90%) ---
        seller_balance = Balance.query.filter_by(user_id=seller.user_id).first()
        if not seller_balance:
            seller_balance = Balance(user_id=seller.user_id)
            db.session.add(seller_balance)
            db.session.flush()

        seller_tx = seller_balance.receive(
            cents=seller_cents,
            reference_type='marketplace_sale',
            reference_id=str(listing_id),
            description=f'Sale: {listing.title}'
        )

        # Update seller counters
        seller.total_earned_cents   += seller_cents
        seller.pending_payout_cents += seller_cents
        seller.record_delivery()

        listing.increment_downloads()

        # Create purchase record
        purchase = MarketplacePurchase(
            buyer_id=buyer_id,
            seller_id=seller.id,
            listing_id=listing_id,
            price_cents=price_cents,
            platform_fee_cents=fee_cents,
            seller_cut_cents=seller_cents,
            buyer_tx_id=buyer_tx.id if buyer_tx else None,
            seller_tx_id=seller_tx.id if seller_tx else None,
            status='completed',
        )
        db.session.add(purchase)
        db.session.commit()

        # ── Notify seller of new sale ──────────────────────────────
        buyer = User.query.get(buyer_id)
        buyer_name = f"{buyer.first_name} {buyer.last_name}" if buyer else 'Someone'

        notification_service.create_notification(
            user_id=seller.user_id,
            template_key='MARKETPLACE_NEW_PURCHASE',
            actor_id=buyer_id,
            entity_type='marketplace_listing',
            entity_id=listing_id,
            variables={
                'buyer_name': buyer_name,
                'listing_title': listing.title,
                'amount': f"{price_cents / 100:.2f}",
            },
            link_url='/marketplace',
        )

        # ── Notify buyer of successful purchase ────────────────────
        notification_service.create_notification(
            user_id=buyer_id,
            template_key='MARKETPLACE_PURCHASE_CONFIRMED',
            actor_id=seller.user_id,
            entity_type='marketplace_listing',
            entity_id=listing_id,
            variables={'listing_title': listing.title},
            link_url='/marketplace',
        )

        return jsonify({
            'success': True,
            'purchase': purchase.to_dict(),
            'download_url': listing.file_url,
            'buyer_balance': buyer_balance.to_dict(),
            'message': f'Successfully purchased "{listing.title}"'
        }), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/listings/<int:listing_id>/download', methods=['GET'])
@jwt_required()
def download_listing(listing_id):
    """
    Get the download URL for a purchased listing.
    Only buyers who have completed a purchase can access this.
    """
    try:
        buyer_id = int(get_jwt_identity())

        purchase = MarketplacePurchase.query.filter_by(
            buyer_id=buyer_id,
            listing_id=listing_id,
            status='completed'
        ).first()

        if not purchase:
            return jsonify({
                'success': False,
                'error': 'You have not purchased this listing'
            }), 403

        listing = MarketplaceListing.query.get(listing_id)
        if not listing or not listing.file_url:
            return jsonify({'success': False, 'error': 'File not available'}), 404

        return jsonify({
            'success': True,
            'download_url': listing.file_url,
            'file_name': listing.file_name,
            'file_size': listing.file_size_bytes,
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/my-purchases', methods=['GET'])
@jwt_required()
def get_my_purchases():
    """Get all listings the current user has purchased."""
    try:
        buyer_id = int(get_jwt_identity())
        purchases = MarketplacePurchase.query.filter_by(
            buyer_id=buyer_id, status='completed'
        ).order_by(desc(MarketplacePurchase.purchased_at)).all()

        return jsonify({
            'success': True,
            'purchases': [p.to_dict() for p in purchases]
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# RATING ENDPOINT
# ------------------------------------------------------------------

@marketplace_bp.route('/purchases/<int:purchase_id>/rate', methods=['POST'])
@jwt_required()
def rate_purchase(purchase_id):
    """
    Buyer rates a listing after purchase.
    One rating per purchase. Score must be 1–5.

    Body:
      rating      (float) — 1.0 to 5.0
      review_text (str, optional)
    """
    try:
        buyer_id = int(get_jwt_identity())
        data     = request.get_json() or {}

        purchase = MarketplacePurchase.query.get(purchase_id)
        if not purchase:
            return jsonify({'success': False, 'error': 'Purchase not found'}), 404
        if purchase.buyer_id != buyer_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        if purchase.status != 'completed':
            return jsonify({'success': False, 'error': 'Can only rate completed purchases'}), 400
        if purchase.rating is not None:
            return jsonify({'success': False, 'error': 'You have already rated this purchase'}), 400

        score = data.get('rating')
        if score is None:
            return jsonify({'success': False, 'error': 'rating is required'}), 400

        try:
            score = float(score)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'rating must be a number'}), 400

        if not 1 <= score <= 5:
            return jsonify({'success': False, 'error': 'rating must be between 1 and 5'}), 400

        # Save rating on purchase
        purchase.rating      = score
        purchase.review_text = data.get('review_text', '').strip() or None
        purchase.rated_at    = datetime.utcnow()

        # Update listing average rating
        listing = MarketplaceListing.query.get(purchase.listing_id)
        if listing:
            listing.add_rating(score)

        db.session.commit()

        # ── Notify seller of new rating ────────────────────────────
        if listing and listing.seller:
            buyer = User.query.get(buyer_id)
            notification_service.create_notification(
                user_id=listing.seller.user_id,
                template_key='MARKETPLACE_LISTING_RATED',
                actor_id=buyer_id,
                entity_type='marketplace_listing',
                entity_id=listing.id,
                variables={
                    'buyer_name': f"{buyer.first_name} {buyer.last_name}" if buyer else 'A buyer',
                    'listing_title': listing.title,
                    'rating': score,
                },
                link_url='/marketplace',
            )

        return jsonify({
            'success': True,
            'purchase': purchase.to_dict(),
            'listing_rating': listing.rating if listing else None,
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# SELLER PAYOUT ENDPOINT
# ------------------------------------------------------------------

@marketplace_bp.route('/seller/payout', methods=['POST'])
@jwt_required()
def request_seller_payout():
    """
    Seller requests a payout of their pending earnings to their Balance wallet.

    The pending_payout_cents on the Seller model tracks money owed to the seller.
    This endpoint moves it from pending_payout → seller's available Balance.

    In production this would trigger a Stripe Connect payout to their bank.
    For now it immediately credits their Balance wallet.
    """
    try:
        user_id = int(get_jwt_identity())

        seller = Seller.query.filter_by(user_id=user_id).first()
        if not seller:
            return jsonify({'success': False, 'error': 'Not registered as a seller'}), 404

        if seller.pending_payout_cents <= 0:
            return jsonify({'success': False, 'error': 'No pending earnings to pay out'}), 400

        # Minimum payout $5
        if seller.pending_payout_cents < 500:
            return jsonify({
                'success': False,
                'error': f'Minimum payout is $5.00. Current pending: ${seller.pending_payout_cents / 100:.2f}'
            }), 400

        amount_cents = seller.pending_payout_cents

        # Credit seller's Balance
        balance = Balance.query.filter_by(user_id=user_id).first()
        if not balance:
            balance = Balance(user_id=user_id)
            db.session.add(balance)
            db.session.flush()

        balance.receive(
            cents=amount_cents,
            reference_type='seller_payout',
            description=f'Marketplace payout — ${amount_cents / 100:.2f}'
        )

        # Clear pending
        seller.pending_payout_cents = 0
        db.session.commit()

        return jsonify({
            'success': True,
            'paid_out': amount_cents / 100,
            'balance': balance.to_dict(),
            'seller': seller.to_dict(),
            'message': f'${amount_cents / 100:.2f} paid to your Balance wallet'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/seller/earnings', methods=['GET'])
@jwt_required()
def get_seller_earnings():
    """Get seller's earnings summary and recent sales."""
    try:
        user_id = int(get_jwt_identity())

        seller = Seller.query.filter_by(user_id=user_id).first()
        if not seller:
            return jsonify({'success': False, 'error': 'Not registered as a seller'}), 404

        # Recent sales
        recent_sales = MarketplacePurchase.query.filter_by(
            seller_id=seller.id, status='completed'
        ).order_by(desc(MarketplacePurchase.purchased_at)).limit(20).all()

        # Sales by listing
        from sqlalchemy import func
        sales_by_listing = db.session.query(
            MarketplacePurchase.listing_id,
            func.count(MarketplacePurchase.id).label('count'),
            func.sum(MarketplacePurchase.seller_cut_cents).label('total_cents')
        ).filter_by(seller_id=seller.id, status='completed')\
         .group_by(MarketplacePurchase.listing_id).all()

        return jsonify({
            'success': True,
            'earnings': {
                'total_earned': seller.total_earned_cents / 100,
                'pending_payout': seller.pending_payout_cents / 100,
                'sales_count': len(recent_sales),
            },
            'recent_sales': [s.to_dict() for s in recent_sales],
            'sales_by_listing': [
                {
                    'listing_id': str(r.listing_id),
                    'count': r.count,
                    'total_earned': r.total_cents / 100,
                }
                for r in sales_by_listing
            ]
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# CRYSTAL BOOST ENDPOINT
# ------------------------------------------------------------------

# Crystal cost per 24h boost unit for marketplace listings
LISTING_BOOST_COST = 100   # 100 crystals / 24h per SF Economy docs

@marketplace_bp.route('/listings/<int:listing_id>/boost', methods=['POST'])
@jwt_required()
def boost_listing(listing_id):
    """
    Boost a marketplace listing's visibility using Crystals.

    RULE: Crystals are NOT money. They only accelerate discovery.
          They CANNOT be used to pay for listings or reduce prices.

    Body:
      duration_units (int, optional) — number of 24h blocks (default: 1)

    Cost: 100 crystals per 24h block.
    Effect: listing floats to top of discovery feed while boost is active.
    """
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json() or {}

        listing = MarketplaceListing.query.get(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404

        # Only seller can boost their own listing
        seller = Seller.query.filter_by(user_id=user_id).first()
        if not seller or listing.seller_id != seller.id:
            return jsonify({'success': False, 'error': 'Only the seller can boost this listing'}), 403

        if listing.status != 'published':
            return jsonify({'success': False, 'error': 'Only published listings can be boosted'}), 400

        duration_units = max(1, int(data.get('duration_units', 1)))
        total_cost     = LISTING_BOOST_COST * duration_units

        # Get or create crystal wallet
        crystal_wallet = CrystalWallet.query.filter_by(user_id=user_id).first()
        if not crystal_wallet:
            crystal_wallet = CrystalWallet(user_id=user_id)
            db.session.add(crystal_wallet)
            db.session.flush()

        if crystal_wallet.balance < total_cost:
            return jsonify({
                'success': False,
                'error': 'Insufficient crystals',
                'balance': crystal_wallet.balance,
                'required': total_cost,
                'shortfall': total_cost - crystal_wallet.balance,
            }), 400

        # Spend crystals
        crystal_wallet.spend_crystals(
            amount=total_cost,
            usage_type='listing_promotion',
            description=f'Boost listing: {listing.title} ({duration_units}×24h)',
            reference_id=str(listing_id),
        )

        # Apply boost to listing
        from datetime import timedelta
        now        = datetime.utcnow()
        # If already boosted, extend from current expiry
        if listing.is_boost_active() and listing.boost_expires_at:
            new_expiry = listing.boost_expires_at + timedelta(hours=24 * duration_units)
        else:
            new_expiry = now + timedelta(hours=24 * duration_units)

        listing.is_boosted       = True
        listing.boost_expires_at = new_expiry

        db.session.commit()

        return jsonify({
            'success': True,
            'boost': {
                'listing_id': str(listing_id),
                'crystals_spent': total_cost,
                'duration_hours': 24 * duration_units,
                'expires_at': new_expiry.isoformat(),
                'is_active': True,
            },
            'crystal_wallet': crystal_wallet.to_dict(),
            'message': f'Listing boosted for {duration_units * 24} hours!'
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@marketplace_bp.route('/listings/<int:listing_id>/boost', methods=['GET'])
@jwt_required()
def get_boost_status(listing_id):
    """Check the current boost status of a listing."""
    try:
        listing = MarketplaceListing.query.get(listing_id)
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404

        return jsonify({
            'success': True,
            'is_boosted': listing.is_boost_active(),
            'expires_at': listing.boost_expires_at.isoformat() if listing.boost_expires_at else None,
            'cost_per_24h': LISTING_BOOST_COST,
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500