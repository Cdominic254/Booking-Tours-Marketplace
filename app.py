import ipaddress
import hashlib
from io import BytesIO
import json
import math
import os
import re
import secrets
import smtplib
import sys
import tempfile
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from functools import wraps
from email.message import EmailMessage

from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, redirect, request, send_file, send_from_directory, session
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import case, or_, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from saas.extensions import db
from saas.fees import (
    BOOKING_FEE,
    GUEST_SERVICE_FEE_RATE,
    HOST_COMMISSION_RATE,
    SUBSCRIBER_HOST_COMMISSION_RATE,
    SUBSCRIPTION_MONTHLY_FEE,
    split_fee_quote,
)
from saas.modules.analytics.models import AnalyticsEvent
from saas.modules.bookings.models import Booking, BookingDispute
from saas.modules.bookings.daraja import (
    DarajaError,
    initiate_stk_push,
    is_configured as is_daraja_configured,
    query_stk_push,
)
from saas.modules.bookings.settings import AdminSetting
from saas.modules.bookings.service import (
    KENYA_TIMEZONE,
    calculate_booking_price as calculate_booking_price_service,
    parse_local_datetime,
    release_schedule,
    reserve_schedule,
    save_booking as save_booking_service,
)
from saas.modules.catalog.availability import (
    check_in_cutoff,
    clear_availability_day,
    parse_stay_date,
    release_room_nights,
    reserve_room_nights,
    room_calendar,
    stay_nights,
    stay_option,
    update_availability_range,
)
from saas.brand import BRAND_DOMAIN, BRAND_NAME, BRAND_SOCIAL_HANDLE
from saas.modules.catalog.models import (
    Destination,
    Property,
    PropertyAvailability,
    PropertyRoom,
    Promotion,
    Review,
    Service,
    Tour,
    TourSchedule,
    PROMOTION_LISTING_TYPES,
    PROMOTION_TIERS,
    SERVICE_PRICE_UNITS,
    SERVICE_TYPES,
    TOUR_GROUP_TYPES,
    TOUR_TYPES,
)
from saas.modules.identity.models import (
    VENDOR_BUSINESS_TYPES,
    AdminAccount,
    SavedItem,
    User,
    VendorAccount,
    VendorSubscriptionPayment,
)
from saas.modules.messaging.models import ChatConversation, ChatMessage, NewsletterSubscriber, Submission

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIST = os.path.join(BASE_DIR, 'frontend', 'dist')
UPLOAD_DIR = os.path.abspath(os.environ.get('UPLOAD_DIR', os.path.join(BASE_DIR, 'uploads')))

EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USERNAME = os.environ.get('EMAIL_USERNAME', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', EMAIL_USERNAME)
EMAIL_TO = os.environ.get('EMAIL_TO', f'info@{BRAND_DOMAIN}')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
whatsapp_phone = re.sub(r'\D', '', os.environ.get('WHATSAPP_BUSINESS_PHONE', ''))
WHATSAPP_BUSINESS_PHONE = whatsapp_phone if 8 <= len(whatsapp_phone) <= 15 else ''
SITE_URL = os.environ.get('SITE_URL', f'https://{BRAND_DOMAIN}').strip().rstrip('/')
# One prepaid month of a partner subscription.
VENDOR_SUBSCRIPTION_PERIOD = timedelta(days=30)
# A blank setting falls back to the brand's official @safarinasstay profile so the
# footer and share rows always link to the branded identity. Set any SOCIAL_*
# variable to a non-URL value (for example "off") to hide that network.
SOCIAL_PROFILE_SETTINGS = (
    ('Instagram', 'SOCIAL_INSTAGRAM_URL', 'instagram', f'https://www.instagram.com/{BRAND_SOCIAL_HANDLE}/'),
    ('Facebook', 'SOCIAL_FACEBOOK_URL', 'facebook', f'https://www.facebook.com/{BRAND_SOCIAL_HANDLE}'),
    ('X', 'SOCIAL_X_URL', 'x', f'https://x.com/{BRAND_SOCIAL_HANDLE}'),
    ('TikTok', 'SOCIAL_TIKTOK_URL', 'tiktok', f'https://www.tiktok.com/@{BRAND_SOCIAL_HANDLE}'),
    ('YouTube', 'SOCIAL_YOUTUBE_URL', 'youtube', f'https://www.youtube.com/@{BRAND_SOCIAL_HANDLE}'),
)
IS_VERCEL = os.environ.get('VERCEL') == '1'
IS_PRODUCTION = (
    os.environ.get('FLASK_ENV', '').lower() == 'production'
    or IS_VERCEL
    or (bool(os.environ.get('SITE_URL')) and SITE_URL.startswith('https://'))
)


def social_profile_links():
    """Public social profiles, defaulting to the brand's official social identity."""
    links = []
    for label, setting, icon, default_href in SOCIAL_PROFILE_SETTINGS:
        href = (os.environ.get(setting) or '').strip() or default_href
        if href.startswith(('https://', 'http://')):
            links.append({'label': label, 'href': href, 'icon': icon})
    return links


def warn_deployment_config(message):
    """Report a degraded production setting without stopping the deployment.

    An exception raised while importing this module becomes
    FUNCTION_INVOCATION_FAILED for every request on Vercel, so missing
    configuration is surfaced as a startup warning instead.
    """
    print(f'WARNING: {message}', file=sys.stderr, flush=True)


# Redis integrations expose the connection string under different names on
# Vercel (Upstash / KV marketplace resources prefix the variables, e.g.
# RATELIMIT_STORAGE_REDIS_URL or RATELIMIT_STORAGE_KV_URL), so every common
# alias is accepted. "memory://" stays the local-development default.
RATE_LIMIT_STORAGE_ENV_VARS = (
    'RATELIMIT_STORAGE_URI',
    'RATELIMIT_STORAGE_URL',
    'RATELIMIT_STORAGE_REDIS_URL',
    'RATELIMIT_STORAGE_KV_URL',
    'REDIS_URL',
    'KV_URL',
)
RATE_LIMIT_STORAGE_URI = 'memory://'
for _storage_var in RATE_LIMIT_STORAGE_ENV_VARS:
    _storage_value = (os.environ.get(_storage_var) or '').strip().strip('"\'')
    if _storage_value.lower().startswith(('redis://', 'rediss://')):
        RATE_LIMIT_STORAGE_URI = _storage_value
        break
    if _storage_value.lower().startswith('memory://'):
        RATE_LIMIT_STORAGE_URI = _storage_value
        break
if IS_PRODUCTION and RATE_LIMIT_STORAGE_URI.startswith('memory://'):
    # Serverless instances are temporary, so limits stay locally scoped until a
    # shared backend is configured.
    warn_deployment_config(
        'rate limiting falls back to memory:// in production; set RATELIMIT_STORAGE_URI '
        'to a shared Redis URL (rediss://...) for cross-instance limits.'
    )

# Database and session secrets are resolved before the Flask app is created so
# a missing value degrades the deployment instead of aborting the import.
database_url = (os.environ.get('DATABASE_URL') or '').strip()
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
if not database_url:
    if IS_VERCEL:
        # Serverless bundles are read-only; /tmp is the only writable location.
        sqlite_path = os.path.join(tempfile.gettempdir(), 'submissions.db')
        warn_deployment_config(
            'DATABASE_URL is not set, so ephemeral SQLite is used at '
            f'{sqlite_path}. Bookings and accounts are lost on every cold start; '
            'connect PostgreSQL (DATABASE_URL=postgresql://...).'
        )
    else:
        sqlite_path = os.path.join(BASE_DIR, 'submissions.db')
    database_url = f'sqlite:///{sqlite_path}'


def resolve_session_secret_key():
    """Pick a session signing key instead of refusing to start without one."""
    configured_key = (os.environ.get('SECRET_KEY') or '').strip()
    if configured_key:
        return configured_key
    if database_url.startswith('postgresql://'):
        # Derive a stable key so every serverless instance agrees on session
        # signatures; the DATABASE_URL credentials stay private.
        warn_deployment_config(
            'SECRET_KEY is not set; session signatures are derived from DATABASE_URL. '
            'Set SECRET_KEY to a long random value and invalidate existing sessions.'
        )
        return hashlib.sha256(f'{BRAND_DOMAIN}-session|{database_url}'.encode('utf-8')).hexdigest()
    warn_deployment_config(
        'SECRET_KEY is not set and no PostgreSQL DATABASE_URL is available, so an '
        'ephemeral key is generated. Sessions, CSRF tokens, and login cookies will not '
        'survive a restart or reach another instance; set SECRET_KEY.'
    )
    return secrets.token_hex(32)


SESSION_SECRET_KEY = resolve_session_secret_key()

CURRENCY_CACHE_TTL = 60 * 60 * 12
CURRENCY_API_TIMEOUT = 4
_currency_cache_lock = threading.Lock()
_exchange_rates_cache = {'expires_at': 0.0, 'rates': None, 'updated_at': None}
_geolocation_cache = {}

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = SESSION_SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION or os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri=RATE_LIMIT_STORAGE_URI,
    headers_enabled=True,
)

# Vercel terminates TLS at its edge and forwards the visitor address in
# X-Forwarded-For. Without ProxyFix every request would look like it came from
# the proxy, so IP rate limits would be shared by all visitors and generated
# URLs would use the internal host. Other reverse proxies opt in explicitly.
if IS_VERCEL or os.environ.get('TRUST_PROXY_HEADERS', '').lower() in ('1', 'true', 'yes'):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), geolocation=(), microphone=()')
    if app.config['SESSION_COOKIE_SECURE']:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000')
    return response


@app.after_request
def cache_static_assets(response):
    """Let the Vercel edge cache hashed bundles and bundled photography."""
    if request.method != 'GET' or response.status_code != 200:
        return response
    path = request.path
    if path.startswith('/assets/'):
        cache_control = 'public, max-age=31536000, immutable'
    elif path.startswith(('/images/', '/pictures/')) or path == '/logo.svg':
        cache_control = 'public, max-age=86400'
    else:
        return response
    response.headers['Cache-Control'] = cache_control
    response.headers['Vercel-CDN-Cache-Control'] = cache_control
    return response


app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
db.init_app(app)

def ensure_booking_payment_columns():
    inspector = db.inspect(db.engine)
    booking_columns = {column['name'] for column in inspector.get_columns('booking')}
    with db.engine.begin() as connection:
        if 'amount' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN amount FLOAT NOT NULL DEFAULT 0.0'))
        if 'payment_status' not in booking_columns:
            connection.execute(text("ALTER TABLE booking ADD COLUMN payment_status VARCHAR(30) NOT NULL DEFAULT 'pending'"))
        if 'payment_reference' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN payment_reference VARCHAR(64)'))
        if 'checkout_request_id' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN checkout_request_id VARCHAR(100)'))
        if 'merchant_request_id' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN merchant_request_id VARCHAR(100)'))
        if 'mpesa_receipt_number' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN mpesa_receipt_number VARCHAR(30)'))
        if 'payment_confirmed_at' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN payment_confirmed_at TIMESTAMP'))
        if 'traffic_source' not in booking_columns:
            connection.execute(text("ALTER TABLE booking ADD COLUMN traffic_source VARCHAR(120) NOT NULL DEFAULT 'Unattributed'"))
        if 'user_id' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN user_id INTEGER'))
        if 'schedule_id' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN schedule_id INTEGER'))
        if 'status' not in booking_columns:
            connection.execute(text("ALTER TABLE booking ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'requested'"))
        if 'commission_rate' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN commission_rate FLOAT NOT NULL DEFAULT 15.0'))
        if 'subtotal_amount' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN subtotal_amount FLOAT NOT NULL DEFAULT 0.0'))
            connection.execute(text('ALTER TABLE booking ADD COLUMN service_fee_amount FLOAT NOT NULL DEFAULT 0.0'))
            connection.execute(text('ALTER TABLE booking ADD COLUMN host_commission_amount FLOAT NOT NULL DEFAULT 0.0'))
            connection.execute(text('ALTER TABLE booking ADD COLUMN host_payout_amount FLOAT NOT NULL DEFAULT 0.0'))
            connection.execute(text('ALTER TABLE booking ADD COLUMN host_commission_rate FLOAT NOT NULL DEFAULT 4.0'))
            connection.execute(text('ALTER TABLE booking ADD COLUMN guest_service_fee_rate FLOAT NOT NULL DEFAULT 9.0'))
            # Bookings taken before the split fee model charged no platform fees,
            # so their full amount is treated as the host's own subtotal.
            connection.execute(text(
                'UPDATE booking SET subtotal_amount = amount, host_payout_amount = amount'
            ))
        if 'booking_fee_amount' not in booking_columns:
            # The flat guest booking fee arrived after the split fee model.
            connection.execute(text('ALTER TABLE booking ADD COLUMN booking_fee_amount FLOAT NOT NULL DEFAULT 0.0'))
        if 'refund_status' not in booking_columns:
            connection.execute(text("ALTER TABLE booking ADD COLUMN refund_status VARCHAR(30) NOT NULL DEFAULT 'none'"))
        if 'booking_type' not in booking_columns:
            connection.execute(text("ALTER TABLE booking ADD COLUMN booking_type VARCHAR(20) NOT NULL DEFAULT 'tour'"))
        if 'property_id' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN property_id INTEGER'))
        if 'room_id' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN room_id INTEGER'))
        if 'check_in' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN check_in VARCHAR(20)'))
        if 'check_out' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN check_out VARCHAR(20)'))
        if 'nights' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN nights INTEGER'))
        connection.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_payment_reference '
            'ON booking (payment_reference)'
        ))
        connection.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_checkout_request_id '
            'ON booking (checkout_request_id)'
        ))
        connection.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_mpesa_receipt_number '
            'ON booking (mpesa_receipt_number)'
        ))


def ensure_identity_columns():
    with db.engine.begin() as connection:
        for table in ('user', 'vendor_account'):
            if db.inspect(connection).has_table(table):
                columns = {column['name'] for column in db.inspect(connection).get_columns(table)}
                if 'is_active' not in columns:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE'))


def ensure_operator_columns():
    """Attach public operator profiles to vendor accounts created earlier."""
    inspector = db.inspect(db.engine)
    if not inspector.has_table('vendor_account'):
        return
    vendor_columns = {column['name'] for column in inspector.get_columns('vendor_account')}
    with db.engine.begin() as connection:
        for column, declaration in {
            'slug': 'VARCHAR(160)',
            'business_types': "VARCHAR(255) NOT NULL DEFAULT ''",
            'description': "TEXT NOT NULL DEFAULT ''",
            'location': "VARCHAR(120) NOT NULL DEFAULT ''",
            'phone': "VARCHAR(50) NOT NULL DEFAULT ''",
            'website': "VARCHAR(255) NOT NULL DEFAULT ''",
            'logo_url': 'VARCHAR(500)',
            'subscription_status': "VARCHAR(20) NOT NULL DEFAULT 'inactive'",
            'subscription_plan': "VARCHAR(40) NOT NULL DEFAULT ''",
            'subscription_started_at': 'TIMESTAMP',
            'subscription_renews_at': 'TIMESTAMP',
            'subscription_monthly_fee': 'FLOAT NOT NULL DEFAULT 0.0',
        }.items():
            if column not in vendor_columns:
                connection.execute(text(f'ALTER TABLE vendor_account ADD COLUMN {column} {declaration}'))
        connection.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_vendor_account_slug ON vendor_account (slug)'
        ))

    # Existing vendors need a stable public page before they can be linked to.
    operators = VendorAccount.query.filter(
        (VendorAccount.slug.is_(None)) | (VendorAccount.slug == '')
    ).all()
    for operator in operators:
        operator.slug = unique_slug(operator.name, VendorAccount, operator.id)
    if operators:
        db.session.commit()


def ensure_review_columns():
    """Attach guest reviews to the booking and customer account that earned them."""
    inspector = db.inspect(db.engine)
    if not inspector.has_table('review'):
        return
    review_columns = {column['name'] for column in inspector.get_columns('review')}
    with db.engine.begin() as connection:
        if 'booking_id' not in review_columns:
            connection.execute(text('ALTER TABLE review ADD COLUMN booking_id INTEGER'))
        if 'user_id' not in review_columns:
            connection.execute(text('ALTER TABLE review ADD COLUMN user_id INTEGER'))
        connection.execute(text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_review_booking ON review (booking_id)'
        ))


def ensure_refund_columns():
    """Track refunds owed after a cancellation and their manual payout."""
    inspector = db.inspect(db.engine)
    if not inspector.has_table('booking'):
        return
    booking_columns = {column['name'] for column in inspector.get_columns('booking')}
    with db.engine.begin() as connection:
        if 'refund_amount' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN refund_amount FLOAT NOT NULL DEFAULT 0.0'))
        if 'refund_reason' not in booking_columns:
            connection.execute(text("ALTER TABLE booking ADD COLUMN refund_reason VARCHAR(255) NOT NULL DEFAULT ''"))
        if 'refund_requested_at' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN refund_requested_at TIMESTAMP'))
        if 'refund_paid_at' not in booking_columns:
            connection.execute(text('ALTER TABLE booking ADD COLUMN refund_paid_at TIMESTAMP'))
        # Earlier refund reviews move onto the payout vocabulary.
        connection.execute(text(
            "UPDATE booking SET refund_status = 'pending' "
            "WHERE refund_status IN ('pending_review', 'approved')"
        ))
        connection.execute(text(
            "UPDATE booking SET refund_status = 'paid' WHERE refund_status = 'completed'"
        ))
        connection.execute(text(
            "UPDATE booking SET refund_amount = amount, "
            "refund_reason = 'Refund paid before refund tracking was added.' "
            "WHERE refund_status = 'paid' AND refund_amount = 0"
        ))


def ensure_admin_settings():
    changed = False
    for key, value in {
        'host_commission_rate': f'{HOST_COMMISSION_RATE:g}',
        'subscriber_host_commission_rate': f'{SUBSCRIBER_HOST_COMMISSION_RATE:g}',
        'guest_service_fee_rate': f'{GUEST_SERVICE_FEE_RATE:g}',
        'booking_fee': f'{BOOKING_FEE:g}',
        'subscription_monthly_fee': f'{SUBSCRIPTION_MONTHLY_FEE:g}',
        'refund_policy': 'automatic',
        'cancellation_window_hours': '48',
    }.items():
        setting = db.session.get(AdminSetting, key)
        if not setting:
            db.session.add(AdminSetting(key=key, value=value))
            changed = True
        elif key == 'refund_policy' and setting.value != value:
            # Refunds are automatic now; earlier databases stored a manual-review flag.
            setting.value = value
            changed = True
    if changed:
        db.session.commit()


def get_admin_setting(key, default):
    setting = db.session.get(AdminSetting, key)
    return setting.value if setting else str(default)


def platform_fee_rates():
    """Host commission and guest service fee rates, as percentages."""
    try:
        host_rate = float(get_admin_setting('host_commission_rate', HOST_COMMISSION_RATE))
        guest_rate = float(get_admin_setting('guest_service_fee_rate', GUEST_SERVICE_FEE_RATE))
    except (TypeError, ValueError):
        return HOST_COMMISSION_RATE, GUEST_SERVICE_FEE_RATE
    if not (0 <= host_rate < 100 and 0 <= guest_rate < 100):
        return HOST_COMMISSION_RATE, GUEST_SERVICE_FEE_RATE
    return host_rate, guest_rate


def platform_booking_fee():
    """Flat guest booking fee, in Kenyan shillings, charged on every booking."""
    try:
        fee = float(get_admin_setting('booking_fee', BOOKING_FEE))
    except (TypeError, ValueError):
        return BOOKING_FEE
    if not (0 <= fee <= 5000):
        return BOOKING_FEE
    return fee


def booking_fee_quote(subtotal, vendor_id=None):
    """Split a listing subtotal using the marketplace's current fee policy.

    A tour or safari operator with a live monthly subscription is charged the
    subscriber commission instead of the standard host commission.
    """
    host_rate, guest_rate = platform_fee_rates()
    if vendor_has_operator_subscription(vendor_id):
        host_rate = platform_subscriber_rate()
    return split_fee_quote(subtotal, host_rate, guest_rate, platform_booking_fee())


def platform_subscriber_rate():
    """Host commission, as a percentage, charged to subscribed operators."""
    try:
        rate = float(get_admin_setting(
            'subscriber_host_commission_rate', SUBSCRIBER_HOST_COMMISSION_RATE
        ))
    except (TypeError, ValueError):
        return SUBSCRIBER_HOST_COMMISSION_RATE
    if not (0 <= rate < 100):
        return SUBSCRIBER_HOST_COMMISSION_RATE
    return rate


def platform_subscription_fee():
    """Monthly partner subscription price, in Kenyan shillings."""
    try:
        fee = float(get_admin_setting('subscription_monthly_fee', SUBSCRIPTION_MONTHLY_FEE))
    except (TypeError, ValueError):
        return SUBSCRIPTION_MONTHLY_FEE
    if not (0 <= fee <= 50000):
        return SUBSCRIPTION_MONTHLY_FEE
    return fee


def vendor_has_operator_subscription(vendor_id):
    """True when the listing owner is a subscribed tour or safari operator."""
    if not vendor_id:
        return False
    vendor = db.session.get(VendorAccount, vendor_id)
    return bool(vendor and vendor.is_tour_operator() and vendor.subscription_is_active())


def ensure_catalog_columns():
    inspector = db.inspect(db.engine)
    table_columns = {table: {column['name'] for column in inspector.get_columns(table)}
                     for table in ('property', 'review', 'tour', 'destination') if inspector.has_table(table)}
    with db.engine.begin() as connection:
        if 'slug' not in table_columns.get('property', set()):
            connection.execute(text('ALTER TABLE property ADD COLUMN slug VARCHAR(160)'))
        if 'vendor_id' not in table_columns.get('property', set()):
            connection.execute(text('ALTER TABLE property ADD COLUMN vendor_id INTEGER'))
        for column, declaration in {
            'amenities': "TEXT NOT NULL DEFAULT ''",
            'latitude': 'FLOAT',
            'longitude': 'FLOAT',
            'destination': "VARCHAR(120) NOT NULL DEFAULT 'lamu'",
        }.items():
            if column not in table_columns.get('property', set()):
                connection.execute(text(f'ALTER TABLE property ADD COLUMN {column} {declaration}'))
        if 'vendor_id' not in table_columns.get('tour', set()):
            connection.execute(text('ALTER TABLE tour ADD COLUMN vendor_id INTEGER'))
        for column, declaration in {
            'site_type': "VARCHAR(20) NOT NULL DEFAULT 'area'",
            'latitude': 'FLOAT',
            'longitude': 'FLOAT',
        }.items():
            if column not in table_columns.get('destination', set()):
                connection.execute(text(f'ALTER TABLE destination ADD COLUMN {column} {declaration}'))
        tour_columns = table_columns.get('tour', set())
        for column, declaration in {
            'category': "VARCHAR(100) NOT NULL DEFAULT 'Experiences'",
            'itinerary': "TEXT NOT NULL DEFAULT ''",
            'inclusions': "TEXT NOT NULL DEFAULT ''",
            'exclusions': "TEXT NOT NULL DEFAULT ''",
            'pickup_point': "VARCHAR(200) NOT NULL DEFAULT 'Confirm with your operator'",
            'min_group_size': 'INTEGER NOT NULL DEFAULT 1',
            'max_group_size': 'INTEGER NOT NULL DEFAULT 12',
            'destination': "VARCHAR(120) NOT NULL DEFAULT 'lamu'",
            'tour_type': "VARCHAR(40) NOT NULL DEFAULT 'experience'",
            'duration_days': 'INTEGER NOT NULL DEFAULT 1',
            'languages': "TEXT NOT NULL DEFAULT ''",
            'group_type': "VARCHAR(20) NOT NULL DEFAULT 'private'",
        }.items():
            if column not in tour_columns:
                connection.execute(text(f'ALTER TABLE tour ADD COLUMN {column} {declaration}'))
        review_columns = table_columns.get('review', set())
        if 'target_type' not in review_columns:
            connection.execute(text('ALTER TABLE review ADD COLUMN target_type VARCHAR(20)'))
        if 'target_id' not in review_columns:
            connection.execute(text('ALTER TABLE review ADD COLUMN target_id VARCHAR(160)'))

    properties = Property.query.filter((Property.slug.is_(None)) | (Property.slug == '')).all()
    for property_listing in properties:
        property_listing.slug = unique_slug(property_listing.name, Property, property_listing.id)
    if properties:
        db.session.commit()

    # Move listings created under the older type names onto the accommodation vocabulary.
    legacy_types = tuple(LEGACY_PROPERTY_TYPES)
    legacy_listings = Property.query.filter(db.func.lower(Property.property_type).in_(legacy_types)).all()
    for property_listing in legacy_listings:
        property_listing.property_type = normalize_property_type(property_listing.property_type)
    if legacy_listings:
        db.session.commit()

    # Every property needs at least one room so it can be booked as a stay.
    properties_with_rooms = {room.property_id for room in PropertyRoom.query.all()}
    roomless_properties = [
        property_listing for property_listing in Property.query.all()
        if property_listing.id not in properties_with_rooms
    ]
    for property_listing in roomless_properties:
        db.session.add(PropertyRoom(
            property_id=property_listing.id,
            name='Entire place',
            description='',
            guests=property_listing.guests,
            base_rate=property_listing.price_per_night,
            total_units=1,
        ))
    if roomless_properties:
        db.session.commit()

    categories = {
        'dhow': 'Dhow & Island Hopping',
        'sandbank': 'Dhow & Island Hopping',
        'day-trips': 'Dhow & Island Hopping',
        'old-town': 'Heritage & Culture',
        'cultural': 'Heritage & Culture',
        'fort-jesus-walk': 'Heritage & Culture',
        'kaya-kinondo-walk': 'Heritage & Culture',
        'gede-ruins': 'Heritage & Culture',
        'nairobi-city-heritage': 'Heritage & Culture',
        'fishing': 'Water & Marine',
        'water-sports': 'Water & Marine',
        'mombasa-dhow-sunset': 'Water & Marine',
        'diani-snorkel': 'Water & Marine',
        'watamu-marine-park': 'Water & Marine',
        'naivasha-boat-safari': 'Water & Marine',
        'nairobi-national-park': 'Wildlife Safari',
        'giraffe-centre': 'Wildlife Safari',
        'mara-game-drive': 'Wildlife Safari',
        'mara-balloon': 'Wildlife Safari',
        'amboseli-safari': 'Wildlife Safari',
        'amboseli-sunset': 'Wildlife Safari',
        'hells-gate-cycle': 'Adventure & Nature',
    }
    # Categories that were applied automatically by older seeds. Only these are
    # migrated, so a category edited by a vendor is never overwritten.
    legacy_categories = {
        'Island experiences',
        'Experiences',
        'Lamu Old Town Walk',
        'Island Day Trips',
        'Dhow & Island Hopping',
    }
    for slug, category in categories.items():
        tour = db.session.get(Tour, slug)
        if tour and tour.category != category and tour.category in legacy_categories:
            tour.category = category
    if db.session.new or db.session.dirty:
        db.session.commit()


DEFAULT_TOURS = (
    # Lamu
    ('dhow', 'Dhow Trips', "Enjoy traditional dhow sailing around Lamu's coastline with snorkeling and island stops.", 'Half day', 8500, 'images/shela-lamu-kenya-09.jpg', 'lamu', 'Dhow & Island Hopping'),
    ('old-town', 'Old Town Walks', 'Explore the historic streets, architecture, and marketplaces of Lamu Old Town.', '3 hours', 3500, "images/Lamu_Fort_Museum's.jpg", 'lamu', 'Heritage & Culture'),
    ('sandbank', 'Sandbank Picnics', 'Relax on a private sandbank with picnic lunch, swimming, and beach activities.', 'Half day', 7000, 'images/shela-village.webp', 'lamu', 'Dhow & Island Hopping'),
    ('fishing', 'Fishing Trips', 'Go deep-sea fishing with local crew and enjoy fresh catch barbecue.', 'Full day', 12000, 'images/Lamu_coast.jpg', 'lamu', 'Water & Marine'),
    ('water-sports', 'Water Sports', 'Experience adrenaline with jet skiing, windsurfing, and paddleboarding in clear waters.', 'Half day', 9500, 'images/Spiritedpursuit_leelitumbe-106_lamu_kenya.webp', 'lamu', 'Water & Marine'),
    ('day-trips', 'Day Trips', 'Explore nearby islands and coastal attractions on a full-day guided excursion.', 'Full day', 9000, 'images/Spiritedpursuit_leelitumbe-49_lamu_kenya.webp', 'lamu', 'Dhow & Island Hopping'),
    ('cultural', 'Cultural Tours', 'Visit museums, traditional workshops, and attend local cultural performances.', '4 hours', 4000, 'images/Riadha_Mosque_in_Lamu.jpg', 'lamu', 'Heritage & Culture'),
    # Mombasa
    ('fort-jesus-walk', 'Fort Jesus & Old Town Walk', 'Walk the Portuguese fort and Mombasa Swahili old town with a local guide.', '3 hours', 3500, 'pictures/292080828.jpg', 'mombasa', 'Heritage & Culture'),
    ('mombasa-dhow-sunset', 'Sunset Dhow Cruise', 'Sail the Mombasa channel at golden hour aboard a traditional dhow.', '2 hours', 4500, 'pictures/295463285.jpg', 'mombasa', 'Water & Marine'),
    # Diani
    ('diani-snorkel', 'Diani Reef Snorkelling', 'Snorkel the reef off Diani and swim among tropical fish and coral gardens.', 'Half day', 6500, 'pictures/460469483.jpg', 'diani', 'Water & Marine'),
    ('kaya-kinondo-walk', 'Kaya Kinondo Forest Walk', 'A guided walk through a sacred coastal forest led by a local elder.', '3 hours', 3000, 'pictures/498623923.jpg', 'diani', 'Heritage & Culture'),
    # Watamu
    ('watamu-marine-park', 'Marine Park Snorkelling', 'Explore coral gardens in one of Kenya’s longest-protected marine areas.', 'Half day', 7000, 'pictures/498623932.jpg', 'watamu', 'Water & Marine'),
    ('gede-ruins', 'Gede Ruins & Mida Creek', 'Wander the medieval Swahili ruins, then glide through the Mida Creek mangroves.', '4 hours', 4000, 'pictures/498623941.jpg', 'watamu', 'Heritage & Culture'),
    # Nairobi
    ('nairobi-national-park', 'Nairobi National Park Safari', 'Game drive against the skyline in the only national park inside a capital city.', 'Half day', 11000, 'pictures/772777099.jpg', 'nairobi', 'Wildlife Safari'),
    ('nairobi-city-heritage', 'Nairobi City Heritage Walk', 'From the railway museum to the old town squares with a city guide.', '3 hours', 3000, 'pictures/772777142.jpg', 'nairobi', 'Heritage & Culture'),
    ('giraffe-centre', 'Giraffe Centre & Karen', 'Meet endangered Rothschild giraffes and visit the Karen heritage farmhouse.', '4 hours', 5500, 'pictures/772777203.jpg', 'nairobi', 'Wildlife Safari'),
    # Lake Naivasha
    ('naivasha-boat-safari', 'Lake Naivasha Boat Safari', 'Glide past hippos and fish eagles on a guided boat safari.', '2 hours', 5000, 'pictures/882985623.jpg', 'naivasha', 'Water & Marine'),
    ('hells-gate-cycle', "Hell's Gate Cycling Day", 'Cycle between cliffs, gorges and geothermal springs on a full-day ride.', 'Full day', 8000, 'pictures/873059687.jpg', 'naivasha', 'Adventure & Nature'),
    # Maasai Mara
    ('mara-game-drive', 'Mara Full-Day Game Drive', 'Track big cats across the Mara plains with a resident guide.', 'Full day', 18000, 'pictures/295463166.jpg', 'maasai-mara', 'Wildlife Safari'),
    ('mara-balloon', 'Mara Sunrise Balloon Safari', 'Drift over the plains at dawn and land for a bush breakfast.', 'Half day', 45000, 'pictures/295463173.jpg', 'maasai-mara', 'Wildlife Safari'),
    # Amboseli
    ('amboseli-safari', 'Amboseli Elephant Safari', 'Spend a day with the elephant herds that gather below Kilimanjaro.', 'Full day', 16500, 'pictures/337169041.jpg', 'amboseli', 'Wildlife Safari'),
    ('amboseli-sunset', 'Amboseli Sunset Game Drive', 'An evening drive to the viewpoints facing the mountain.', '3 hours', 9000, 'pictures/354456403.jpg', 'amboseli', 'Wildlife Safari'),
    # Tsavo
    ('tsavo-game-drive', 'Tsavo Red-Elephant Safari', 'Track red-dusted elephants and lion between the waterholes and lava flows of Tsavo East.', 'Full day', 15500, 'images/tsavo-red-elephants.jpg', 'tsavo', 'Wildlife Safari'),
    # Mount Kenya
    ('mount-kenya-forest-trek', 'Mount Kenya Forest Trek', 'Walk the montane forest belt below the peaks with a guide, looking for colobus monkeys and giant heather.', 'Full day', 9500, 'images/mount-kenya-highlands.jpg', 'mount-kenya', 'Adventure & Nature'),
)

DEFAULT_TOUR_DETAILS = {
    'dhow': {
        'itinerary': '08:00–08:30 | Meet the crew at Lamu waterfront; Highlights: safety briefing and dhow boarding\n08:30–10:00 | Sail the coastline and island channels; Highlights: Lamu seascapes and quiet coves\n10:00–11:30 | Stop for a swim or snorkel where conditions allow; Highlights: clear-water time and a relaxed dhow sail\n11:30–12:00 | Sail back to Lamu waterfront; Highlights: return views of the old town',
        'inclusions': 'Dhow transport and local sailing crew\nLocal guide on board\nCoastal sailing experience',
        'exclusions': 'Meals and snacks\nDrinking water (bring your own unless confirmed by the operator)\nSnorkeling equipment and personal expenses',
        'pickup_point': 'Lamu Town waterfront',
    },
    'old-town': {
        'itinerary': '09:00–09:15 | Meet your guide in Lamu Old Town; Highlights: route and local customs briefing\n09:15–10:30 | Walk the historic lanes and waterfront; Highlights: Swahili architecture and carved doors\n10:30–11:15 | Visit the fort and nearby heritage landmarks; Highlights: Lamu history and island life\n11:15–12:00 | Browse the market streets and return to the meeting point; Highlights: local crafts and daily life',
        'inclusions': 'Local walking guide\nGuided Old Town route',
        'exclusions': 'Private transport (the tour is on foot)\nDrinking water (bring your own unless confirmed by the operator)\nEntry fees and personal purchases',
        'pickup_point': 'Lamu Old Town waterfront',
    },
    'sandbank': {
        'itinerary': '09:00–09:30 | Meet at Lamu waterfront and board the dhow; Highlights: crew briefing and island-channel views\n09:30–10:15 | Sail to a nearby sandbank; Highlights: open-water scenery\n10:15–12:30 | Enjoy a sandbank picnic and free time; Highlights: swimming, beach time and lunch\n12:30–13:00 | Sail back to Lamu; Highlights: relaxed return along the coast',
        'inclusions': 'Dhow transport to and from the sandbank\nLocal dhow crew\nPicnic lunch',
        'exclusions': 'Private road transport to the waterfront\nDrinking water (bring your own unless confirmed by the operator)\nPersonal expenses and optional activities',
        'pickup_point': 'Lamu Town waterfront',
    },
    'fishing': {
        'itinerary': '06:00–06:30 | Meet the fishing crew and prepare the boat; Highlights: tackle and safety briefing\n06:30–10:30 | Sail to local fishing grounds; Highlights: coastal fishing with the crew\n10:30–11:30 | Head back to shore; Highlights: return sail and catch discussion',
        'inclusions': 'Fishing boat and local crew\nFishing guidance',
        'exclusions': 'Private transport to the waterfront\nDrinking water and meals (bring your own unless confirmed by the operator)\nPersonal fishing equipment and any catch preparation',
        'pickup_point': 'Lamu Town waterfront',
    },
    'water-sports': {
        'itinerary': '09:00–09:20 | Check in with the activity team; Highlights: safety and equipment briefing\n09:20–12:00 | Take part in the water activities selected at booking; Highlights: time on the water with the activity crew\n12:00–12:15 | Return equipment and wrap up; Highlights: final safety check and return to the launch point',
        'inclusions': 'Activity briefing\nEquipment for activities selected and confirmed at booking',
        'exclusions': 'Private transport to the launch point\nDrinking water (bring your own unless confirmed by the operator)\nOptional activities not selected at booking',
        'pickup_point': 'Confirm with the activity team',
    },
    'day-trips': {
        'itinerary': '08:30–09:00 | Meet your guide at Lamu waterfront; Highlights: destination and travel briefing\n09:00–11:00 | Travel by boat to the selected nearby island; Highlights: channel and coastline views\n11:00–14:00 | Explore the destination with your guide; Highlights: local landmarks and time to relax\n14:00–15:00 | Return to Lamu; Highlights: afternoon sail back to the waterfront',
        'inclusions': 'Boat transfers to and from the selected destination\nLocal guide',
        'exclusions': 'Private road transport to the waterfront\nMeals and drinking water (bring your own unless confirmed by the operator)\nDestination entry fees and personal expenses',
        'pickup_point': 'Lamu Town waterfront',
    },
    'cultural': {
        'itinerary': '09:00–09:15 | Meet your cultural guide; Highlights: route and respectful-visit briefing\n09:15–10:30 | Visit local heritage landmarks; Highlights: Swahili history and island traditions\n10:30–12:00 | Explore workshops and cultural spaces; Highlights: local craft and community stories\n12:00–13:00 | Walk back to the meeting point; Highlights: questions and recommendations from your guide',
        'inclusions': 'Local cultural guide\nGuided walking route',
        'exclusions': 'Private transport (the tour is on foot)\nDrinking water (bring your own unless confirmed by the operator)\nEntry fees, meals and personal purchases',
        'pickup_point': 'Lamu Old Town waterfront',
    },
    'fort-jesus-walk': {
        'itinerary': '09:00–09:15 | Meet your guide at Fort Jesus; Highlights: route and safety briefing\n09:15–10:45 | Explore the fort and its museum; Highlights: Portuguese and Swahili history\n10:45–11:45 | Walk the old town lanes and market streets; Highlights: carved doors and spice stalls\n11:45–12:00 | Return to the meeting point; Highlights: local recommendations',
        'inclusions': 'Local walking guide\nFort Jesus entry arrangement\nGuided old town route',
        'exclusions': 'Private transport\nDrinks and meals\nPersonal purchases',
        'pickup_point': 'Fort Jesus main gate',
    },
    'mombasa-dhow-sunset': {
        'itinerary': '16:30–16:45 | Meet the crew at the old port; Highlights: safety briefing and boarding\n16:45–18:15 | Sail the channel at golden hour; Highlights: harbour views and city skyline\n18:15–18:30 | Return to the jetty; Highlights: sunset photos',
        'inclusions': 'Dhow cruise with local crew\nSafety equipment',
        'exclusions': 'Hotel transfers\nDrinks and snacks\nGratuities',
        'pickup_point': 'Mombasa old port',
    },
    'diani-snorkel': {
        'itinerary': '08:30–09:00 | Meet at the dive centre; Highlights: equipment fitting and briefing\n09:00–10:00 | Boat ride to the reef; Highlights: coastline views\n10:00–12:00 | Snorkel the coral gardens; Highlights: reef fish and coral\n12:00–12:30 | Return to shore; Highlights: rinse and debrief',
        'inclusions': 'Boat transfer to the reef\nSnorkelling equipment\nMarine guide',
        'exclusions': 'Marine park fees\nMeals and drinks\nUnderwater camera hire',
        'pickup_point': 'Diani dive centre',
    },
    'kaya-kinondo-walk': {
        'itinerary': '09:00–09:15 | Meet your guide at the forest gate; Highlights: cultural protocol briefing\n09:15–10:30 | Walk the sacred forest trails; Highlights: old-growth trees and local stories\n10:30–11:00 | Talk with the community guide; Highlights: Digo traditions\n11:00–11:15 | Return to the gate',
        'inclusions': 'Local community guide\nForest entry arrangement',
        'exclusions': 'Transport to the forest\nDrinks\nPersonal purchases',
        'pickup_point': 'Kaya Kinondo forest gate',
    },
    'watamu-marine-park': {
        'itinerary': '08:30–09:00 | Meet at the beach launch point; Highlights: safety briefing\n09:00–10:00 | Boat out to the coral gardens; Highlights: reef views\n10:00–11:30 | Snorkel the marine park; Highlights: turtles and reef fish\n11:30–12:00 | Return to shore',
        'inclusions': 'Boat transfer\nSnorkelling equipment\nMarine guide',
        'exclusions': 'Marine park entry fees\nMeals and drinks\nEquipment hire beyond snorkelling',
        'pickup_point': 'Watamu beach launch point',
    },
    'gede-ruins': {
        'itinerary': '09:00–09:20 | Meet your guide at the Gede gate; Highlights: site briefing\n09:20–10:40 | Explore the Swahili ruins; Highlights: mosques, tombs and wells\n10:40–11:30 | Drive to Mida Creek; Highlights: mangrove boardwalk\n11:30–12:30 | Creek walk and birdwatching; Highlights: waders and kingfishers\n12:30–13:00 | Return to Gede',
        'inclusions': 'Local guide\nRuins entry arrangement\nMida Creek boardwalk',
        'exclusions': 'Drinks and meals\nPersonal purchases\nGratuities',
        'pickup_point': 'Gede ruins entrance',
    },
    'nairobi-national-park': {
        'itinerary': '06:00–06:15 | Hotel pickup within the city; Highlights: briefing\n06:15–09:30 | Game drive in the park; Highlights: rhino, lion and skyline views\n09:30–10:30 | Picnic stop at a viewpoint; Highlights: photography\n10:30–11:30 | Return drive to your hotel',
        'inclusions': 'Game drive vehicle and guide\nPark entry arrangement\nBottled water',
        'exclusions': 'Breakfast\nPersonal insurance\nGratuities',
        'pickup_point': 'Your Nairobi hotel',
    },
    'nairobi-city-heritage': {
        'itinerary': '09:00–09:15 | Meet your guide at the railway museum; Highlights: city history briefing\n09:15–10:30 | Railway museum and city squares; Highlights: colonial-era landmarks\n10:30–11:30 | Old town markets and coffee stops; Highlights: everyday city life\n11:30–12:00 | Return to the meeting point',
        'inclusions': 'City guide\nMuseum entry arrangement',
        'exclusions': 'Transport\nFood and drinks\nPersonal purchases',
        'pickup_point': 'Nairobi Railway Museum',
    },
    'giraffe-centre': {
        'itinerary': '09:00–09:20 | Meet your guide in Karen; Highlights: route briefing\n09:20–10:30 | Visit the giraffe centre; Highlights: feeding platform and conservation talk\n10:30–11:40 | Karen heritage farmhouse visit; Highlights: house museum and gardens\n11:40–12:00 | Return to the meeting point',
        'inclusions': 'Local guide\nGiraffe centre entry arrangement\nFarmhouse museum entry arrangement',
        'exclusions': 'Transport\nFood and drinks\nPersonal purchases',
        'pickup_point': 'Karen, Nairobi',
    },
    'naivasha-boat-safari': {
        'itinerary': '08:30–08:45 | Meet at the jetty; Highlights: safety briefing\n08:45–10:15 | Boat safari on the lake; Highlights: hippos, fish eagles and acacia shores\n10:15–10:30 | Return to the jetty',
        'inclusions': 'Boat and skipper\nLife jackets\nGuide',
        'exclusions': 'Park or conservancy fees\nDrinks and snacks\nTransport to the jetty',
        'pickup_point': 'Naivasha jetty',
    },
    'hells-gate-cycle': {
        'itinerary': '08:30–09:00 | Meet at the park gate; Highlights: bike fitting and briefing\n09:00–11:30 | Cycle through the park; Highlights: cliffs, gorges and wildlife\n11:30–12:30 | Thermal spa stop; Highlights: geothermal springs\n12:30–13:00 | Return bikes at the gate',
        'inclusions': 'Mountain bike hire\nLocal guide\nHelmet',
        'exclusions': 'Park entry fees\nMeals and drinks\nSpa entry',
        'pickup_point': "Hell's Gate park gate",
    },
    'mara-game-drive': {
        'itinerary': '06:00–06:15 | Meet your guide at camp; Highlights: day plan briefing\n06:15–09:00 | Morning game drive; Highlights: big cats and plains game\n09:00–10:00 | Bush breakfast stop; Highlights: open savannah views\n10:00–13:00 | Continue the drive; Highlights: river crossings and birdlife\n13:00–17:00 | Afternoon drive and return; Highlights: golden-hour photography',
        'inclusions': 'Game drive vehicle and guide\nBush breakfast\nBottled water',
        'exclusions': 'Park conservancy fees\nDrinks\nGratuities',
        'pickup_point': 'Your Mara camp',
    },
    'mara-balloon': {
        'itinerary': '05:15–05:45 | Transfer to the launch site; Highlights: safety briefing\n05:45–07:00 | Sunrise balloon flight; Highlights: plains and wildlife from above\n07:00–08:30 | Bush breakfast on landing; Highlights: champagne breakfast\n08:30–09:00 | Game drive back to camp',
        'inclusions': 'Balloon flight with pilot\nBush breakfast\nTransfer to the launch site',
        'exclusions': 'Park conservancy fees\nDrinks beyond breakfast\nGratuities',
        'pickup_point': 'Your Mara camp',
    },
    'amboseli-safari': {
        'itinerary': '06:00–06:15 | Meet at your lodge; Highlights: briefing\n06:15–09:30 | Morning game drive; Highlights: elephant herds and mountain views\n09:30–13:00 | Continue with a picnic stop; Highlights: swamp and plains wildlife\n13:00–16:00 | Afternoon drive back; Highlights: photography stops',
        'inclusions': 'Game drive vehicle and guide\nPicnic lunch\nBottled water',
        'exclusions': 'Park entry fees\nDrinks\nGratuities',
        'pickup_point': 'Your Amboseli lodge',
    },
    'amboseli-sunset': {
        'itinerary': '15:30–15:45 | Meet your guide; Highlights: sunset viewpoint briefing\n15:45–18:00 | Evening game drive; Highlights: elephants and mountain backdrop\n18:00–18:30 | Sunset viewpoint; Highlights: golden-hour photography\n18:30–19:00 | Return to your lodge',
        'inclusions': 'Game drive vehicle and guide\nBottled water',
        'exclusions': 'Park entry fees\nDrinks and dinner\nGratuities',
        'pickup_point': 'Your Amboseli lodge',
    },
    'tsavo-game-drive': {
        'itinerary': '06:00–06:15 | Meet your guide at camp; Highlights: park and waterhole briefing\n06:15–09:30 | Morning game drive in Tsavo East; Highlights: red elephants and lion\n09:30–12:30 | Continue through the waterhole circuit; Highlights: baobabs and open plains\n12:30–13:30 | Picnic lunch under the trees; Highlights: shade and birdlife\n13:30–17:00 | Afternoon drive back towards camp; Highlights: golden-hour photography',
        'inclusions': 'Game drive vehicle and resident guide\nPicnic lunch\nBottled water',
        'exclusions': 'Park entry fees\nDrinks\nGratuities',
        'pickup_point': 'Your Tsavo camp',
    },
    'mount-kenya-forest-trek': {
        'itinerary': '07:30–07:45 | Meet your guide at the park gate; Highlights: mountain weather and route briefing\n07:45–10:30 | Walk the montane forest trails; Highlights: giant heather, bamboo and colobus monkeys\n10:30–12:30 | Climb to a highland viewpoint; Highlights: views towards the peaks\n12:30–13:30 | Picnic lunch on the ridge; Highlights: open highland scenery\n13:30–15:30 | Descend through farmland back to the gate',
        'inclusions': 'Local mountain guide\nForest entry arrangement\nPicnic lunch',
        'exclusions': 'Transport to the park gate\nDrinks\nPersonal hiking gear and gratuities',
        'pickup_point': 'Mount Kenya forest gate',
    },
}

# Overnight packages seeded so the catalogue covers multi-day safaris, not
# only day experiences. Each row ends with the number of days.
DEFAULT_PACKAGE_TOURS = (
    (
        'mara-3-day-safari',
        '3-Day Maasai Mara Safari',
        'Three days on the Mara plains with morning and evening game drives, full board in a tented camp, and a guide who knows the river crossings.',
        '3 days · 2 nights',
        78500,
        'pictures/295463166.jpg',
        'maasai-mara',
        'Wildlife Safari',
        3,
    ),
    (
        'amboseli-tsavo-4-day',
        '4-Day Amboseli & Tsavo Safari',
        'Elephants below Kilimanjaro, then the red earth of Tsavo West. Four days of game drives, lodges with pools, and slow evenings under the mountain.',
        '4 days · 3 nights',
        96500,
        'pictures/337169041.jpg',
        'amboseli',
        'Wildlife Safari',
        4,
    ),
    (
        'coast-to-mara-6-day',
        '6-Day Coast to Mara Safari',
        'The full Kenya trip in one itinerary: two days on the Swahili coast, a night in Nairobi, then three nights on the Mara plains.',
        '6 days · 5 nights',
        148000,
        'pictures/295463173.jpg',
        'maasai-mara',
        'Wildlife Safari',
        6,
    ),
)

DEFAULT_PACKAGE_DETAILS = {
    'mara-3-day-safari': {
        'itinerary': 'Day 1 | Drive from Nairobi to the Mara with a Rift Valley stop; Highlights: escarpment views and an afternoon game drive\nDay 2 | Full day in the reserve with a picnic lunch; Highlights: big cats, river crossings and the Mara triangle\nDay 3 | Sunrise game drive and return to Nairobi; Highlights: golden-hour photography and a final sighting',
        'inclusions': 'Two nights full board in a tented camp\nPark fees and conservancy levies\nGame drives in a 4x4 with a resident guide\nTransfers from Nairobi',
        'exclusions': 'Drinks and personal items\nBalloon safari (booked separately)\nTravel insurance and gratuities',
        'pickup_point': 'Your Nairobi hotel or Wilson Airport',
    },
    'amboseli-tsavo-4-day': {
        'itinerary': 'Day 1 | Nairobi to Amboseli with an afternoon drive; Highlights: elephant herds below Kilimanjaro\nDay 2 | Morning and evening game drives in Amboseli; Highlights: observation hill and the swamps\nDay 3 | Transfer to Tsavo West and an afternoon drive; Highlights: Mzima Springs and the lava flows\nDay 4 | Sunrise drive and return to Nairobi; Highlights: red-earth scenery and a final game drive',
        'inclusions': 'Three nights full board in lodges\nPark fees for both parks\nGame drives in a 4x4 with a guide\nTransfers from Nairobi',
        'exclusions': 'Drinks and personal items\nOptional night drive\nTravel insurance and gratuities',
        'pickup_point': 'Your Nairobi hotel',
    },
    'coast-to-mara-6-day': {
        'itinerary': 'Day 1 | Arrive on the coast and settle in; Highlights: beach time and a sunset dhow sail\nDay 2 | A coast day at your own pace; Highlights: reef snorkelling or the old town\nDay 3 | Fly to Nairobi and overnight; Highlights: a city dinner and an early night\nDay 4 | Drive to the Mara with an afternoon drive; Highlights: the escarpment and first sightings\nDay 5 | Full day in the reserve; Highlights: big cats, river crossings and a picnic lunch\nDay 6 | Sunrise game drive and return to Nairobi; Highlights: final photography and transfers',
        'inclusions': 'Five nights full board except coast breakfasts\nDomestic flight to Nairobi\nPark fees and game drives\nAirport and hotel transfers',
        'exclusions': 'International flights\nDrinks and personal items\nBalloon safari and spa treatments\nTravel insurance and gratuities',
        'pickup_point': 'Your coast hotel or Mombasa airport',
    },
}

LEGACY_DEFAULT_ITINERARIES = {
    'dhow': 'Meet your crew at the Lamu waterfront\nSail along the coastline and island channels\nReturn to the waterfront',
    'old-town': 'Meet your local guide in Lamu Old Town\nExplore historic lanes and landmarks\nReturn to the meeting point',
    'sandbank': 'Depart by dhow from Lamu\nEnjoy time on a nearby sandbank\nSail back to Lamu',
    'fishing': 'Meet the fishing crew\nSail to local fishing grounds\nReturn to shore with the crew',
    'water-sports': 'Meet the activity team\nChoose from available water activities\nReturn to the launch point',
    'day-trips': 'Meet your local guide\nExplore a nearby island or coastal destination\nReturn to Lamu',
    'cultural': 'Meet your local guide\nVisit cultural landmarks and local workshops\nReturn to the meeting point',
    'fort-jesus-walk': 'Meet your guide at Fort Jesus\nWalk the old town and market streets\nReturn to the meeting point',
    'mombasa-dhow-sunset': 'Meet the crew at the old port\nSail the channel at sunset\nReturn to the jetty',
    'diani-snorkel': 'Meet at the dive centre\nSnorkel the reef by boat\nReturn to shore',
    'kaya-kinondo-walk': 'Meet your community guide\nWalk the sacred forest trails\nReturn to the gate',
    'watamu-marine-park': 'Meet at the beach launch point\nSnorkel the marine park\nReturn to shore',
    'gede-ruins': 'Meet your guide at the ruins\nExplore Gede and Mida Creek\nReturn to the meeting point',
    'nairobi-national-park': 'Meet your guide\nGame drive in the national park\nReturn to your hotel',
    'nairobi-city-heritage': 'Meet your city guide\nWalk the heritage route\nReturn to the meeting point',
    'giraffe-centre': 'Meet your guide in Karen\nVisit the giraffe centre and farmhouse\nReturn to the meeting point',
    'naivasha-boat-safari': 'Meet at the jetty\nBoat safari on the lake\nReturn to the jetty',
    'hells-gate-cycle': 'Meet at the park gate\nCycle the park trails\nReturn bikes at the gate',
    'mara-game-drive': 'Meet your guide at camp\nGame drive across the plains\nReturn to camp',
    'mara-balloon': 'Transfer to the launch site\nSunrise balloon flight and breakfast\nReturn to camp',
    'amboseli-safari': 'Meet your guide at the lodge\nGame drive in the park\nReturn to your lodge',
    'amboseli-sunset': 'Meet your guide\nEvening game drive to the viewpoints\nReturn to your lodge',
    'tsavo-game-drive': 'Meet your guide at camp\nGame drive through the waterholes of Tsavo East\nReturn to camp',
    'mount-kenya-forest-trek': 'Meet your guide at the forest gate\nTrek the montane forest belt\nReturn to the gate',
}

DEFAULT_PROPERTIES = (
    # Lamu
    ('shela-guest-house', 'Shela Village Guest House', 'rental', 'Shela, Lamu', 4500, 2, 'images/shela-village.webp', 'Comfortable guest house in Shela village.', 'lamu'),
    ('old-town-hotel', 'Old Town Swahili Hotel', 'hotel', 'Lamu Old Town', 6500, 3, "images/Lamu_Fort_Museum's.jpg", 'A Swahili hotel close to the history and culture of Lamu Old Town.', 'lamu'),
    ('manda-beach-home', 'Manda Island Beach Home', 'rental', 'Manda Island, Lamu', 10000, 5, 'images/Lamu_coast.jpg', 'An island home with spacious ocean views.', 'lamu'),
    ('shela-palm-villa', 'Shela Palm Villa', 'rental', 'Shela, Lamu', 12500, 4, 'pictures/187747945.jpg', 'A private villa close to Shela beach.', 'lamu'),
    ('mjini-budget-hotel', 'Mjini Budget Hotel', 'hotel', 'Lamu Mjini', 5500, 2, 'pictures/292079957.jpg', 'An affordable hotel in the heart of Lamu town.', 'lamu'),
    ('kipungani-guest-house', 'Kipungani Coast Guest House', 'rental', 'Kipungani, Lamu', 5000, 3, 'pictures/611137747.jpg', 'A quiet guest house along the Kipungani coast.', 'lamu'),
    ('manda-ocean-villa', 'Manda Ocean Villa', 'rental', 'Manda Island, Lamu', 16000, 6, 'pictures/552000169.jpg', 'A private ocean villa on Manda Island.', 'lamu'),
    # Mombasa
    ('nyali-beach-hotel', 'Nyali Beach Hotel', 'hotel', 'Nyali, Mombasa', 9500, 2, 'pictures/292080012.jpg', 'Ocean-view rooms minutes from the reef and the city centre.', 'mombasa'),
    ('mombasa-old-town-house', 'Old Town Swahili House', 'rental', 'Mombasa Old Town', 5200, 2, 'pictures/292079967.jpg', 'A restored Swahili house a short walk from Fort Jesus.', 'mombasa'),
    # Diani
    ('diani-sands-villa', 'Diani Sands Villa', 'rental', 'Diani Beach', 15000, 6, 'pictures/497804782.jpg', 'A private villa a few steps from the white sand.', 'diani'),
    ('diani-garden-home', 'Diani Garden Home', 'rental', 'Diani Beach', 7800, 4, 'pictures/464889964.jpg', 'A garden home with a shaded veranda near the beach path.', 'diani'),
    # Watamu
    ('watamu-bay-hotel', 'Watamu Bay Hotel', 'hotel', 'Watamu', 8800, 2, 'pictures/498623900.jpg', 'A bay-front hotel with easy access to the marine park.', 'watamu'),
    ('mida-creek-home', 'Mida Creek Home', 'rental', 'Mida Creek, Watamu', 9900, 5, 'pictures/498623923.jpg', 'A quiet home overlooking the mangroves of Mida Creek.', 'watamu'),
    # Nairobi
    ('westlands-city-hotel', 'Westlands City Hotel', 'hotel', 'Westlands, Nairobi', 11500, 2, 'pictures/772777040.jpg', 'A central hotel close to restaurants and business districts.', 'nairobi'),
    ('karen-garden-villa', 'Karen Garden Villa', 'rental', 'Karen, Nairobi', 18500, 6, 'pictures/772777142.jpg', 'A leafy villa with a private garden on the city edge.', 'nairobi'),
    # Lake Naivasha
    ('naivasha-lake-lodge', 'Lake Naivasha Lodge', 'rental', 'Lake Naivasha', 7400, 3, 'pictures/882985623.jpg', 'A lakeside lodge with acacia views and abundant birdlife.', 'naivasha'),
    # Maasai Mara
    ('mara-savannah-camp', 'Mara Savannah Camp', 'rental', 'Maasai Mara', 22000, 2, 'pictures/295463166.jpg', 'A tented camp on the edge of the open plains.', 'maasai-mara'),
    ('mara-river-lodge', 'Mara River Lodge', 'hotel', 'Maasai Mara', 26500, 4, 'pictures/295463173.jpg', 'A river-front lodge with guiding included.', 'maasai-mara'),
    # Amboseli
    ('amboseli-view-lodge', 'Amboseli View Lodge', 'hotel', 'Amboseli', 17500, 3, 'pictures/337169041.jpg', 'Rooms facing the mountain and the elephant corridors.', 'amboseli'),
    # Tsavo
    ('tsavo-red-earth-camp', 'Tsavo Red Earth Camp', 'lodge', 'Tsavo East', 16500, 3, 'images/tsavo-red-elephants.jpg', 'A tented camp on the edge of Tsavo East, with waterhole views.', 'tsavo'),
    ('voi-station-rest', 'Voi Station Rest', 'rental', 'Voi, Tsavo', 6300, 4, 'images/tsavo-red-elephants.jpg', 'A simple, well-placed base for early starts into Tsavo.', 'tsavo'),
    # Mount Kenya
    ('nanyuki-highlands-lodge', 'Nanyuki Highlands Lodge', 'lodge', 'Nanyuki, Mount Kenya', 14500, 4, 'images/mount-kenya-highlands.jpg', 'A highland lodge with mountain views and a fireplace for cold evenings.', 'mount-kenya'),
    ('naro-moru-forest-cabin', 'Naro Moru Forest Cabin', 'rental', 'Naro Moru, Mount Kenya', 6800, 2, 'images/mount-kenya-highlands.jpg', 'A timber cabin on the forest edge, a short drive from the park gate.', 'mount-kenya'),
)

# Accommodation types offered when listing or filtering a property.
PROPERTY_TYPES = ('hotel', 'lodge', 'resort', 'apartment', 'rental', 'hostel')
# Listings created before this vocabulary was introduced are mapped onto it.
LEGACY_PROPERTY_TYPES = {'home': 'rental', 'guest house': 'rental', 'villa': 'rental'}


def normalize_property_type(value):
    property_type = str(value or '').strip().lower()
    return LEGACY_PROPERTY_TYPES.get(property_type, property_type)


DEFAULT_DESTINATIONS = (
    ('lamu', 'Lamu', 'Car-free Swahili streets, dhow sails and quiet island beaches.', 'images/shela-lamu-kenya-09.jpg', 'Lamu'),
    ('mombasa', 'Mombasa', 'Fort Jesus, spice markets and a lively Indian Ocean port city.', 'pictures/292080012.jpg', 'Mombasa'),
    ('diani', 'Diani Beach', 'Powder-white sand, reef snorkelling and relaxed beach accommodation.', 'pictures/497804782.jpg', 'Diani'),
    ('watamu', 'Watamu', 'Marine park reefs, turtle beaches and the Gede ruins.', 'pictures/498623900.jpg', 'Watamu'),
    ('nairobi', 'Nairobi', 'A capital where wildlife parks meet museums and coffee culture.', 'pictures/772777040.jpg', 'Nairobi'),
    ('naivasha', 'Lake Naivasha', 'Boat safaris, hippo shores and the cliffs of Hell’s Gate.', 'pictures/882985623.jpg', 'Naivasha'),
    ('mount-kenya', 'Mount Kenya', 'Snow-capped peaks, montane forest and highland farms around Nanyuki and Naro Moru.', 'images/mount-kenya-highlands.jpg', 'Nanyuki'),
    ('maasai-mara', 'Maasai Mara', 'Big-cat plains and the great migration on open savannah.', 'pictures/295463166.jpg', 'Mara'),
    ('amboseli', 'Amboseli', 'Elephant herds beneath the snows of Kilimanjaro.', 'pictures/337169041.jpg', 'Amboseli'),
    ('tsavo', 'Tsavo', 'Red elephants, lava flows and wide waterhole country between Nairobi and the coast.', 'images/tsavo-red-elephants.jpg', 'Tsavo'),
)

# Paid placements the marketplace runs on its own inventory. They demonstrate
# the sponsored slot on a fresh install and can be paused from the dashboard;
# seeding never rewrites an existing campaign, so an admin edit always wins.
DEFAULT_PROMOTIONS = (
    ('tour', 'mombasa-dhow-sunset', 'spotlight', 'Sunset dhow sailing', 45),
    ('property', 'shela-palm-villa', 'featured', 'Shela beach villa', 45),
)
# Hard ceiling on simultaneous live campaigns so sponsored slots stay scarce.
PROMOTION_MAX_ACTIVE = 6

# Placeholder pickup points written by older seeds; matched so they can be
# upgraded to the operator-specific value in DEFAULT_TOUR_DETAILS.
LEGACY_PICKUP_POINTS = ('Lamu Town waterfront', 'Confirm with your operator')
# Owner details written by older seeds; upgraded to the current brand on boot.
LEGACY_OWNER_NAMES = ('Lamu Tours', 'Kenya Tours')
LEGACY_OWNER_EMAILS = ('admin@lamutours.com',)
DEFAULT_OWNER_NAME = BRAND_NAME
DEFAULT_OWNER_EMAIL = f'admin@{BRAND_DOMAIN}'

# Neighbourhood-level rows from the earlier Lamu-only seed. They are replaced by
# the country-wide destinations above; Destination.slug is not referenced by any
# foreign key, so removing the rows cannot orphan a listing.
RETIRED_DESTINATION_SLUGS = (
    'shela',
    'lamu-old-town',
    'manda-island',
    'kipungani',
    'lamu-mjini',
    'lamu-coast',
)


def unique_slug(value, model, current_id=None):
    base = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-') or 'listing'
    slug = base
    suffix = 2
    while True:
        query = model.query.filter_by(slug=slug)
        if current_id is not None:
            query = query.filter(model.id != current_id) if hasattr(model, 'id') else query.filter(model.slug != current_id)
        if not query.first():
            return slug
        slug = f'{base}-{suffix}'
        suffix += 1


def seed_catalogue():
    # Track work explicitly: the loops below issue queries, which autoflush
    # pending inserts. A `db.session.new` check after that point would look
    # empty and silently skip the commit, rolling the whole seed back.
    changed = False
    for slug, name, description, duration, price, image_url, destination, category in DEFAULT_TOURS:
        tour = db.session.get(Tour, slug)
        if not tour:
            tour = Tour(
                slug=slug,
                name=name,
                description=description,
                duration=duration,
                price=price,
                image_url=image_url,
                destination=destination,
                category=category,
            )
            db.session.add(tour)
            changed = True
        elif not tour.destination:
            tour.destination = destination
            changed = True
        defaults = DEFAULT_TOUR_DETAILS[slug]
        if not tour.itinerary or tour.itinerary == LEGACY_DEFAULT_ITINERARIES[slug]:
            tour.itinerary = defaults['itinerary']
            changed = True
        if not tour.inclusions:
            tour.inclusions = defaults['inclusions']
            changed = True
        if not tour.exclusions:
            tour.exclusions = defaults['exclusions']
            changed = True
        if tour.pickup_point in LEGACY_PICKUP_POINTS:
            tour.pickup_point = defaults['pickup_point']
            changed = True

    for slug, name, property_type, location, price, guests, image_url, description, destination in DEFAULT_PROPERTIES:
        listing = Property.query.filter_by(slug=slug).first()
        if not listing:
            db.session.add(Property(
                slug=slug,
                owner_name=DEFAULT_OWNER_NAME,
                owner_email=DEFAULT_OWNER_EMAIL,
                name=name,
                property_type=property_type,
                location=location,
                destination=destination,
                price_per_night=price,
                guests=guests,
                image_url=image_url,
                description=description,
            ))
            changed = True
        else:
            if not listing.destination:
                listing.destination = destination
                changed = True
            if listing.owner_name in LEGACY_OWNER_NAMES and listing.owner_email in LEGACY_OWNER_EMAILS:
                # Seeded rows still carry pre-rebrand owner details; a vendor-owned
                # listing never uses the placeholder email, so it is left alone.
                listing.owner_name = DEFAULT_OWNER_NAME
                listing.owner_email = DEFAULT_OWNER_EMAIL
                changed = True

    for slug, name, description, duration, price, image_url, destination, category, days in DEFAULT_PACKAGE_TOURS:
        tour = db.session.get(Tour, slug)
        if not tour:
            tour = Tour(
                slug=slug,
                name=name,
                description=description,
                duration=duration,
                price=price,
                image_url=image_url,
                destination=destination,
                category=category,
                tour_type='multi-day-safari',
                duration_days=days,
                group_type='shared',
            )
            db.session.add(tour)
            changed = True
        else:
            if tour.tour_type != 'multi-day-safari':
                tour.tour_type = 'multi-day-safari'
                changed = True
            if (tour.duration_days or 1) < 2:
                tour.duration_days = days
                changed = True
        package = DEFAULT_PACKAGE_DETAILS[slug]
        if not tour.itinerary:
            tour.itinerary = package['itinerary']
            changed = True
        if not tour.inclusions:
            tour.inclusions = package['inclusions']
            changed = True
        if not tour.exclusions:
            tour.exclusions = package['exclusions']
            changed = True
        if not tour.pickup_point or tour.pickup_point in LEGACY_PICKUP_POINTS:
            tour.pickup_point = package['pickup_point']
            changed = True
        # Give the packages published departures so they can be booked online.
        if not TourSchedule.query.filter_by(tour_slug=slug).first():
            first_start = datetime.now(KENYA_TIMEZONE).replace(
                tzinfo=None, hour=7, minute=0, second=0, microsecond=0
            ) + timedelta(days=14)
            for index in range(12):
                db.session.add(TourSchedule(
                    tour_slug=slug,
                    starts_at=first_start + timedelta(days=14 * index),
                    capacity=8,
                    booked_count=0,
                    is_active=True,
                ))
            changed = True

    for slug, name, description, image_url, search_location in DEFAULT_DESTINATIONS:
        if not db.session.get(Destination, slug):
            db.session.add(Destination(
                slug=slug,
                name=name,
                description=description,
                image_url=image_url,
                search_location=search_location,
            ))
            changed = True
    for retired_slug in RETIRED_DESTINATION_SLUGS:
        retired = db.session.get(Destination, retired_slug)
        if retired:
            db.session.delete(retired)
            changed = True
    today = datetime.now(KENYA_TIMEZONE).date()
    for listing_type, listing_slug, tier, headline, days in DEFAULT_PROMOTIONS:
        if Promotion.query.filter_by(listing_type=listing_type, listing_slug=listing_slug).first():
            continue
        listing = (
            db.session.get(Tour, listing_slug) if listing_type == 'tour'
            else Property.query.filter_by(slug=listing_slug).first()
        )
        if not listing:
            continue
        db.session.add(Promotion(
            listing_type=listing_type,
            listing_slug=listing_slug,
            tier=tier,
            headline=headline,
            starts_on=today,
            ends_on=today + timedelta(days=days),
            impressions=0,
            clicks=0,
        ))
        changed = True
    if changed or db.session.new or db.session.dirty:
        db.session.commit()

    legacy_reviews = Review.query.filter(Review.target_type.is_(None)).all()
    for review in legacy_reviews:
        tour = Tour.query.filter(db.func.lower(Tour.name) == review.place.lower()).first()
        listing = Property.query.filter(db.func.lower(Property.name) == review.place.lower()).first()
        if tour:
            review.target_type, review.target_id = 'tour', tour.slug
        elif listing:
            review.target_type, review.target_id = 'property', listing.slug
    if legacy_reviews:
        db.session.commit()


def bootstrap_admin_account():
    email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    password = os.environ.get('ADMIN_PASSWORD', '')
    if not email or not password or AdminAccount.query.count():
        return
    db.session.add(AdminAccount(
        name=os.environ.get('ADMIN_NAME', 'Administrator').strip() or 'Administrator',
        email=email,
        password_hash=generate_password_hash(password),
    ))
    db.session.commit()


def is_admin_logged_in():
    admin_id = session.get('admin_id')
    return bool(admin_id and db.session.get(AdminAccount, admin_id))


def get_current_vendor():
    vendor_id = session.get('vendor_id')
    vendor = db.session.get(VendorAccount, vendor_id) if vendor_id else None
    return vendor if vendor and vendor.is_active else None


def auth_attempt_key():
    email = request.form.get('email', '').strip().lower()[:120]
    return f'{get_remote_address()}:{email}'


def auth_account_key():
    email = request.form.get('email', '').strip().lower()[:120]
    if not email:
        return auth_attempt_key()
    return f'{request.path}:{email}'


def failed_auth_attempt(response):
    return response.status_code == 401 or 'error=' in response.headers.get('Location', '')


def is_vendor_logged_in():
    return get_current_vendor() is not None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin_logged_in():
            if request.path.startswith('/api/'):
                return {'error': 'Admin sign-in is required.'}, 401
            return redirect('/admin/login')
        return view(*args, **kwargs)
    return wrapped


def vendor_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_vendor_logged_in():
            if request.path.startswith('/api/'):
                return {'error': 'Partner sign-in is required.'}, 401
            return redirect('/partner/login')
        return view(*args, **kwargs)
    return wrapped


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get('user_id')
        user = db.session.get(User, user_id) if user_id else None
        if not user or not user.is_active:
            return {'error': 'Sign in to view and manage your bookings.'}, 401
        return view(*args, **kwargs)
    return wrapped


def _valid_csrf(session_key, *, allow_form=False):
    token = request.headers.get('X-CSRF-Token')
    if allow_form:
        token = token or request.form.get('csrf_token')
    expected = session.get(session_key, '')
    return bool(token and expected and secrets.compare_digest(token, expected))


def _require_csrf(session_key, message, *, allow_form=False):
    if not _valid_csrf(session_key, allow_form=allow_form):
        return {'error': message}, 403
    return None


def valid_admin_csrf():
    return _valid_csrf('admin_csrf', allow_form=True)


def require_admin_csrf():
    return _require_csrf('admin_csrf', 'Your session expired. Refresh the page and try again.', allow_form=True)


def valid_vendor_csrf():
    return _valid_csrf('vendor_csrf', allow_form=True)


def require_vendor_csrf():
    return _require_csrf('vendor_csrf', 'Your session expired. Refresh the page and try again.', allow_form=True)


def require_customer_csrf():
    return _require_csrf('customer_csrf', 'Your session expired. Refresh the page and try again.')


def require_vendor_registration_csrf():
    return _require_csrf('vendor_registration_csrf', 'Refresh the page before creating a partner account.')


def safe_image_url(value):
    image_url = str(value or '').strip()
    if not image_url:
        return None
    if image_url.startswith(('https://', 'http://')):
        return image_url
    if image_url.startswith(('images/', 'pictures/', 'uploads/')) and '..' not in image_url.split('/'):
        return image_url
    raise ValueError('Image must use an http(s) URL or a path under images/, pictures/, or uploads/.')


_database_initialized = False
_database_initialization_lock = threading.Lock()


def initialize_database():
    """Create/update the schema without preventing health checks from loading."""
    global _database_initialized
    if _database_initialized:
        return
    with _database_initialization_lock:
        if _database_initialized:
            return
        db.create_all()
        ensure_booking_payment_columns()
        ensure_identity_columns()
        ensure_operator_columns()
        ensure_catalog_columns()
        ensure_review_columns()
        ensure_refund_columns()
        ensure_admin_settings()
        seed_catalogue()
        bootstrap_admin_account()
        _database_initialized = True


if os.environ.get('VERCEL') != '1':
    with app.app_context():
        initialize_database()


@app.before_request
def ensure_vercel_database():
    if os.environ.get('VERCEL') != '1' or request.path in {'/healthz', '/readyz'}:
        return None
    try:
        initialize_database()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception('Database initialization failed for the request.')
        return {'error': 'Database unavailable.'}, 503
    return None


def save_submission(submission: dict) -> Submission:
    new_submission = Submission(
        name=submission['name'],
        email=submission['email'],
        subject=submission['subject'],
        message=submission['message'],
        timestamp=datetime.fromisoformat(submission['timestamp'][:-1]) if submission.get('timestamp') else datetime.utcnow(),
        email_sent=submission.get('email_sent', False)
    )
    db.session.add(new_submission)
    db.session.commit()
    return new_submission


def calculate_booking_price(tour: str, guests: int) -> int:
    return calculate_booking_price_service(tour, guests, app)


def save_booking(booking: dict) -> Booking:
    return save_booking_service(booking)


def normalize_mpesa_phone(country_code: str, phone: str) -> str:
    if country_code != '+254':
        raise ValueError('M-Pesa payments require a Kenyan phone number.')
    if not phone.isdigit():
        raise ValueError('Enter your M-Pesa phone number using digits only.')

    normalized = phone
    if len(normalized) == 10 and normalized.startswith('0'):
        normalized = normalized[1:]
    elif len(normalized) == 12 and normalized.startswith('254'):
        normalized = normalized[3:]
    if len(normalized) != 9 or normalized[0] not in {'1', '7'}:
        raise ValueError('Enter a valid Kenyan mobile number for M-Pesa.')
    return f'254{normalized}'


def create_daraja_stk_push(booking: Booking):
    result = initiate_stk_push(
        booking.phone.removeprefix('+'),
        int(round(booking.amount)),
        booking.id,
    )
    booking.checkout_request_id = result['checkout_request_id']
    booking.merchant_request_id = result.get('merchant_request_id')
    db.session.commit()
    return result


def _callback_metadata(callback):
    metadata_container = callback.get('CallbackMetadata', {})
    if not isinstance(metadata_container, dict):
        return {}
    metadata = metadata_container.get('Item', [])
    if not isinstance(metadata, list):
        return {}
    return {
        item.get('Name'): item.get('Value')
        for item in metadata
        if isinstance(item, dict) and isinstance(item.get('Name'), str)
    }


def release_booking_availability(booking):
    """Return the held inventory when a booking fails or is cancelled."""
    if booking.booking_type == 'property' and booking.room_id:
        room = db.session.get(PropertyRoom, booking.room_id)
        if room is not None:
            release_room_nights(room, booking.check_in, booking.check_out)
        return
    release_schedule(booking.schedule_id, booking.guests)


def booking_listing_name(booking):
    if booking.booking_type == 'property':
        listing = Property.query.filter_by(slug=booking.tour).first()
        return listing.name if listing else booking.tour.replace('-', ' ').title()
    tour = db.session.get(Tour, booking.tour)
    return tour.name if tour else booking.tour.replace('-', ' ').title()


def booking_room_name(booking):
    if not booking.room_id:
        return ''
    room = db.session.get(PropertyRoom, booking.room_id)
    return room.name if room else ''


REFUND_TRANSITIONS = {
    'none': {'pending'},
    'pending': {'paid', 'rejected'},
    'rejected': {'pending'},
    'paid': set(),
}
REFUND_STATUS_LABELS = {
    'none': 'No refund',
    'pending': 'Refund due',
    'paid': 'Refund paid',
    'rejected': 'Refund declined',
}


def queue_booking_refund(booking, reason):
    """Record the full refund owed to the customer for a cancelled booking."""
    booking.refund_status = 'pending'
    booking.refund_amount = float(booking.amount or 0)
    booking.refund_reason = reason
    booking.refund_requested_at = datetime.utcnow()
    booking.refund_paid_at = None


def queue_cancellation_refund(booking, actor):
    """Queue the automatic full refund for a paid booking that was just cancelled."""
    if booking.payment_status != 'paid' or float(booking.amount or 0) <= 0:
        return False
    if booking.refund_status != 'none':
        return False
    queue_booking_refund(
        booking,
        f'Booking cancelled by the {actor}; the full amount is refundable.',
    )
    return True


def mark_booking_refund_paid(booking):
    """Record a refund the team sent outside the app."""
    booking.refund_status = 'paid'
    booking.refund_amount = float(booking.refund_amount or booking.amount or 0)
    booking.refund_paid_at = datetime.utcnow()
    booking.payment_status = 'refunded'


STAY_CHECK_OUT_HOUR = 10
REVIEW_BLOCKED_MESSAGES = {
    'reviewed': 'You already reviewed this booking. Thank you!',
    'ineligible': 'Only paid bookings that were used can be reviewed.',
    'upcoming': 'You can review this booking once the experience or stay is over.',
}


def booking_review_target(booking):
    """Return the listing type, slug and name a booking should be reviewed against."""
    if booking.booking_type == 'property':
        listing = Property.query.filter_by(slug=booking.tour).first()
        return ('property', listing.slug, listing.name) if listing else (None, None, None)
    tour = db.session.get(Tour, booking.tour)
    return ('tour', tour.slug, tour.name) if tour else (None, None, None)


def booking_service_end(booking):
    """Return the local time the booked experience or stay finishes."""
    if booking.booking_type == 'property':
        if not booking.check_out:
            return None
        try:
            check_out = parse_stay_date(booking.check_out)
        except ValueError:
            return None
        return datetime.combine(check_out, datetime.min.time()).replace(hour=STAY_CHECK_OUT_HOUR)
    try:
        return datetime.strptime(f'{booking.date} {booking.time}', '%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return None


def review_capability(booking, review):
    """Return (can_review, reason) for a booking the customer already paid for."""
    if review is not None:
        return False, 'reviewed'
    if booking.status == 'cancelled' or booking.payment_status != 'paid':
        return False, 'ineligible'
    if booking.status == 'completed':
        return True, 'ready'
    ended = booking_service_end(booking)
    if ended is not None and ended <= datetime.now(KENYA_TIMEZONE).replace(tzinfo=None):
        return True, 'ready'
    return False, 'upcoming'


def booking_review_state(booking):
    review = Review.query.filter_by(booking_id=booking.id).first()
    can_review, reason = review_capability(booking, review)
    return can_review, reason, review


def review_blocked_message(reason):
    return REVIEW_BLOCKED_MESSAGES.get(reason, 'This booking cannot be reviewed yet.')


def review_ratings(target_type, target_ids=None):
    """Average rating and review count for each listing slug."""
    query = db.session.query(
        Review.target_id,
        db.func.count(Review.id),
        db.func.avg(Review.rating),
    ).filter(Review.target_type == target_type)
    if target_ids is not None:
        target_ids = [target_id for target_id in target_ids if target_id]
        if not target_ids:
            return {}
        query = query.filter(Review.target_id.in_(target_ids))
    return {
        target_id: {'rating': round(float(average or 0), 1), 'review_count': int(count)}
        for target_id, count, average in query.group_by(Review.target_id).all()
    }


DISCOVERY_RECENT_DAYS = 30
DISCOVERY_PRICE_BAND = 0.1
DISCOVERY_PRICE_PEER_MIN_SIZE = 3
DISCOVERY_TOP_RATED_MIN_REVIEWS = 2
DISCOVERY_POPULAR_MIN_BOOKINGS = 3
DISCOVERY_POPULAR_MIN_RECENT = 2


def paid_booking_signals():
    """Lifetime and recent verified booking counts for every listing."""
    recent_since = datetime.utcnow() - timedelta(days=DISCOVERY_RECENT_DAYS)
    rows = db.session.query(
        Booking.tour,
        db.func.count(Booking.id),
        db.func.coalesce(db.func.sum(case((Booking.created_at >= recent_since, 1), else_=0)), 0),
    ).filter(Booking.payment_status == 'paid').group_by(Booking.tour).all()
    return {
        slug: {'paid_bookings': int(total or 0), 'recent_bookings': int(recent or 0)}
        for slug, total, recent in rows
        if slug
    }


def room_rate_ranges():
    """Lowest and highest active nightly rate published for each property."""
    rows = db.session.query(
        PropertyRoom.property_id,
        db.func.min(PropertyRoom.base_rate),
        db.func.max(PropertyRoom.base_rate),
        db.func.count(PropertyRoom.id),
    ).filter(
        PropertyRoom.is_active.is_(True),
        PropertyRoom.base_rate > 0,
    ).group_by(PropertyRoom.property_id).all()
    return {
        property_id: {
            'price_from': int(lowest or 0),
            'price_to': int(highest or 0),
            'room_types': int(room_count or 0),
        }
        for property_id, lowest, highest, room_count in rows
    }


def median_price(values):
    ordered = sorted(float(value) for value in values if value and float(value) > 0)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def price_comparison(price, peers, label=''):
    """Compare a listing's starting price with the median of comparable listings."""
    peer_median = median_price(peers)
    starting_price = float(price or 0)
    if not starting_price or not peer_median:
        return {
            'median': round(peer_median),
            'difference_percent': 0.0,
            'position': 'unknown',
            'label': label,
        }
    difference = (starting_price - peer_median) / peer_median
    if difference <= -DISCOVERY_PRICE_BAND:
        position = 'below'
    elif difference >= DISCOVERY_PRICE_BAND:
        position = 'above'
    else:
        position = 'typical'
    return {
        'median': round(peer_median),
        'difference_percent': round(difference * 100, 1),
        'position': position,
        'label': label,
    }


def listing_badges(*, rating, review_count, paid_bookings, recent_bookings, comparison):
    """Honest, data-backed labels shown next to listings."""
    badges = []
    if review_count >= DISCOVERY_TOP_RATED_MIN_REVIEWS and rating >= 4.5:
        badges.append('Top rated')
    if paid_bookings >= DISCOVERY_POPULAR_MIN_BOOKINGS or recent_bookings >= DISCOVERY_POPULAR_MIN_RECENT:
        badges.append('Popular')
    if comparison['position'] == 'below' and (review_count == 0 or rating >= 4.0):
        badges.append('Best value')
    return badges


def catalogue_insights():
    """Ratings, verified demand and price positioning for every listing.

    These signals steer search ranking, recommendations and price display so the
    marketplace reacts to what travelers actually book instead of static order.
    """
    tours = Tour.query.all()
    properties = Property.query.all()
    destination_names = {item.slug: item.name for item in Destination.query.all()}
    tour_ratings = review_ratings('tour', [tour.slug for tour in tours])
    property_ratings = review_ratings('property', [listing.slug for listing in properties if listing.slug])
    demand = paid_booking_signals()
    rates = room_rate_ranges()

    tour_prices = []
    tours_by_destination = {}
    for tour in tours:
        price = float(tour.price or 0)
        if price > 0:
            tour_prices.append(price)
            tours_by_destination.setdefault(tour.destination, []).append(price)

    property_starting_prices = {}
    property_prices = []
    properties_by_destination = {}
    for listing in properties:
        rate = rates.get(listing.id) or {}
        starting = float(rate.get('price_from') or listing.price_per_night or 0)
        property_starting_prices[listing.slug] = starting
        if starting > 0:
            property_prices.append(starting)
            properties_by_destination.setdefault(listing.destination, []).append(starting)

    def peer_group(groups, key, all_prices):
        group = groups.get(key) or []
        if len(group) >= DISCOVERY_PRICE_PEER_MIN_SIZE:
            return group, destination_names.get(key, '')
        return all_prices, ''

    insights = {'tours': {}, 'properties': {}}
    for tour in tours:
        rating = tour_ratings.get(tour.slug, {'rating': 0, 'review_count': 0})
        signal = demand.get(tour.slug, {})
        peers, label = peer_group(tours_by_destination, tour.destination, tour_prices)
        comparison = price_comparison(tour.price, peers, label)
        insights['tours'][tour.slug] = {
            'rating': rating['rating'],
            'review_count': rating['review_count'],
            'paid_bookings': signal.get('paid_bookings', 0),
            'recent_bookings': signal.get('recent_bookings', 0),
            'price_from': int(tour.price or 0),
            'price_to': int(tour.price or 0),
            'room_types': 0,
            'price_comparison': comparison,
            'badges': listing_badges(
                rating=rating['rating'],
                review_count=rating['review_count'],
                paid_bookings=signal.get('paid_bookings', 0),
                recent_bookings=signal.get('recent_bookings', 0),
                comparison=comparison,
            ),
        }

    for listing in properties:
        if not listing.slug:
            continue
        rating = property_ratings.get(listing.slug, {'rating': 0, 'review_count': 0})
        signal = demand.get(listing.slug, {})
        rate = rates.get(listing.id) or {}
        starting = property_starting_prices.get(listing.slug) or float(listing.price_per_night or 0)
        peers, label = peer_group(properties_by_destination, listing.destination, property_prices)
        comparison = price_comparison(starting, peers, label)
        insights['properties'][listing.slug] = {
            'rating': rating['rating'],
            'review_count': rating['review_count'],
            'paid_bookings': signal.get('paid_bookings', 0),
            'recent_bookings': signal.get('recent_bookings', 0),
            'price_from': int(starting),
            'price_to': int(rate.get('price_to') or starting),
            'room_types': int(rate.get('room_types') or 0),
            'price_comparison': comparison,
            'badges': listing_badges(
                rating=rating['rating'],
                review_count=rating['review_count'],
                paid_bookings=signal.get('paid_bookings', 0),
                recent_bookings=signal.get('recent_bookings', 0),
                comparison=comparison,
            ),
        }
    return insights


def _release_failed_mpesa_booking(booking: Booking, result_description: str):
    if booking.payment_status != 'pending':
        return
    release_booking_availability(booking)
    booking.payment_status = 'failed'
    booking.status = 'cancelled'
    db.session.commit()
    app.logger.info('M-Pesa payment failed for booking %s: %s', booking.id, result_description)


def process_daraja_callback(payload):
    body = payload.get('Body')
    if not isinstance(body, dict) or not isinstance(body.get('stkCallback'), dict):
        return 'Invalid callback payload', 400
    stk_callback = body['stkCallback']
    checkout_request_id = stk_callback.get('CheckoutRequestID')
    merchant_request_id = stk_callback.get('MerchantRequestID')
    callback_result_code = stk_callback.get('ResultCode')
    if not all(isinstance(value, str) and value for value in (checkout_request_id, merchant_request_id)):
        return 'Invalid callback references', 400
    try:
        callback_result_code = int(callback_result_code)
    except (TypeError, ValueError):
        return 'Invalid callback result', 400

    booking = Booking.query.filter_by(checkout_request_id=checkout_request_id).first()
    if booking and booking.merchant_request_id == merchant_request_id:
        return _process_booking_daraja_callback(
            booking, stk_callback, checkout_request_id, callback_result_code
        )

    payment = VendorSubscriptionPayment.query.filter_by(
        checkout_request_id=checkout_request_id
    ).first()
    if payment and payment.merchant_request_id == merchant_request_id:
        return _process_subscription_daraja_callback(
            payment, stk_callback, checkout_request_id, callback_result_code
        )

    app.logger.warning('Ignoring unmatched Daraja callback.')
    return '', 204


def _verified_daraja_result(checkout_request_id, callback_result_code, context):
    """Confirm a callback against Daraja's own record of the payment."""
    try:
        query_result = query_stk_push(checkout_request_id)
    except DarajaError:
        app.logger.exception('Could not verify Daraja callback for %s.', context)
        return None, ('Payment verification temporarily unavailable', 503)

    try:
        query_result_code = int(query_result.get('ResultCode', -1))
    except (TypeError, ValueError):
        query_result_code = -1
    if (
        str(query_result.get('ResponseCode', '')) != '0'
        or query_result.get('CheckoutRequestID') != checkout_request_id
        or query_result_code != callback_result_code
    ):
        app.logger.warning('Daraja query did not match callback for %s.', context)
        return None, ('Payment verification is pending', 503)
    return query_result, None


def _callback_amount_and_phone(stk_callback):
    """Amount, payer phone, and receipt from a successful STK callback."""
    metadata = _callback_metadata(stk_callback)
    receipt = metadata.get('MpesaReceiptNumber')
    phone_number = metadata.get('PhoneNumber')
    try:
        raw_amount = metadata.get('Amount')
        if raw_amount is None or phone_number is None:
            raise ValueError('Missing payment amount or phone number')
        amount = int(raw_amount)
        phone_number = str(int(phone_number))
    except (TypeError, ValueError):
        return None
    if not isinstance(receipt, str) or not receipt:
        return None
    return amount, phone_number, receipt


def _process_booking_daraja_callback(booking, stk_callback, checkout_request_id, callback_result_code):
    if booking.payment_status != 'pending':
        return '', 204

    context = f'booking {booking.id}'
    query_result, error = _verified_daraja_result(checkout_request_id, callback_result_code, context)
    if error:
        return error

    if callback_result_code != 0:
        try:
            _release_failed_mpesa_booking(
                booking,
                str(query_result.get('ResultDesc') or stk_callback.get('ResultDesc') or 'Payment was not completed.'),
            )
        except ValueError:
            db.session.rollback()
            app.logger.exception('Could not release capacity for failed M-Pesa booking %s.', booking.id)
            return 'Could not update booking availability', 503
        return '', 204

    details = _callback_amount_and_phone(stk_callback)
    if details is None:
        return 'Invalid payment details', 400
    amount, phone_number, receipt = details
    if amount != int(round(booking.amount)) or phone_number != booking.phone.removeprefix('+'):
        app.logger.error('Daraja payment details did not match booking %s.', booking.id)
        return 'Payment details did not match booking', 400

    cancelled = booking.status == 'cancelled'
    booking.payment_status = 'paid'
    if not cancelled:
        booking.status = 'confirmed'
    booking.mpesa_receipt_number = receipt
    booking.payment_confirmed_at = datetime.utcnow()
    if cancelled:
        queue_booking_refund(
            booking,
            'Payment was confirmed after the booking was cancelled, so the full amount is refundable.',
        )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        app.logger.exception('Daraja receipt could not be uniquely assigned to booking %s.', booking.id)
        return 'Payment receipt was already processed', 409
    if cancelled:
        app.logger.warning(
            'Booking %s was paid after cancellation; refund queued for manual payout.', booking.id
        )
        send_refund_notification(booking, paid=False)
    else:
        send_booking_confirmation(booking, payment_confirmed=True)
    return '', 204


def activate_vendor_subscription(vendor, payment):
    """Extend a partner's subscription by the month the payment just bought."""
    now = datetime.utcnow()
    start = vendor.subscription_renews_at if vendor.subscription_is_active() else now
    if not start or start < now:
        start = now
    payment.period_start = start
    payment.period_end = start + VENDOR_SUBSCRIPTION_PERIOD
    vendor.subscription_status = 'active'
    vendor.subscription_plan = 'monthly'
    vendor.subscription_started_at = vendor.subscription_started_at or now
    vendor.subscription_renews_at = payment.period_end
    vendor.subscription_monthly_fee = float(payment.amount or 0)


def _process_subscription_daraja_callback(payment, stk_callback, checkout_request_id, callback_result_code):
    if payment.status != 'pending':
        return '', 204

    context = f'subscription payment {payment.id}'
    query_result, error = _verified_daraja_result(checkout_request_id, callback_result_code, context)
    if error:
        return error

    if callback_result_code != 0:
        payment.status = 'failed'
        db.session.commit()
        app.logger.info(
            'M-Pesa subscription payment %s failed: %s',
            payment.id,
            query_result.get('ResultDesc') or stk_callback.get('ResultDesc') or 'Payment was not completed.',
        )
        return '', 204

    details = _callback_amount_and_phone(stk_callback)
    if details is None:
        return 'Invalid payment details', 400
    amount, phone_number, receipt = details
    if amount != int(round(payment.amount)) or phone_number != payment.phone.removeprefix('+'):
        app.logger.error('Daraja payment details did not match subscription payment %s.', payment.id)
        return 'Payment details did not match subscription', 400

    vendor = db.session.get(VendorAccount, payment.vendor_id)
    if vendor is None:
        app.logger.error('Subscription payment %s has no partner account.', payment.id)
        return 'Subscription payment has no partner account', 409

    payment.status = 'paid'
    payment.mpesa_receipt_number = receipt
    payment.paid_at = datetime.utcnow()
    activate_vendor_subscription(vendor, payment)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        app.logger.exception('Daraja receipt could not be uniquely assigned to subscription payment %s.', payment.id)
        return 'Payment receipt was already processed', 409
    app.logger.info(
        'Partner %s renewed its subscription until %s.', vendor.id, vendor.subscription_renews_at
    )
    return '', 204


def send_email_message(message: EmailMessage, *, context: str) -> bool:
    """Deliver an EmailMessage through the configured SMTP transport."""
    if not (EMAIL_HOST and EMAIL_USERNAME and EMAIL_PASSWORD and EMAIL_FROM):
        app.logger.warning('Email skipped (%s): missing SMTP configuration.', context)
        return False
    try:
        if EMAIL_USE_SSL:
            with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
                server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
                server.ehlo()
                if EMAIL_USE_TLS:
                    server.starttls()
                    server.ehlo()
                server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
                server.send_message(message)
    except Exception:
        app.logger.exception('Failed to send email (%s).', context)
        return False
    app.logger.info('Email sent (%s).', context)
    return True


def send_email_notification(submission: dict) -> bool:
    if not EMAIL_TO:
        app.logger.warning('Email notification skipped: missing EMAIL_TO configuration.')
        return False

    message = EmailMessage()
    message['Subject'] = f"New contact message from {submission['name']}"
    message['From'] = EMAIL_FROM
    message['To'] = EMAIL_TO
    message.set_content(
        f"Name: {submission['name']}\n"
        f"Email: {submission['email']}\n"
        f"Subject: {submission['subject']}\n"
        f"Message:\n{submission['message']}\n"
        f"Sent at: {submission['timestamp']}\n"
    )

    return send_email_message(message, context=f'contact message from {submission["email"]}')


def generate_booking_document(booking: Booking, document_type: str) -> bytes:
    if document_type not in {'invoice', 'receipt'}:
        raise ValueError('Unsupported booking document type.')
    if document_type == 'receipt' and not booking.mpesa_receipt_number:
        raise ValueError('A verified payment is required to generate a receipt.')

    def safe_text(value):
        return str(value or '').encode('cp1252', 'replace').decode('cp1252')

    output = BytesIO()
    document = canvas.Canvas(output, pagesize=letter)
    document_id = f"{'INV' if document_type == 'invoice' else 'RCT'}-{booking.id:06d}"
    issued_at = booking.payment_confirmed_at if document_type == 'receipt' else booking.created_at
    issued_at = issued_at or datetime.utcnow()
    document.setTitle(f'{BRAND_NAME} {document_type.title()} {document_id}')
    document.setFillColorRGB(0.13, 0.25, 0.22)
    document.setFont('Helvetica-Bold', 22)
    document.drawString(72, 730, BRAND_NAME)
    document.setFont('Helvetica', 10)
    document.setFillColorRGB(0.35, 0.40, 0.37)
    document.drawString(72, 712, safe_text(SITE_URL))
    document.setFillColorRGB(0.13, 0.25, 0.22)
    document.setFont('Helvetica-Bold', 18)
    document.drawRightString(540, 730, document_type.upper())
    document.setFont('Helvetica', 10)
    document.drawRightString(540, 710, safe_text(document_id))
    document.drawRightString(540, 694, safe_text(issued_at.strftime('%d %b %Y %H:%M UTC')))
    document.setStrokeColorRGB(0.72, 0.43, 0.27)
    document.setLineWidth(1.5)
    document.line(72, 675, 540, 675)

    rows = [
        ('Booking reference', f'#{booking.id}'),
        ('Customer', booking.name),
        ('Email', booking.email),
    ]
    if booking.booking_type == 'property':
        rows.extend([
            ('Accommodation', booking_listing_name(booking)),
            ('Room', booking_room_name(booking) or 'Room'),
            ('Check-in', booking.check_in or booking.date),
            ('Check-out', booking.check_out or ''),
            ('Nights', str(booking.nights or '')),
        ])
    else:
        rows.extend([
            ('Experience', booking_listing_name(booking)),
            ('Date and time', f'{booking.date} at {booking.time} (Kenya time)'),
        ])
    rows.extend([
        ('Guests', str(booking.guests)),
        ('Payment status', booking.payment_status.replace('_', ' ').title()),
    ])
    if document_type == 'receipt':
        rows.extend([
            ('Payment method', 'M-Pesa'),
            ('M-Pesa receipt', booking.mpesa_receipt_number),
        ])
    y = 642
    for label, value in rows:
        document.setFont('Helvetica', 10)
        document.setFillColorRGB(0.35, 0.40, 0.37)
        document.drawString(72, y, safe_text(label))
        document.setFont('Helvetica-Bold', 10)
        document.setFillColorRGB(0.13, 0.25, 0.22)
        document.drawRightString(540, y, safe_text(value)[:70])
        y -= 25

    y -= 8
    document.setStrokeColorRGB(0.86, 0.86, 0.82)
    document.line(72, y, 540, y)
    y -= 30
    document.setFont('Helvetica', 10)
    document.setFillColorRGB(0.35, 0.40, 0.37)
    if booking.booking_type == 'property':
        summary = f'{booking_room_name(booking) or "Room"} · {booking.nights} night(s) · {booking.guests} guest(s)'
    else:
        summary = f'{booking.guests} guest(s) - {booking_listing_name(booking)}'
    document.drawString(72, y, safe_text(summary))
    subtotal_amount = booking.subtotal_amount or booking.amount
    service_fee_amount = booking.service_fee_amount or 0
    service_fee_rate = booking.guest_service_fee_rate or 0
    document.drawRightString(540, y, f'KSh {subtotal_amount:,.0f}')
    y -= 22
    document.drawString(72, y, safe_text(f'Service fee ({service_fee_rate:g}%)'))
    document.drawRightString(540, y, f'KSh {service_fee_amount:,.0f}')
    if booking.booking_fee_amount:
        y -= 22
        document.drawString(72, y, 'Booking fee')
        document.drawRightString(540, y, f'KSh {booking.booking_fee_amount:,.0f}')
    y -= 32
    document.setFont('Helvetica-Bold', 14)
    document.drawString(72, y, 'TOTAL PAID' if document_type == 'receipt' else 'TOTAL DUE')
    document.drawRightString(540, y, f'KSh {booking.amount:,.0f}')

    document.setFont('Helvetica', 9)
    document.setFillColorRGB(0.35, 0.40, 0.37)
    footer = 'Payment received and verified via M-Pesa.' if document_type == 'receipt' else 'Keep this invoice for your booking records.'
    document.drawString(72, 90, safe_text(footer))
    document.drawString(72, 74, safe_text(f'Payment reference: {booking.payment_reference}'))
    document.save()
    return output.getvalue()


def send_booking_confirmation(booking: Booking, *, payment_confirmed=False) -> bool:
    listing_name = booking_listing_name(booking)
    if booking.booking_type == 'property':
        booking_details = (
            f"Accommodation: {listing_name}\n"
            f"Room: {booking_room_name(booking) or 'Room'}\n"
            f"Check-in: {booking.check_in}\n"
            f"Check-out: {booking.check_out}\n"
            f"Nights: {booking.nights}\n"
        )
    else:
        booking_details = (
            f"Experience: {listing_name}\n"
            f"Date and time: {booking.date} at {booking.time} (Kenya time)\n"
        )
    message = EmailMessage()
    message['Subject'] = f"Payment confirmed for booking #{booking.id}" if payment_confirmed else f"Booking request #{booking.id} received"
    message['From'] = EMAIL_FROM
    message['To'] = booking.email
    message.set_content(
        f"Hello {booking.name},\n\n"
        f"We received your booking request for {listing_name}.\n"
        + booking_details
        + f"Guests: {booking.guests}\n"
        f"Subtotal: KSh {booking.subtotal_amount or booking.amount:,.0f}\n"
        f"Service fee ({(booking.guest_service_fee_rate or 0):g}%): KSh {booking.service_fee_amount or 0:,.0f}\n"
        f"Booking fee: KSh {booking.booking_fee_amount or 0:,.0f}\n"
        f"Total payable: KSh {booking.amount:,.0f}\n"
        f"Booking status: {booking.status}\n"
        + (
            f"M-Pesa payment received and verified. Receipt: {booking.mpesa_receipt_number}. Your invoice and receipt are attached.\n"
            if payment_confirmed
            else "Check the M-Pesa prompt on your phone to complete payment. We will confirm your booking after Daraja verifies the payment. Your invoice is attached.\n"
        )
        + f"\nYou can sign in at the {BRAND_NAME} website to view and manage bookings made with your account.\n"
    )
    try:
        invoice = generate_booking_document(booking, 'invoice')
        message.add_attachment(invoice, maintype='application', subtype='pdf', filename=f'{BRAND_NAME}-Invoice-{booking.id}.pdf')
        if booking.mpesa_receipt_number and booking.payment_status in {'paid', 'refunded'}:
            receipt = generate_booking_document(booking, 'receipt')
            message.add_attachment(receipt, maintype='application', subtype='pdf', filename=f'{BRAND_NAME}-Receipt-{booking.id}.pdf')
    except Exception:
        app.logger.exception('Could not generate payment documents for booking %s.', booking.id)
    return send_email_message(message, context=f'booking {booking.id} confirmation')


def send_booking_status_notification(booking: Booking) -> bool:
    if booking.booking_type == 'property':
        listing_details = (
            f"Accommodation: {booking_listing_name(booking)}\n"
            f"Room: {booking_room_name(booking) or 'Room'}\n"
            f"Check-in: {booking.check_in}\n"
            f"Check-out: {booking.check_out}\n"
        )
    else:
        listing_details = (
            f"Experience: {booking_listing_name(booking)}\n"
            f"Departure: {booking.date} at {booking.time} (Kenya time)\n"
        )
    message = EmailMessage()
    message['Subject'] = f"Booking #{booking.id} status updated"
    message['From'] = EMAIL_FROM
    message['To'] = booking.email
    message.set_content(
        f"Hello {booking.name},\n\n"
        f"The status of your {BRAND_NAME} booking #{booking.id} is now: {booking.status.replace('_', ' ').title()}.\n"
        + listing_details
        + "\nContact our team if you have questions about this update.\n"
    )
    return send_email_message(message, context=f'booking {booking.id} status update')


def send_refund_notification(booking: Booking, *, paid: bool) -> bool:
    """Best-effort email about a refund that is due or has been sent."""
    amount = float(booking.refund_amount or booking.amount or 0)
    if paid:
        message_body = (
            f"We have sent your refund of KSh {amount:,.0f} for booking #{booking.id}. "
            "It should reflect on your M-Pesa statement shortly.\n"
        )
    elif booking.refund_status == 'rejected':
        message_body = (
            f"The refund request for booking #{booking.id} was reviewed and declined. "
            "Contact our team if you would like us to look at the case again.\n"
        )
    else:
        message_body = (
            f"Your booking #{booking.id} was cancelled and a refund of KSh {amount:,.0f} is due. "
            "Our team processes refunds and will let you know once the money has been sent.\n"
        )
    message = EmailMessage()
    message['Subject'] = (
        f"Refund sent for booking #{booking.id}" if paid
        else f"Refund update for booking #{booking.id}"
    )
    message['From'] = EMAIL_FROM
    message['To'] = booking.email
    message.set_content(
        f"Hello {booking.name},\n\n"
        + message_body
        + f"Listing: {booking_listing_name(booking)}\n"
        + f"\nYou can follow the refund status in My bookings on the {BRAND_NAME} website.\n"
    )
    return send_email_message(message, context=f'booking {booking.id} refund update')


@app.route('/')
def index():
    return frontend_page()


@app.route('/operators/<string:slug>')
def operator_page(slug):
    """Serve the React operator profile; the profile data comes from the API."""
    return frontend_page()


@app.route('/blog/<string:slug>')
def blog_post_page(slug):
    """Serve the React travel guide; guide content is bundled with the frontend."""
    return frontend_page()


@app.route('/healthz')
def health_check():
    return {'status': 'ok'}, 200


@app.route('/readyz')
def readiness_check():
    try:
        db.session.execute(text('SELECT 1'))
    except SQLAlchemyError:
        app.logger.exception('Readiness check failed while querying the database.')
        return {'status': 'unavailable'}, 503
    return {'status': 'ready'}, 200


def frontend_page():
    frontend_index = os.path.join(FRONTEND_DIST, 'index.html')
    if not os.path.isfile(frontend_index):
        return {'error': 'Frontend build is unavailable.'}, 503
    return send_from_directory(FRONTEND_DIST, 'index.html')


@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit('10 per hour', key_func=auth_account_key, methods=['POST'], deduct_when=failed_auth_attempt)
@limiter.limit('5 per minute', key_func=auth_attempt_key, methods=['POST'])
@limiter.limit('30 per hour', methods=['POST'])
def admin_login():
    if request.method == 'GET':
        return frontend_page()

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    admin = AdminAccount.query.filter_by(email=email).first()
    if not admin or not check_password_hash(admin.password_hash, password):
        return redirect('/admin/login?error=Invalid%20admin%20email%20or%20password.')

    session.clear()
    session['admin_id'] = admin.id
    session['admin_csrf'] = secrets.token_urlsafe(32)
    return redirect('/admin')


@app.route('/partner/login', methods=['GET', 'POST'])
@app.route('/vendor/login', methods=['GET', 'POST'])
@limiter.limit('10 per hour', key_func=auth_account_key, methods=['POST'], deduct_when=failed_auth_attempt)
@limiter.limit('5 per minute', key_func=auth_attempt_key, methods=['POST'])
@limiter.limit('30 per hour', methods=['POST'])
def vendor_login():
    if request.method == 'GET':
        return frontend_page()

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    vendor = VendorAccount.query.filter_by(email=email).first()
    if not vendor or not vendor.is_active or not check_password_hash(vendor.password_hash, password):
        return redirect('/partner/login?error=Invalid%20partner%20email%20or%20password.')

    session.clear()
    session['vendor_id'] = vendor.id
    session['vendor_csrf'] = secrets.token_urlsafe(32)
    return redirect('/partner/dashboard')


@app.route('/api/vendor/registration-token', methods=['GET'])
def vendor_registration_token():
    token = secrets.token_urlsafe(32)
    session['vendor_registration_csrf'] = token
    return {'csrf_token': token}


@app.route('/partner/register', methods=['GET', 'POST'])
@app.route('/vendor/register', methods=['GET', 'POST'])
@limiter.limit('3 per hour', methods=['POST'])
def vendor_register():
    if request.method == 'GET':
        return frontend_page()

    response = require_vendor_registration_csrf()
    if response:
        return response
    data = json_payload()
    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    password = data.get('password', '')
    if not name or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or not isinstance(password, str) or len(password) < 12:
        return {'error': 'Enter your name, a valid email, and a password of at least 12 characters.'}, 400
    if VendorAccount.query.filter_by(email=email).first():
        return {'error': 'A partner account with that email already exists.'}, 409

    try:
        profile = vendor_profile_values({
            **data,
            'business_types': data.get('business_types') or ['tours'],
        })
    except ValueError as exc:
        return {'error': str(exc)}, 400

    vendor = VendorAccount(
        email=email,
        password_hash=generate_password_hash(password),
        slug=unique_slug(profile['name'], VendorAccount),
        **profile,
    )
    db.session.add(vendor)
    db.session.commit()
    session.clear()
    session['vendor_id'] = vendor.id
    session['vendor_csrf'] = secrets.token_urlsafe(32)
    return {'vendor': vendor.to_dict(), 'csrf_token': session['vendor_csrf']}, 201


@app.route('/partner/logout', methods=['POST'])
@app.route('/vendor/logout', methods=['POST'])
@vendor_required
def vendor_logout():
    response = require_vendor_csrf()
    if response:
        return response
    session.clear()
    return '', 204


@app.route('/partner/dashboard', methods=['GET'])
@app.route('/vendor/dashboard', methods=['GET'])
@vendor_required
def vendor_dashboard_page():
    return frontend_page()


@app.route('/api/vendor/profile', methods=['GET', 'PUT'])
@vendor_required
def vendor_profile():
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    if request.method == 'GET':
        return {'vendor': vendor.to_dict()}

    response = require_vendor_csrf()
    if response:
        return response
    try:
        values = vendor_profile_values(json_payload())
    except ValueError as exc:
        return {'error': str(exc)}, 400
    apply_values(vendor, values)
    if not vendor.slug:
        vendor.slug = unique_slug(vendor.name, VendorAccount, vendor.id)
        db.session.commit()
    return {'vendor': vendor.to_dict()}


@app.route('/my-bookings', methods=['GET'])
def customer_bookings_page():
    return frontend_page()


@app.route('/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    response = require_admin_csrf()
    if response:
        return response
    session.clear()
    if request.accept_mimetypes.best == 'application/json':
        return '', 204
    return redirect('/admin/login')


@app.route('/admin', methods=['GET'])
@admin_required
def admin_page():
    return frontend_page()


@app.route('/admin/dashboard', methods=['GET'])
@admin_required
def admin_dashboard_page():
    return frontend_page()


@app.route('/api/admin/catalogue', methods=['GET'])
@admin_required
def admin_catalogue():
    return {
        'csrf_token': session['admin_csrf'],
        'tours': [{**item.to_dict(), 'vendor_id': item.vendor_id} for item in Tour.query.order_by(Tour.name).all()],
        'properties': [{
            **item.to_dict(),
            'vendor_id': item.vendor_id,
            'owner_name': item.owner_name,
            'owner_email': item.owner_email,
        } for item in Property.query.order_by(Property.name).all()],
        'destinations': [item.to_dict() for item in Destination.query.order_by(Destination.name).all()],
        'services': [{
            **item.to_dict(),
            'vendor_name': (db.session.get(VendorAccount, item.vendor_id).name if item.vendor_id else ''),
        } for item in Service.query.order_by(Service.name).all()],
        'service_types': [[key, label] for key, label in SERVICE_TYPES.items()],
        'service_price_units': list(SERVICE_PRICE_UNITS),
        'tour_types': [[key, label] for key, label in TOUR_TYPES.items()],
        'tour_group_types': [[key, label] for key, label in TOUR_GROUP_TYPES.items()],
        'promotions': [
            {**item.to_dict(), 'listing_name': promotion_listing_name(item)}
            for item in Promotion.query.order_by(Promotion.ends_on.desc(), Promotion.id.desc()).all()
        ],
        'promotion_tiers': [[key, label] for key, label in PROMOTION_TIERS.items()],
        'promotion_listing_types': [[key, label] for key, label in PROMOTION_LISTING_TYPES.items()],
        'promotion_max_active': PROMOTION_MAX_ACTIVE,
        'newsletter': {
            'count': NewsletterSubscriber.query.filter_by(is_active=True).count(),
            'recent': [
                item.to_dict()
                for item in NewsletterSubscriber.query.order_by(
                    NewsletterSubscriber.created_at.desc()
                ).limit(10).all()
            ],
        },
        'admins': [{'id': item.id, 'name': item.name, 'email': item.email} for item in AdminAccount.query.order_by(AdminAccount.email).all()],
        'vendors': [{
            **vendor.to_dict(),
            'tour_count': Tour.query.filter_by(vendor_id=vendor.id).count(),
            'property_count': Property.query.filter_by(vendor_id=vendor.id).count(),
            'service_count': Service.query.filter_by(vendor_id=vendor.id).count(),
        } for vendor in VendorAccount.query.order_by(VendorAccount.email).all()],
    }


@app.route('/api/admin/dashboard', methods=['GET'])
@admin_required
def admin_dashboard_data():
    recent_submissions = Submission.query.order_by(Submission.timestamp.desc()).limit(20).all()
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(20).all()
    return {
        'csrf_token': session['admin_csrf'],
        'total_submissions': Submission.query.count(),
        'total_bookings': Booking.query.count(),
        'recent_submissions': [item.to_dict() for item in recent_submissions],
        'recent_bookings': [item.to_dict() for item in recent_bookings],
    }


def normalize_analytics_source(value):
    source = str(value or '').strip()[:512]
    if not source:
        return 'Direct'

    if '://' in source or source.startswith('//'):
        parsed = urllib.parse.urlsplit(source if '://' in source else f'https:{source}')
        hostname = (parsed.hostname or '').lower().removeprefix('www.')
        site_host = (urllib.parse.urlsplit(SITE_URL).hostname or '').lower().removeprefix('www.')
        if not hostname or hostname == site_host:
            return 'Direct'
        for token, label in (
            ('google.', 'Google'), ('bing.', 'Bing'), ('facebook.', 'Facebook'),
            ('instagram.', 'Instagram'), ('tiktok.', 'TikTok'), ('linkedin.', 'LinkedIn'),
            ('youtube.', 'YouTube'), ('t.co', 'X'), ('twitter.', 'X'),
        ):
            if token in hostname:
                return label
        return hostname[:120]

    label = re.sub(r'[^a-zA-Z0-9._ -]', '', source).strip()
    aliases = {
        'google': 'Google',
        'bing': 'Bing',
        'facebook': 'Facebook',
        'instagram': 'Instagram',
        'tiktok': 'TikTok',
        'linkedin': 'LinkedIn',
        'youtube': 'YouTube',
        'twitter': 'X',
        'x': 'X',
        'direct': 'Direct',
    }
    return aliases.get(label.lower(), label[:120]) or 'Direct'


@app.route('/api/analytics/events', methods=['POST'])
@limiter.limit('120 per minute')
def record_analytics_event():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {'error': 'Analytics event must be JSON.'}, 400
    page = payload.get('page')
    if not isinstance(page, str) or not page.startswith('/') or len(page) > 160:
        return {'error': 'A valid page path is required.'}, 400
    if page.startswith(('/admin', '/partner', '/vendor', '/dashboard')):
        return '', 204

    if 'analytics_source' not in session:
        session['analytics_source'] = normalize_analytics_source(payload.get('source'))
    visitor_token = session.setdefault('analytics_visitor_token', secrets.token_urlsafe(32))
    visitor_key = hashlib.sha256(visitor_token.encode('utf-8')).hexdigest()
    db.session.add(AnalyticsEvent(
        visitor_key=visitor_key,
        source=session['analytics_source'],
        page=page,
    ))
    db.session.commit()
    return '', 204


@app.route('/api/promotions/<string:listing_type>/<string:slug>/click', methods=['POST'])
@limiter.limit('120 per minute')
def record_promotion_click(listing_type, slug):
    """Count a click on a sponsored slot; best-effort, never blocks the visitor."""
    if listing_type not in PROMOTION_LISTING_TYPES:
        return {'error': 'Unknown promotion type.'}, 400
    promotion = Promotion.query.filter_by(listing_type=listing_type, listing_slug=slug).first()
    if promotion and promotion.is_live(datetime.now(KENYA_TIMEZONE).date()):
        promotion.clicks = (promotion.clicks or 0) + 1
        db.session.commit()
    return '', 204


@app.route('/api/admin/operations', methods=['GET'])
@admin_required
def admin_operations():
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(200).all()
    tour_slugs = {booking.tour for booking in bookings if booking.booking_type != 'property'}
    booking_tour_names = {
        tour.slug: tour.name for tour in Tour.query.filter(Tour.slug.in_(tour_slugs)).all()
    } if tour_slugs else {}
    stay_slugs = {booking.tour for booking in bookings if booking.booking_type == 'property'}
    stay_names = {
        listing.slug: listing.name for listing in Property.query.filter(Property.slug.in_(stay_slugs)).all()
    } if stay_slugs else {}
    booked_room_ids = {booking.room_id for booking in bookings if booking.room_id}
    room_names = {
        room.id: room.name for room in PropertyRoom.query.filter(PropertyRoom.id.in_(booked_room_ids)).all()
    } if booked_room_ids else {}
    booking_rows = []
    for booking in bookings:
        if booking.booking_type == 'property':
            listing_name = stay_names.get(booking.tour) or booking.tour.replace('-', ' ').title()
        else:
            listing_name = booking_tour_names.get(booking.tour, booking.tour)
        booking_rows.append({
            **booking.to_dict(),
            'tour_name': listing_name,
            'property_name': listing_name if booking.booking_type == 'property' else None,
            'room_name': room_names.get(booking.room_id, '') if booking.booking_type == 'property' else '',
        })

    booking_counts = dict(db.session.query(
        Booking.user_id,
        db.func.count(Booking.id),
    ).filter(Booking.user_id.isnot(None)).group_by(Booking.user_id).all())
    customers = [{
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'is_active': user.is_active,
        'created_at': user.created_at.isoformat() + 'Z' if user.created_at else None,
        'booking_count': booking_counts.get(user.id, 0),
    } for user in User.query.order_by(User.created_at.desc()).all()]
    vendors = [vendor.to_dict() for vendor in VendorAccount.query.order_by(VendorAccount.created_at.desc()).all()]

    report_rows = db.session.query(
        Booking.tour,
        db.func.count(Booking.id),
        db.func.coalesce(db.func.sum(
            case((Booking.payment_status == 'paid', Booking.amount), else_=0)
        ), 0),
        db.func.coalesce(db.func.sum(
            case(
                (
                    Booking.payment_status == 'paid',
                    Booking.service_fee_amount + Booking.booking_fee_amount + Booking.host_commission_amount,
                ),
                else_=0,
            )
        ), 0),
        db.func.coalesce(db.func.sum(
            case((Booking.payment_status == 'paid', Booking.host_payout_amount), else_=0)
        ), 0),
    ).group_by(Booking.tour).order_by(db.func.count(Booking.id).desc()).all()
    total_paid = sum(float(row[2] or 0) for row in report_rows)
    total_commission = sum(float(row[3] or 0) for row in report_rows)
    total_host_payout = sum(float(row[4] or 0) for row in report_rows)
    report_tour_slugs = {row[0] for row in report_rows}
    report_tour_names = {
        tour.slug: tour.name for tour in Tour.query.filter(Tour.slug.in_(report_tour_slugs)).all()
    } if report_tour_slugs else {}
    if report_tour_slugs:
        for listing in Property.query.filter(Property.slug.in_(report_tour_slugs)).all():
            report_tour_names.setdefault(listing.slug, listing.name)

    period_days = 30
    period_start = datetime.utcnow() - timedelta(days=period_days)
    recent_events = AnalyticsEvent.query.filter(AnalyticsEvent.created_at >= period_start).all()
    visitor_keys = {event.visitor_key for event in recent_events}
    checkout_visitor_keys = {
        event.visitor_key for event in recent_events if event.page == '/booking.html'
    }
    recent_bookings = Booking.query.filter(Booking.created_at >= period_start).all()
    recent_paid_bookings = [booking for booking in recent_bookings if booking.payment_status == 'paid']

    source_metrics = {}

    def source_bucket(source):
        return source_metrics.setdefault(source or 'Unattributed', {
            'visitor_keys': set(),
            'booking_requests': 0,
            'paid_bookings': 0,
            'paid_revenue': 0.0,
        })

    for event in recent_events:
        source_bucket(event.source)['visitor_keys'].add(event.visitor_key)
    for booking in recent_bookings:
        bucket = source_bucket(booking.traffic_source)
        bucket['booking_requests'] += 1
        if booking.payment_status == 'paid':
            bucket['paid_bookings'] += 1
            bucket['paid_revenue'] += float(booking.amount or 0)

    funnel_counts = [
        len(visitor_keys),
        len(checkout_visitor_keys),
        len(recent_bookings),
        len(recent_paid_bookings),
    ]
    funnel_labels = ['Unique visitors', 'Booking page visitors', 'Booking requests', 'Paid bookings']
    funnel = []
    for index, (label, count) in enumerate(zip(funnel_labels, funnel_counts)):
        previous_count = funnel_counts[index - 1] if index else count
        funnel.append({
            'label': label,
            'count': count,
            'conversion_rate': round(count / previous_count * 100, 1) if previous_count else 0,
        })

    traffic_sources = [{
        'source': source,
        'visitors': len(values['visitor_keys']),
        'booking_requests': values['booking_requests'],
        'paid_bookings': values['paid_bookings'],
        'paid_revenue': round(values['paid_revenue'], 2),
        'conversion_rate': round(values['booking_requests'] / len(values['visitor_keys']) * 100, 1)
        if values['visitor_keys'] else 0,
    } for source, values in source_metrics.items()]
    traffic_sources.sort(key=lambda row: (-row['visitors'], -row['booking_requests'], row['source']))

    current_month = datetime.now(KENYA_TIMEZONE).replace(tzinfo=None, day=1, hour=0, minute=0, second=0, microsecond=0)

    def month_start(offset):
        month_index = current_month.year * 12 + current_month.month - 1 + offset
        return datetime(month_index // 12, month_index % 12 + 1, 1)

    month_offsets = range(-5, 7)
    month_starts = [month_start(offset) for offset in month_offsets]
    occupancy = {
        start.strftime('%Y-%m'): {'capacity': 0, 'booked_seats': 0, 'departures': 0}
        for start in month_starts
    }
    schedules = TourSchedule.query.filter(
        TourSchedule.starts_at >= month_starts[0],
        TourSchedule.starts_at < month_start(7),
    ).all()
    for schedule in schedules:
        month = occupancy.get(schedule.starts_at.strftime('%Y-%m'))
        if month is None:
            continue
        month['capacity'] += schedule.capacity
        month['booked_seats'] += schedule.booked_count
        month['departures'] += 1
    occupancy_trends = [{
        'month': month,
        **values,
        'occupancy_rate': round(values['booked_seats'] / values['capacity'] * 100, 1)
        if values['capacity'] else 0,
    } for month, values in occupancy.items()]

    property_slugs = [property_listing.slug for property_listing in Property.query.all() if property_listing.slug]
    property_totals = {}
    if property_slugs:
        property_rows = db.session.query(
            Booking.tour,
            db.func.count(Booking.id),
            db.func.coalesce(db.func.sum(case((Booking.payment_status == 'paid', 1), else_=0)), 0),
            db.func.coalesce(db.func.sum(case((Booking.payment_status == 'paid', Booking.amount), else_=0)), 0),
        ).filter(
            # Legacy stay bookings predate booking_type and never had a tour schedule.
            or_(Booking.booking_type == 'property', Booking.schedule_id.is_(None)),
            Booking.tour.in_(property_slugs),
        ).group_by(Booking.tour).all()
        property_totals = {
            row[0]: {'bookings': row[1], 'paid_bookings': row[2], 'paid_revenue': float(row[3] or 0)}
            for row in property_rows
        }
    property_revenue = [{
        'slug': property_listing.slug,
        'name': property_listing.name,
        'bookings': property_totals.get(property_listing.slug, {}).get('bookings', 0),
        'paid_bookings': property_totals.get(property_listing.slug, {}).get('paid_bookings', 0),
        'paid_revenue': property_totals.get(property_listing.slug, {}).get('paid_revenue', 0),
    } for property_listing in Property.query.filter(Property.slug.isnot(None)).all()]
    property_revenue.sort(key=lambda row: (-row['paid_revenue'], row['name']))

    disputes = BookingDispute.query.order_by(BookingDispute.created_at.desc()).limit(100).all()
    dispute_booking_ids = {dispute.booking_id for dispute in disputes}
    dispute_bookings = {
        booking.id: booking for booking in Booking.query.filter(Booking.id.in_(dispute_booking_ids)).all()
    } if dispute_booking_ids else {}
    dispute_rows = []
    for dispute in disputes:
        booking = dispute_bookings.get(dispute.booking_id)
        dispute_rows.append({
            **dispute.to_dict(),
            'booking_name': booking.name if booking else 'Booking removed',
            'booking_email': booking.email if booking else '',
            'tour': booking.tour if booking else '',
        })
    refund_due_count, refund_due_amount = db.session.query(
        db.func.count(Booking.id),
        db.func.coalesce(db.func.sum(Booking.refund_amount), 0),
    ).filter(Booking.refund_status == 'pending').one()

    discovery = catalogue_insights()
    tour_names = {tour.slug: tour.name for tour in Tour.query.all()}
    stay_names = {
        listing.slug: listing.name for listing in Property.query.filter(Property.slug.isnot(None)).all()
    }
    revenue_by_slug = {row[0]: float(row[2] or 0) for row in report_rows}
    price_rows = []
    for slug_key, insight in discovery['tours'].items():
        price_rows.append({
            'slug': slug_key,
            'name': tour_names.get(slug_key, slug_key.replace('-', ' ').title()),
            'kind': 'tour',
            'price_from': insight['price_from'],
            'price_to': insight['price_to'],
            'price_unit': 'per guest',
            'median': insight['price_comparison']['median'],
            'difference_percent': insight['price_comparison']['difference_percent'],
            'position': insight['price_comparison']['position'],
            'paid_bookings': insight['paid_bookings'],
            'recent_bookings': insight['recent_bookings'],
            'paid_revenue': revenue_by_slug.get(slug_key, 0.0),
        })
    for slug_key, insight in discovery['properties'].items():
        price_rows.append({
            'slug': slug_key,
            'name': stay_names.get(slug_key, slug_key.replace('-', ' ').title()),
            'kind': 'stay',
            'price_from': insight['price_from'],
            'price_to': insight['price_to'],
            'price_unit': 'per night',
            'median': insight['price_comparison']['median'],
            'difference_percent': insight['price_comparison']['difference_percent'],
            'position': insight['price_comparison']['position'],
            'paid_bookings': insight['paid_bookings'],
            'recent_bookings': insight['recent_bookings'],
            'paid_revenue': revenue_by_slug.get(slug_key, 0.0),
        })

    def summarize_price_rows(rows):
        prices = [row['price_from'] for row in rows if row['price_from'] > 0]
        return {
            'listings': len(rows),
            'priced_listings': len(prices),
            'median_price': round(median_price(prices)),
            'below_market': sum(1 for row in rows if row['position'] == 'below'),
            'above_market': sum(1 for row in rows if row['position'] == 'above'),
            'around_market': sum(1 for row in rows if row['position'] == 'typical'),
        }

    tour_price_rows = [row for row in price_rows if row['kind'] == 'tour']
    stay_price_rows = [row for row in price_rows if row['kind'] == 'stay']
    price_rows.sort(key=lambda row: (-row['paid_revenue'], row['name']))

    return {
        'csrf_token': session['admin_csrf'],
        'settings': {
            'host_commission_rate': platform_fee_rates()[0],
            'subscriber_host_commission_rate': platform_subscriber_rate(),
            'guest_service_fee_rate': platform_fee_rates()[1],
            'booking_fee': platform_booking_fee(),
            'subscription_monthly_fee': platform_subscription_fee(),
            'refund_policy': get_admin_setting('refund_policy', 'automatic'),
            'cancellation_window_hours': int(get_admin_setting('cancellation_window_hours', 48)),
        },
        'customers': customers,
        'vendors': vendors,
        'bookings': booking_rows,
        'bookings_truncated': Booking.query.count() > len(bookings),
        'disputes': dispute_rows,
        'refunds_due': {
            'count': int(refund_due_count or 0),
            'amount': float(refund_due_amount or 0),
        },
        'analytics': {
            'total_bookings': Booking.query.count(),
            'paid_revenue': total_paid,
            'commission_earned': total_commission,
            'host_payout_due': total_host_payout,
            'subscription_revenue': float(
                db.session.query(
                    db.func.coalesce(db.func.sum(VendorSubscriptionPayment.amount), 0)
                ).filter(VendorSubscriptionPayment.status == 'paid').scalar() or 0
            ),
            'active_subscriptions': sum(
                1 for row in vendors if row['subscription']['is_active']
            ),
            'period_days': period_days,
            'funnel': funnel,
            'traffic_sources': traffic_sources,
            'occupancy_trends': occupancy_trends,
            'property_revenue': property_revenue,
            'price_insights': {
                'tours': summarize_price_rows(tour_price_rows),
                'stays': summarize_price_rows(stay_price_rows),
                'listings': price_rows[:20],
            },
            'by_tour': [{
                'tour': row[0],
                'tour_name': report_tour_names.get(row[0], row[0]),
                'bookings': row[1],
                'paid_revenue': float(row[2] or 0),
                'commission_earned': float(row[3] or 0),
                'host_payout': float(row[4] or 0),
            } for row in report_rows],
        },
    }


@app.route('/api/admin/settings', methods=['PUT'])
@admin_required
def admin_update_settings():
    response = require_admin_csrf()
    if response:
        return response
    payload = json_payload()

    def fee_rate(name, label):
        raw = payload.get(name)
        if raw is None or raw == '':
            raise ValueError(f'{label} is required.')
        value = float(raw)
        if not math.isfinite(value) or not 0 <= value <= 25:
            raise ValueError(f'{label} must be between 0% and 25%.')
        return value

    try:
        host_rate = fee_rate('host_commission_rate', 'Host commission')
        subscriber_rate = fee_rate('subscriber_host_commission_rate', 'Subscriber commission')
        guest_rate = fee_rate('guest_service_fee_rate', 'Guest service fee')
        raw_booking_fee = payload.get('booking_fee')
        if raw_booking_fee is None or raw_booking_fee == '':
            raise ValueError('Booking fee is required.')
        booking_fee = float(raw_booking_fee)
        if not math.isfinite(booking_fee) or not 0 <= booking_fee <= 5000:
            raise ValueError('Booking fee must be between KSh 0 and KSh 5,000.')
        raw_subscription_fee = payload.get('subscription_monthly_fee')
        if raw_subscription_fee is None or raw_subscription_fee == '':
            raise ValueError('Subscription fee is required.')
        subscription_fee = float(raw_subscription_fee)
        if not math.isfinite(subscription_fee) or not 0 <= subscription_fee <= 50000:
            raise ValueError('Subscription fee must be between KSh 0 and KSh 50,000.')
    except (TypeError, ValueError) as exc:
        return {'error': str(exc)}, 400
    if payload.get('refund_policy', 'automatic') != 'automatic':
        return {'error': 'Paid bookings are refunded automatically when they are cancelled.'}, 400
    for key, value in {
        'host_commission_rate': f'{host_rate:g}',
        'subscriber_host_commission_rate': f'{subscriber_rate:g}',
        'guest_service_fee_rate': f'{guest_rate:g}',
        'booking_fee': f'{booking_fee:g}',
        'subscription_monthly_fee': f'{subscription_fee:g}',
        'refund_policy': 'automatic',
        'cancellation_window_hours': '48',
    }.items():
        setting = db.session.get(AdminSetting, key)
        if setting:
            setting.value = value
        else:
            db.session.add(AdminSetting(key=key, value=value))
    db.session.commit()
    return {'settings': {
        'host_commission_rate': host_rate,
        'subscriber_host_commission_rate': subscriber_rate,
        'guest_service_fee_rate': guest_rate,
        'booking_fee': booking_fee,
        'subscription_monthly_fee': subscription_fee,
        'refund_policy': 'automatic',
        'cancellation_window_hours': 48,
    }}


@app.route('/api/admin/users/<string:role>/<int:user_id>/status', methods=['POST'])
@admin_required
def admin_update_user_status(role, user_id):
    response = require_admin_csrf()
    if response:
        return response
    active = json_payload().get('active')
    if not isinstance(active, bool) or role not in {'customer', 'vendor'}:
        return {'error': 'Choose a valid customer or partner account and active status.'}, 400
    model = User if role == 'customer' else VendorAccount
    account = db.session.get(model, user_id)
    if not account:
        return {'error': 'User account not found.'}, 404
    account.is_active = active
    db.session.commit()
    return {'user': {'id': account.id, 'role': role, 'is_active': account.is_active}}


@app.route('/api/admin/bookings/<int:booking_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_booking(booking_id):
    response = require_admin_csrf()
    if response:
        return response
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return {'error': 'Booking not found.'}, 404
    if booking.status not in {'requested', 'confirmed', 'in_preparation'}:
        return {'error': 'Only active bookings can be cancelled.'}, 409
    if booking.payment_status == 'pending':
        return {'error': 'This booking has a pending M-Pesa request. Wait for its payment result before cancelling.'}, 409
    try:
        release_booking_availability(booking)
    except ValueError as exc:
        db.session.rollback()
        return {'error': str(exc)}, 409
    booking.status = 'cancelled'
    if booking.payment_status == 'pending':
        booking.payment_status = 'cancelled'
    refund_queued = queue_cancellation_refund(booking, 'administrator')
    db.session.commit()
    if refund_queued:
        send_refund_notification(booking, paid=False)
    email_sent = send_booking_status_notification(booking)
    return {'booking': booking.to_dict(), 'email_sent': email_sent, 'refund_queued': refund_queued}


@app.route('/api/admin/bookings/<int:booking_id>/refund', methods=['POST'])
@admin_required
def admin_update_refund(booking_id):
    """Move a refund through the manual payout queue."""
    response = require_admin_csrf()
    if response:
        return response
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return {'error': 'Booking not found.'}, 404
    if booking.payment_status != 'paid':
        return {'error': 'Only paid bookings can be refunded.'}, 409
    payload = json_payload()
    status = payload.get('status')
    if status not in REFUND_TRANSITIONS.get(booking.refund_status, set()):
        return {'error': 'That refund status transition is not allowed.'}, 409
    if status == 'pending':
        reason = str(payload.get('reason') or '').strip()
        queue_booking_refund(
            booking,
            reason[:255] or f'Refund requested by the administrator for booking #{booking.id}.',
        )
    elif status == 'paid':
        mark_booking_refund_paid(booking)
    else:
        booking.refund_status = 'rejected'
        booking.refund_paid_at = None
    db.session.commit()
    email_sent = send_refund_notification(booking, paid=status == 'paid')
    return {
        'booking': booking.to_dict(),
        'gateway_refund_issued': False,
        'email_sent': email_sent,
    }


@app.route('/api/admin/bookings/<int:booking_id>/disputes', methods=['POST'])
@admin_required
def admin_open_booking_dispute(booking_id):
    response = require_admin_csrf()
    if response:
        return response
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return {'error': 'Booking not found.'}, 404
    reason = str(json_payload().get('reason', '')).strip()
    if len(reason) < 10 or len(reason) > 3000:
        return {'error': 'Enter a dispute summary between 10 and 3,000 characters.'}, 400
    dispute = BookingDispute(booking_id=booking.id, reason=reason)
    db.session.add(dispute)
    db.session.commit()
    return {'dispute': dispute.to_dict()}, 201


@app.route('/api/admin/disputes/<int:dispute_id>', methods=['PUT'])
@admin_required
def admin_resolve_dispute(dispute_id):
    response = require_admin_csrf()
    if response:
        return response
    dispute = db.session.get(BookingDispute, dispute_id)
    if not dispute:
        return {'error': 'Dispute not found.'}, 404
    if dispute.status != 'open':
        return {'error': 'This dispute has already been resolved.'}, 409
    resolution = str(json_payload().get('resolution', '')).strip()
    if len(resolution) < 10 or len(resolution) > 3000:
        return {'error': 'Enter a resolution between 10 and 3,000 characters.'}, 400
    dispute.status = 'resolved'
    dispute.resolution = resolution
    dispute.resolved_at = datetime.utcnow()
    db.session.commit()
    return {'dispute': dispute.to_dict()}


def json_payload():
    """Return the JSON request body as a dict, or an empty dict when it is not an object."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def apply_values(instance, values):
    """Copy validated payload values onto a model instance and persist them."""
    for field, value in values.items():
        setattr(instance, field, value)
    db.session.commit()
    return instance


BOOKED_TOUR_DELETE_ERROR = 'A tour with booked departures cannot be deleted. Cancel or complete its bookings first.'


def delete_tour(tour) -> bool:
    """Delete a tour with its departures and reviews; returns False when a departure is booked."""
    schedules = TourSchedule.query.filter_by(tour_slug=tour.slug).all()
    if any(schedule.booked_count for schedule in schedules):
        return False
    for schedule in schedules:
        db.session.delete(schedule)
    Review.query.filter_by(target_type='tour', target_id=tour.slug).delete()
    Promotion.query.filter_by(listing_type='tour', listing_slug=tour.slug).delete()
    db.session.delete(tour)
    db.session.commit()
    return True


def delete_property(listing):
    """Delete a property listing together with its rooms, availability and reviews."""
    room_ids = [room.id for room in PropertyRoom.query.filter_by(property_id=listing.id).all()]
    if room_ids:
        PropertyAvailability.query.filter(PropertyAvailability.room_id.in_(room_ids)).delete(synchronize_session=False)
        PropertyRoom.query.filter(PropertyRoom.property_id == listing.id).delete(synchronize_session=False)
    Review.query.filter_by(target_type='property', target_id=listing.slug).delete()
    Promotion.query.filter_by(listing_type='property', listing_slug=listing.slug).delete()
    db.session.delete(listing)
    db.session.commit()


PHONE_PATTERN = re.compile(r'^\+?[0-9][0-9\s\-()]{6,19}$')


def text_lines_value(value, label, *, max_items=20, max_length=200):
    """Normalise a list or one-item-per-line field into stored newline text."""
    if isinstance(value, list):
        items = [str(item).strip() for item in value]
    elif value in (None, ''):
        items = []
    elif isinstance(value, str):
        items = [item.strip() for item in value.splitlines()]
    else:
        raise ValueError(f'{label} must be a list or one item per line.')
    items = list(dict.fromkeys(item for item in items if item))
    if len(items) > max_items:
        raise ValueError(f'Add at most {max_items} entries to {label.lower()}.')
    if any(len(item) > max_length for item in items):
        raise ValueError(f'Each entry in {label.lower()} must be {max_length} characters or fewer.')
    return '\n'.join(items)


def tag_list_value(value, label, *, max_items=12, max_length=40):
    """Normalise a comma-, semicolon- or line-separated tag field."""
    if isinstance(value, list):
        items = [str(item).strip() for item in value]
    elif value in (None, ''):
        items = []
    elif isinstance(value, str):
        items = [item.strip() for item in re.split(r'[,;\n]+', value)]
    else:
        raise ValueError(f'{label} must be a list or separated text.')
    items = list(dict.fromkeys(item for item in items if item))
    if len(items) > max_items:
        raise ValueError(f'Add at most {max_items} entries to {label.lower()}.')
    if any(len(item) > max_length for item in items):
        raise ValueError(f'Each entry in {label.lower()} must be {max_length} characters or fewer.')
    return '\n'.join(items)


def boolean_value(value, default=True):
    if value is None or value == '':
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on', 'active', 'visible'}


def destination_value(value):
    """Resolve a destination slug so listings only point at known places."""
    destination = str(value or 'lamu').strip().lower()
    if not db.session.get(Destination, destination):
        raise ValueError('Choose one of the listed destinations.')
    return destination


def tour_values(data):
    name = str(data.get('name', '')).strip()
    description = str(data.get('description', '')).strip()
    duration = str(data.get('duration', '')).strip()
    category = str(data.get('category', 'Experiences')).strip()
    itinerary = data.get('itinerary', '')
    inclusions = data.get('inclusions', '')
    exclusions = data.get('exclusions', '')
    itinerary = text_lines_value(itinerary, 'Itinerary', max_items=20, max_length=300)
    inclusions = text_lines_value(inclusions, "What's included", max_items=20, max_length=200)
    exclusions = text_lines_value(exclusions, "What's not included", max_items=20, max_length=200)
    languages = tag_list_value(data.get('languages'), 'Languages', max_items=12, max_length=40)
    pickup_point = str(data.get('pickup_point', 'Confirm with your operator')).strip()
    tour_type = str(data.get('tour_type') or 'experience').strip().lower()
    group_type = str(data.get('group_type') or 'private').strip().lower()
    raw_days = data.get('duration_days')
    if raw_days in (None, ''):
        day_match = re.search(r'(\d+)\s*day', duration, re.IGNORECASE)
        raw_days = day_match.group(1) if day_match else 1
    try:
        price = int(data.get('price', 0))
        min_group_size = int(data.get('min_group_size', 1))
        max_group_size = int(data.get('max_group_size', 12))
        duration_days = int(raw_days)
        image_url = safe_image_url(data.get('image_url'))
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc) or 'Price must be a positive whole number.') from exc
    if not name or not description or not duration or not category or not pickup_point or price < 1:
        raise ValueError('Name, category, description, duration, pickup point, and a positive price are required.')
    if min_group_size < 1 or max_group_size < min_group_size:
        raise ValueError('Group sizes must be positive and maximum size cannot be below minimum size.')
    if tour_type not in TOUR_TYPES:
        raise ValueError('Choose a valid tour style.')
    if group_type not in TOUR_GROUP_TYPES:
        raise ValueError('Choose whether the tour runs as a private or shared group.')
    if duration_days < 1 or duration_days > 60:
        raise ValueError('Tour length must be between 1 and 60 days.')
    return {
        'name': name,
        'description': description,
        'duration': duration,
        'price': price,
        'category': category,
        'itinerary': itinerary,
        'inclusions': inclusions,
        'exclusions': exclusions,
        'pickup_point': pickup_point,
        'min_group_size': min_group_size,
        'max_group_size': max_group_size,
        'destination': destination_value(data.get('destination')),
        'tour_type': tour_type,
        'duration_days': duration_days,
        'languages': languages,
        'group_type': group_type,
        'image_url': image_url,
    }


def vendor_profile_values(data):
    """Validate the public business profile a supplier shows to travellers."""
    name = str(data.get('name', '')).strip()
    if not name or len(name) > 100:
        raise ValueError('Enter a business name of 100 characters or fewer.')
    raw_types = data.get('business_types', '')
    if isinstance(raw_types, list):
        selected = [str(item).strip().lower() for item in raw_types]
    elif isinstance(raw_types, str):
        selected = [item.strip().lower() for item in re.split(r'[,;\n]+', raw_types)]
    else:
        raise ValueError('Choose your business types from the available options.')
    selected_set = set(selected)
    business_types = [key for key in VENDOR_BUSINESS_TYPES if key in selected_set]
    if not business_types:
        raise ValueError('Choose at least one business type, such as safari operator or tour operator.')
    description = str(data.get('description', '')).strip()
    if len(description) > 2000:
        raise ValueError('Business descriptions must be under 2,000 characters.')
    location = str(data.get('location', '')).strip()
    if len(location) > 120:
        raise ValueError('Locations must be 120 characters or fewer.')
    phone = re.sub(r'\s+', ' ', str(data.get('phone', '')).strip())
    if phone and not PHONE_PATTERN.fullmatch(phone):
        raise ValueError('Enter a phone number travellers can call or message.')
    website = str(data.get('website', '')).strip()
    if website and (len(website) > 255 or not website.startswith(('https://', 'http://'))):
        raise ValueError('Websites must start with http:// or https:// and be 255 characters or fewer.')
    return {
        'name': name,
        'business_types': ','.join(business_types),
        'description': description,
        'location': location,
        'phone': phone,
        'website': website,
        'logo_url': safe_image_url(data.get('logo_url')),
    }


def service_values(data):
    """Validate an enquiry-only service listing such as a transfer or guide."""
    name = str(data.get('name', '')).strip()
    service_type = str(data.get('service_type') or '').strip().lower()
    description = str(data.get('description', '')).strip()
    price_unit = str(data.get('price_unit') or 'per person').strip().lower()
    location = str(data.get('location', '')).strip()
    coverage = text_lines_value(data.get('coverage'), 'Service coverage', max_items=20, max_length=120)
    inclusions = text_lines_value(data.get('inclusions'), 'Inclusions', max_items=20, max_length=200)
    try:
        price_from = int(data.get('price_from', 0))
        image_url = safe_image_url(data.get('image_url'))
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc) or 'Enter a starting price in whole shillings.') from exc
    if not name or len(name) > 150:
        raise ValueError('Enter a service name of 150 characters or fewer.')
    if service_type not in SERVICE_TYPES:
        raise ValueError('Choose a valid service type.')
    if not description:
        raise ValueError('Describe what the service includes.')
    if len(description) > 2000:
        raise ValueError('Service descriptions must be under 2,000 characters.')
    if price_from < 1:
        raise ValueError('Enter a starting price of at least 1.')
    if price_unit not in SERVICE_PRICE_UNITS:
        raise ValueError('Choose how the service is priced.')
    if not location or len(location) > 120:
        raise ValueError('Enter the location where travellers can use this service.')
    return {
        'name': name,
        'service_type': service_type,
        'description': description,
        'price_from': price_from,
        'price_unit': price_unit,
        'location': location,
        'destination': destination_value(data.get('destination')),
        'coverage': coverage,
        'inclusions': inclusions,
        'image_url': image_url,
        'is_active': boolean_value(data.get('is_active')),
    }


def coordinate_pair(data):
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    if latitude in (None, '') and longitude in (None, ''):
        return None, None
    if latitude in (None, '') or longitude in (None, ''):
        raise ValueError('Enter both latitude and longitude, or leave both blank.')
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValueError('Latitude and longitude must be valid numbers.') from exc
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError('Latitude or longitude is outside the valid range.')
    return latitude, longitude


def property_values(data):
    name = str(data.get('name', '')).strip()
    property_type = normalize_property_type(data.get('property_type'))
    location = str(data.get('location', '')).strip()
    description = str(data.get('description', '')).strip()
    raw_amenities = data.get('amenities', '')
    if isinstance(raw_amenities, list):
        amenities = [str(item).strip() for item in raw_amenities if str(item).strip()]
    elif isinstance(raw_amenities, str):
        amenities = [item.strip() for item in raw_amenities.splitlines() if item.strip()]
    else:
        raise ValueError('Amenities must be a list or one item per line.')
    amenities = list(dict.fromkeys(amenities))
    if any(len(item) > 80 for item in amenities) or sum(map(len, amenities)) > 1500:
        raise ValueError('Each amenity must be 80 characters or fewer and total amenities must be under 1,500 characters.')
    try:
        price = int(data.get('price_per_night', 0))
        guests = int(data.get('guests', 0))
        image_url = safe_image_url(data.get('image_url'))
        latitude, longitude = coordinate_pair(data)
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc) or 'Price and guest capacity must be positive whole numbers.') from exc
    if not name or not location or not description or property_type not in PROPERTY_TYPES or price < 1 or guests < 1:
        raise ValueError('Complete all property fields with a valid type, price, and guest capacity.')
    return {
        'name': name,
        'property_type': property_type,
        'location': location,
        'description': description,
        'amenities': '\n'.join(amenities),
        'latitude': latitude,
        'longitude': longitude,
        'price_per_night': price,
        'guests': guests,
        'image_url': image_url,
    }


def destination_values(data):
    name = str(data.get('name', '')).strip()
    description = str(data.get('description', '')).strip()
    search_location = str(data.get('search_location', '')).strip()
    site_type = str(data.get('site_type', 'area')).strip().lower()
    try:
        image_url = safe_image_url(data.get('image_url'))
        latitude, longitude = coordinate_pair(data)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if not name or not description or not search_location:
        raise ValueError('Name, description, and search location are required.')
    if site_type not in {'area', 'beach', 'heritage'}:
        raise ValueError('Choose an area, beach, or heritage site type.')
    return {
        'name': name,
        'description': description,
        'search_location': search_location,
        'site_type': site_type,
        'image_url': image_url,
        'latitude': latitude,
        'longitude': longitude,
    }


@app.route('/api/admin/tours', methods=['POST'])
@admin_required
def admin_create_tour():
    response = require_admin_csrf()
    if response:
        return response
    data = json_payload()
    try:
        values = tour_values(data)
    except (TypeError, ValueError) as exc:
        return {'error': str(exc)}, 400
    slug = unique_slug(str(data.get('slug') or values['name']), Tour)
    tour = Tour(slug=slug, **values)
    db.session.add(tour)
    db.session.commit()
    return {'tour': tour.to_dict()}, 201


@app.route('/api/admin/tours/<string:slug>', methods=['PUT', 'DELETE'])
@admin_required
def admin_update_tour(slug):
    response = require_admin_csrf()
    if response:
        return response
    tour = db.session.get(Tour, slug)
    if not tour:
        return {'error': 'Tour not found.'}, 404
    if request.method == 'DELETE':
        if not delete_tour(tour):
            return {'error': BOOKED_TOUR_DELETE_ERROR}, 409
        return '', 204

    data = json_payload()
    try:
        values = tour_values(data)
    except (TypeError, ValueError) as exc:
        return {'error': str(exc)}, 400
    apply_values(tour, values)
    return {'tour': tour.to_dict()}


@app.route('/api/admin/services', methods=['POST'])
@admin_required
def admin_create_service():
    response = require_admin_csrf()
    if response:
        return response
    data = json_payload()
    vendor_id = data.get('vendor_id')
    if vendor_id not in (None, ''):
        try:
            vendor_id = int(vendor_id)
        except (TypeError, ValueError):
            return {'error': 'Choose a valid partner account.'}, 400
        if not db.session.get(VendorAccount, vendor_id):
            return {'error': 'Partner account not found.'}, 400
    else:
        vendor_id = None
    try:
        values = service_values(data)
    except ValueError as exc:
        return {'error': str(exc)}, 400
    slug = unique_slug(str(data.get('slug') or values['name']), Service)
    service = Service(slug=slug, vendor_id=vendor_id, **values)
    db.session.add(service)
    db.session.commit()
    return {'service': service.to_dict()}, 201


@app.route('/api/admin/services/<string:slug>', methods=['PUT', 'DELETE'])
@admin_required
def admin_update_service(slug):
    response = require_admin_csrf()
    if response:
        return response
    service = Service.query.filter_by(slug=slug).first()
    if not service:
        return {'error': 'Service not found.'}, 404
    if request.method == 'DELETE':
        db.session.delete(service)
        db.session.commit()
        return '', 204
    try:
        values = service_values(json_payload())
    except ValueError as exc:
        return {'error': str(exc)}, 400
    apply_values(service, values)
    return {'service': service.to_dict()}


@app.route('/api/admin/properties', methods=['POST'])
@admin_required
def admin_create_property():
    response = require_admin_csrf()
    if response:
        return response
    data = json_payload()
    try:
        values = property_values(data)
    except (TypeError, ValueError) as exc:
        return {'error': str(exc)}, 400
    slug = unique_slug(str(data.get('slug') or values['name']), Property)
    admin = db.session.get(AdminAccount, session['admin_id'])
    if admin is None:
        return {'error': 'Admin sign-in is required.'}, 401
    listing = Property(
        slug=slug,
        owner_name=admin.name,
        owner_email=admin.email,
        **values,
    )
    db.session.add(listing)
    db.session.commit()
    return {'property': listing.to_dict()}, 201


@app.route('/api/admin/properties/<int:property_id>', methods=['PUT', 'DELETE'])
@admin_required
def admin_update_property(property_id):
    response = require_admin_csrf()
    if response:
        return response
    listing = db.session.get(Property, property_id)
    if not listing:
        return {'error': 'Property not found.'}, 404
    if request.method == 'DELETE':
        delete_property(listing)
        return '', 204

    data = json_payload()
    try:
        values = property_values(data)
    except (TypeError, ValueError) as exc:
        return {'error': str(exc)}, 400
    apply_values(listing, values)
    return {'property': listing.to_dict()}


def parse_promotion_date(value, label):
    """Read an ISO date from the admin form, with a message a person can act on."""
    try:
        return date.fromisoformat(str(value or '').strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Choose a valid {label} date.') from exc


@app.route('/api/admin/promotions', methods=['POST'])
@admin_required
def admin_save_promotion():
    """Start or edit the single campaign a listing can run at a time."""
    response = require_admin_csrf()
    if response:
        return response
    data = json_payload()
    listing_type = str(data.get('listing_type') or '').strip()
    if listing_type not in PROMOTION_LISTING_TYPES:
        return {'error': 'Choose whether the promotion is for an experience or a place to stay.'}, 400
    listing_slug = str(data.get('listing_slug') or '').strip()
    listing = (
        db.session.get(Tour, listing_slug) if listing_type == 'tour'
        else Property.query.filter_by(slug=listing_slug).first()
    )
    if not listing:
        return {'error': 'Choose a published listing with a public page.'}, 400
    tier = str(data.get('tier') or '').strip()
    if tier not in PROMOTION_TIERS:
        return {'error': 'Choose a promotion tier.'}, 400
    headline = str(data.get('headline') or '').strip()
    if len(headline) > 140:
        return {'error': 'Keep the headline under 140 characters.'}, 400
    try:
        starts_on = parse_promotion_date(data.get('starts_on'), 'start')
        ends_on = parse_promotion_date(data.get('ends_on'), 'end')
    except ValueError as exc:
        return {'error': str(exc)}, 400
    if ends_on < starts_on:
        return {'error': 'The promotion must end on or after it starts.'}, 400

    promotion = Promotion.query.filter_by(listing_type=listing_type, listing_slug=listing_slug).first()
    created = promotion is None
    today = datetime.now(KENYA_TIMEZONE).date()
    live_elsewhere = Promotion.query.filter(
        Promotion.starts_on <= today,
        Promotion.ends_on >= today,
        Promotion.id != (promotion.id if promotion else 0),
    ).count()
    if starts_on <= today <= ends_on and live_elsewhere >= PROMOTION_MAX_ACTIVE:
        return {
            'error': f'Up to {PROMOTION_MAX_ACTIVE} promotions can run at once. Pause one before starting another.'
        }, 400
    if created:
        promotion = Promotion(
            listing_type=listing_type,
            listing_slug=listing_slug,
            impressions=0,
            clicks=0,
        )
        db.session.add(promotion)
    promotion.tier = tier
    promotion.headline = headline
    promotion.starts_on = starts_on
    promotion.ends_on = ends_on
    db.session.commit()
    return {
        'promotion': {**promotion.to_dict(), 'listing_name': listing.name},
    }, 201 if created else 200


@app.route('/api/admin/promotions/<int:promotion_id>', methods=['DELETE'])
@admin_required
def admin_delete_promotion(promotion_id):
    """End a campaign immediately; the listing returns to organic ranking."""
    response = require_admin_csrf()
    if response:
        return response
    promotion = db.session.get(Promotion, promotion_id)
    if not promotion:
        return {'error': 'Promotion not found.'}, 404
    db.session.delete(promotion)
    db.session.commit()
    return '', 204


@app.route('/api/admin/destinations', methods=['POST'])
@admin_required
def admin_create_destination():
    response = require_admin_csrf()
    if response:
        return response
    data = json_payload()
    try:
        values = destination_values(data)
    except ValueError as exc:
        return {'error': str(exc)}, 400
    slug = unique_slug(str(data.get('slug') or values['name']), Destination)
    destination = Destination(slug=slug, **values)
    db.session.add(destination)
    db.session.commit()
    return {'destination': destination.to_dict()}, 201


@app.route('/api/admin/destinations/<string:slug>', methods=['PUT', 'DELETE'])
@admin_required
def admin_update_destination(slug):
    response = require_admin_csrf()
    if response:
        return response
    destination = db.session.get(Destination, slug)
    if not destination:
        return {'error': 'Destination not found.'}, 404
    if request.method == 'DELETE':
        db.session.delete(destination)
        db.session.commit()
        return '', 204
    data = json_payload()
    try:
        values = destination_values(data)
    except ValueError as exc:
        return {'error': str(exc)}, 400
    apply_values(destination, values)
    return {'destination': destination.to_dict()}


@app.route('/api/admin/admins', methods=['POST'])
@admin_required
def admin_create_account():
    response = require_admin_csrf()
    if response:
        return response
    data = json_payload()
    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    password = data.get('password', '')
    if not name or '@' not in email or not isinstance(password, str) or len(password) < 12:
        return {'error': 'Enter a name, valid email, and a password of at least 12 characters.'}, 400
    if AdminAccount.query.filter_by(email=email).first():
        return {'error': 'An admin account with that email already exists.'}, 409
    admin = AdminAccount(name=name, email=email, password_hash=generate_password_hash(password))
    db.session.add(admin)
    db.session.commit()
    return {'admin': {'id': admin.id, 'name': admin.name, 'email': admin.email}}, 201


@app.route('/api/admin/admins/<int:admin_id>', methods=['DELETE'])
@admin_required
def admin_delete_account(admin_id):
    response = require_admin_csrf()
    if response:
        return response
    admin = db.session.get(AdminAccount, admin_id)
    if not admin:
        return {'error': 'Admin account not found.'}, 404
    if admin.id == session.get('admin_id'):
        return {'error': 'You cannot delete the account you are currently using.'}, 400
    if AdminAccount.query.count() <= 1:
        return {'error': 'At least one admin account must remain.'}, 400
    db.session.delete(admin)
    db.session.commit()
    return '', 204


@app.route('/api/admin/vendors/<int:vendor_id>', methods=['DELETE'])
@admin_required
def admin_delete_vendor(vendor_id):
    response = require_admin_csrf()
    if response:
        return response
    vendor = db.session.get(VendorAccount, vendor_id)
    if not vendor:
        return {'error': 'Partner account not found.'}, 404
    tours = Tour.query.filter_by(vendor_id=vendor.id).all()
    properties = Property.query.filter_by(vendor_id=vendor.id).all()
    for tour in tours:
        schedules = TourSchedule.query.filter_by(tour_slug=tour.slug).all()
        if any(schedule.booked_count for schedule in schedules):
            return {'error': 'Cancel or complete this partner’s scheduled bookings before removing the account.'}, 409
        for schedule in schedules:
            db.session.delete(schedule)
        Review.query.filter_by(target_type='tour', target_id=tour.slug).delete()
        db.session.delete(tour)
    for listing in properties:
        Review.query.filter_by(target_type='property', target_id=listing.slug).delete()
        db.session.delete(listing)
    db.session.delete(vendor)
    db.session.commit()
    return '', 204


def availability_payload(data, tour=None):
    tour_slug = tour.slug if tour else str(data.get('tour_slug', '')).strip()
    if not db.session.get(Tour, tour_slug):
        raise ValueError('Choose a valid tour.')
    try:
        starts_at = parse_local_datetime(data.get('starts_at'))
        capacity = int(data.get('capacity', 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc) or 'Enter a valid departure date, time, and capacity.') from exc
    if starts_at <= datetime.now(KENYA_TIMEZONE).replace(tzinfo=None) or capacity < 1:
        raise ValueError('Departure must be in the future and capacity must be positive.')
    return {'tour_slug': tour_slug, 'starts_at': starts_at, 'capacity': capacity}


def manage_availability(scope):
    if request.method == 'GET':
        query = TourSchedule.query
        if scope:
            query = query.join(Tour, Tour.slug == TourSchedule.tour_slug).filter(Tour.vendor_id == scope)
        return {'schedules': [item.to_dict() for item in query.order_by(TourSchedule.starts_at).all()]}

    response = require_admin_csrf() if scope is None else require_vendor_csrf()
    if response:
        return response
    data = json_payload()
    if request.method == 'POST':
        try:
            values = availability_payload(data)
        except ValueError as exc:
            return {'error': str(exc)}, 400
        if scope is not None:
            owned_tour = Tour.query.filter_by(slug=values['tour_slug'], vendor_id=scope).first()
            if not owned_tour:
                return {'error': 'You can only schedule your own tours.'}, 404
        schedule = TourSchedule(**values)
        db.session.add(schedule)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {'error': 'A departure for this tour at that time already exists.'}, 409
        return {'schedule': schedule.to_dict()}, 201

    view_args = request.view_args or {}
    schedule_id = view_args.get('schedule_id')
    if schedule_id is None:
        return {'error': 'Availability slot not found.'}, 404
    query = TourSchedule.query.filter_by(id=schedule_id)
    if scope is not None:
        query = query.join(Tour, Tour.slug == TourSchedule.tour_slug).filter(Tour.vendor_id == scope)
    schedule = query.first()
    if not schedule:
        return {'error': 'Availability slot not found.'}, 404

    if request.method == 'DELETE':
        if schedule.booked_count:
            return {'error': 'A departure with bookings cannot be deleted. Cancel or complete its bookings first.'}, 409
        db.session.delete(schedule)
        db.session.commit()
        return '', 204

    try:
        capacity = int(data.get('capacity', schedule.capacity))
        starts_at = parse_local_datetime(data.get('starts_at', schedule.starts_at.isoformat()))
    except (TypeError, ValueError) as exc:
        return {'error': str(exc) or 'Enter a valid departure date, time, and capacity.'}, 400
    if capacity < schedule.booked_count or starts_at <= datetime.now(KENYA_TIMEZONE).replace(tzinfo=None):
        return {'error': 'Capacity cannot be below booked guests and departure must remain in the future.'}, 400
    schedule.capacity = capacity
    schedule.starts_at = starts_at
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {'error': 'A departure for this tour at that time already exists.'}, 409
    return {'schedule': schedule.to_dict()}


@app.route('/api/admin/availability', methods=['GET', 'POST'])
@admin_required
def admin_availability():
    return manage_availability(None)


@app.route('/api/admin/availability/<int:schedule_id>', methods=['PUT', 'DELETE'])
@admin_required
def admin_availability_item(schedule_id):
    return manage_availability(None)


@app.route('/api/vendor/availability', methods=['GET', 'POST'])
@vendor_required
def vendor_availability():
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    return manage_availability(vendor.id)


@app.route('/api/vendor/availability/<int:schedule_id>', methods=['PUT', 'DELETE'])
@vendor_required
def vendor_availability_item(schedule_id):
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    return manage_availability(vendor.id)


def room_values(data):
    name = str(data.get('name', '')).strip()
    description = str(data.get('description', '')).strip()
    try:
        guests = int(data.get('guests', 0))
        base_rate = int(data.get('base_rate', 0))
        total_units = int(data.get('total_units', 1))
        image_url = safe_image_url(data.get('image_url'))
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc) or 'Enter valid guest capacity, nightly rate and unit count.') from exc
    if not name:
        raise ValueError('Enter a room name.')
    if len(name) > 120:
        raise ValueError('Room names must be 120 characters or fewer.')
    if len(description) > 2000:
        raise ValueError('Room descriptions must be under 2,000 characters.')
    if guests < 1 or guests > 50:
        raise ValueError('Guest capacity per room must be between 1 and 50.')
    if base_rate < 1:
        raise ValueError('Enter a nightly rate of at least 1.')
    if total_units < 1 or total_units > 500:
        raise ValueError('Room units must be between 1 and 500.')
    return {
        'name': name,
        'description': description,
        'guests': guests,
        'base_rate': base_rate,
        'total_units': total_units,
        'image_url': image_url,
    }


def scoped_property(scope, property_id):
    """Resolve a property the current vendor (or any admin) may manage."""
    listing = db.session.get(Property, property_id)
    if listing is None or (scope is not None and listing.vendor_id != scope):
        return None, ({'error': 'Property not found.'}, 404)
    return listing, None


def scoped_room(scope, property_id, room_id):
    listing, error = scoped_property(scope, property_id)
    if error:
        return None, None, error
    room = PropertyRoom.query.filter_by(id=room_id, property_id=listing.id).first()
    if room is None:
        return None, None, ({'error': 'Room not found.'}, 404)
    return room, listing, None


def manage_property_rooms(scope, property_id):
    if request.method == 'GET':
        listing, error = scoped_property(scope, property_id)
        if error:
            return error
        rooms = PropertyRoom.query.filter_by(property_id=listing.id).order_by(
            PropertyRoom.base_rate, PropertyRoom.id
        ).all()
        return {'property': listing.to_dict(), 'rooms': [room.to_dict() for room in rooms]}

    response = require_admin_csrf() if scope is None else require_vendor_csrf()
    if response:
        return response
    listing, error = scoped_property(scope, property_id)
    if error:
        return error
    try:
        values = room_values(json_payload())
    except ValueError as exc:
        return {'error': str(exc)}, 400
    room = PropertyRoom(property_id=listing.id, **values)
    db.session.add(room)
    db.session.commit()
    return {'room': room.to_dict()}, 201


def manage_property_room(scope, property_id, room_id):
    room, listing, error = scoped_room(scope, property_id, room_id)
    if error:
        return error
    if request.method == 'GET':
        return {'room': room.to_dict()}

    response = require_admin_csrf() if scope is None else require_vendor_csrf()
    if response:
        return response
    if request.method == 'DELETE':
        open_booking = Booking.query.filter(
            Booking.room_id == room.id,
            Booking.status.in_(('requested', 'confirmed', 'in_preparation')),
        ).first()
        if open_booking:
            return {'error': 'This room has open bookings. Cancel or complete them before deleting it.'}, 409
        PropertyAvailability.query.filter_by(room_id=room.id).delete()
        db.session.delete(room)
        db.session.commit()
        return '', 204

    data = json_payload()
    try:
        values = room_values({
            'name': data.get('name', room.name),
            'description': data.get('description', room.description),
            'guests': data.get('guests', room.guests),
            'base_rate': data.get('base_rate', room.base_rate),
            'total_units': data.get('total_units', room.total_units),
            'image_url': data.get('image_url', room.image_url or ''),
        })
    except ValueError as exc:
        return {'error': str(exc)}, 400
    reserved = db.session.query(db.func.max(PropertyAvailability.reserved_count)).filter(
        PropertyAvailability.room_id == room.id
    ).scalar() or 0
    if values['total_units'] < int(reserved):
        return {'error': 'Units cannot be below the nights already booked in this room.'}, 409
    for field, value in values.items():
        setattr(room, field, value)
    if 'is_active' in data:
        room.is_active = bool(data.get('is_active'))
    db.session.commit()
    return {'room': room.to_dict()}


def manage_room_availability(scope, property_id, room_id):
    room, listing, error = scoped_room(scope, property_id, room_id)
    if error:
        return error
    if request.method == 'GET':
        today = datetime.now(KENYA_TIMEZONE).date()
        start = request.args.get('from') or today.isoformat()
        end = request.args.get('to') or (today + timedelta(days=60)).isoformat()
        try:
            calendar = room_calendar(room, start, end)
        except ValueError as exc:
            return {'error': str(exc)}, 400
        return {'room': room.to_dict(), 'calendar': calendar}

    response = require_admin_csrf() if scope is None else require_vendor_csrf()
    if response:
        return response

    if request.method == 'DELETE':
        payload = request.get_json(silent=True) or {}
        day = request.args.get('date') or payload.get('date')
        try:
            clear_availability_day(room, day)
        except ValueError as exc:
            return {'error': str(exc)}, 400
        db.session.commit()
        return '', 204

    data = json_payload()
    start = data.get('from') or data.get('start') or request.args.get('from')
    end = data.get('to') or data.get('end') or start
    options = {}
    for key in ('rate', 'units_available'):
        if key in data:
            options[key] = data.get(key)
    if 'is_closed' in data:
        options['is_closed'] = data.get('is_closed') in (True, 1, '1', 'true', 'True', 'on')
    if not options:
        return {'error': 'Set a nightly rate, unit count or closure for the range.'}, 400
    try:
        update_availability_range(room, start, end, **options)
    except ValueError as exc:
        db.session.rollback()
        return {'error': str(exc)}, 400
    db.session.commit()
    try:
        calendar = room_calendar(room, start, end)
    except ValueError:
        calendar = []
    return {'room': room.to_dict(), 'calendar': calendar}


@app.route('/api/admin/properties/<int:property_id>/rooms', methods=['GET', 'POST'])
@admin_required
def admin_property_rooms(property_id):
    return manage_property_rooms(None, property_id)


@app.route('/api/admin/properties/<int:property_id>/rooms/<int:room_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def admin_property_room(property_id, room_id):
    return manage_property_room(None, property_id, room_id)


@app.route('/api/admin/properties/<int:property_id>/rooms/<int:room_id>/availability', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def admin_property_room_availability(property_id, room_id):
    return manage_room_availability(None, property_id, room_id)


@app.route('/api/vendor/properties/<int:property_id>/rooms', methods=['GET', 'POST'])
@vendor_required
def vendor_property_rooms(property_id):
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    return manage_property_rooms(vendor.id, property_id)


@app.route('/api/vendor/properties/<int:property_id>/rooms/<int:room_id>', methods=['GET', 'PUT', 'DELETE'])
@vendor_required
def vendor_property_room(property_id, room_id):
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    return manage_property_room(vendor.id, property_id, room_id)


@app.route('/api/vendor/properties/<int:property_id>/rooms/<int:room_id>/availability', methods=['GET', 'PUT', 'DELETE'])
@vendor_required
def vendor_property_room_availability(property_id, room_id):
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    return manage_room_availability(vendor.id, property_id, room_id)


def save_catalog_image(owner_folder):
    if os.environ.get('VERCEL') == '1' or (IS_PRODUCTION and not os.environ.get('UPLOAD_DIR')):
        return {
            'error': 'Configure persistent image storage before enabling uploads in production.'
        }, 503

    uploaded = request.files.get('image')
    if not uploaded or not uploaded.filename:
        return {'error': 'Choose an image file to upload.'}, 400
    safe_name = secure_filename(uploaded.filename)
    extension = os.path.splitext(safe_name)[1].lower()
    signatures = {
        '.jpg': lambda header: header.startswith(b'\xff\xd8\xff'),
        '.jpeg': lambda header: header.startswith(b'\xff\xd8\xff'),
        '.png': lambda header: header.startswith(b'\x89PNG\r\n\x1a\n'),
        '.webp': lambda header: header.startswith(b'RIFF') and header[8:12] == b'WEBP',
    }
    signature_matches = signatures.get(extension)
    header = uploaded.stream.read(16)
    uploaded.stream.seek(0)
    if not signature_matches or not signature_matches(header):
        return {'error': 'Upload a valid JPEG, PNG, or WebP image.'}, 400
    filename = f'{uuid.uuid4().hex}{extension}'
    relative_path = os.path.join('uploads', owner_folder, filename)
    destination = os.path.join(UPLOAD_DIR, owner_folder, filename)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    uploaded.save(destination)
    return {'image_url': relative_path.replace(os.sep, '/')}, 201


@app.route('/api/admin/uploads', methods=['POST'])
@admin_required
def admin_upload_image():
    response = require_admin_csrf()
    if response:
        return response
    return save_catalog_image('admin')


@app.route('/api/vendor/uploads', methods=['POST'])
@vendor_required
def vendor_upload_image():
    response = require_vendor_csrf()
    if response:
        return response
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    return save_catalog_image(f'vendors/{vendor.id}')


@app.route('/api/tours/<string:tour_slug>/availability', methods=['GET'])
def public_tour_availability(tour_slug):
    tour = db.session.get(Tour, tour_slug)
    if not tour:
        return {'error': 'Tour not found.'}, 404
    now = datetime.now(KENYA_TIMEZONE).replace(tzinfo=None)
    schedules = TourSchedule.query.filter(
        TourSchedule.tour_slug == tour.slug,
        TourSchedule.is_active.is_(True),
        TourSchedule.starts_at >= now,
        TourSchedule.booked_count < TourSchedule.capacity,
    ).order_by(TourSchedule.starts_at).limit(180).all()
    return {'schedules': [item.to_dict() for item in schedules]}


@app.route('/api/properties/<string:property_slug>/availability', methods=['GET'])
def public_property_availability(property_slug):
    property_listing = Property.query.filter_by(slug=property_slug).first()
    if property_listing is None:
        return {'error': 'Accommodation not found.'}, 404
    try:
        start, end, nights = stay_nights(request.args.get('check_in', ''), request.args.get('check_out', ''))
    except ValueError as exc:
        return {'error': str(exc)}, 400
    try:
        guest_count = max(1, int(request.args.get('guests', 1)))
    except (TypeError, ValueError):
        return {'error': 'Choose a valid guest count.'}, 400

    rooms = PropertyRoom.query.filter_by(
        property_id=property_listing.id, is_active=True
    ).order_by(PropertyRoom.base_rate, PropertyRoom.id).all()
    options = []
    for room in rooms:
        try:
            quote = stay_option(room, start.isoformat(), end.isoformat())
        except ValueError:
            continue
        options.append({
            'id': room.id,
            'name': room.name,
            'description': room.description or '',
            'guests': int(room.guests),
            'image_url': room.image_url,
            'rate': quote['nightly'][0]['rate'] if quote['nightly'] else int(room.base_rate),
            'total': quote['total'],
            'remaining': quote['remaining'],
            'is_available': bool(quote['is_available'] and guest_count <= int(room.guests)),
            'nightly': quote['nightly'],
        })
    return {
        'property': {
            **property_listing.to_dict(),
            **review_ratings('property', [property_listing.slug]).get(
                property_listing.slug, {'rating': 0, 'review_count': 0}
            ),
        },
        'check_in': start.isoformat(),
        'check_out': end.isoformat(),
        'nights': nights,
        'guests': guest_count,
        'rooms': options,
    }


@app.route('/api/vendor/catalogue', methods=['GET'])
@vendor_required
def vendor_catalogue():
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    campaigns = {(row.listing_type, row.listing_slug): row for row in Promotion.query.all()}

    def with_promotion(listing_type, payload):
        # Partners see the campaign on their listing, whether it is live or scheduled.
        campaign = campaigns.get((listing_type, payload.get('slug')))
        payload['promotion'] = campaign.to_dict() if campaign else None
        return payload

    return {
        'vendor': vendor.to_dict(),
        'csrf_token': session['vendor_csrf'],
        'tours': [with_promotion('tour', item.to_dict()) for item in Tour.query.filter_by(vendor_id=vendor.id).order_by(Tour.name).all()],
        'properties': [with_promotion('property', item.to_dict()) for item in Property.query.filter_by(vendor_id=vendor.id).order_by(Property.name).all()],
        'services': [item.to_dict() for item in Service.query.filter_by(vendor_id=vendor.id).order_by(Service.name).all()],
        'destinations': [item.to_dict() for item in Destination.query.order_by(Destination.name).all()],
        'service_types': [[key, label] for key, label in SERVICE_TYPES.items()],
        'service_price_units': list(SERVICE_PRICE_UNITS),
        'tour_types': [[key, label] for key, label in TOUR_TYPES.items()],
        'tour_group_types': [[key, label] for key, label in TOUR_GROUP_TYPES.items()],
        'subscription': vendor_subscription_payload(vendor),
    }


def vendor_subscription_payload(vendor):
    """Subscription state, the commission it earns, and recent payments."""
    standard_rate = platform_fee_rates()[0]
    subscriber_rate = platform_subscriber_rate()
    active = vendor.subscription_is_active()
    payments = VendorSubscriptionPayment.query.filter_by(vendor_id=vendor.id).order_by(
        VendorSubscriptionPayment.created_at.desc(), VendorSubscriptionPayment.id.desc()
    ).limit(6).all()
    return {
        'status': 'active' if active else 'inactive',
        'is_active': active,
        'is_tour_operator': vendor.is_tour_operator(),
        'eligible': vendor.is_tour_operator(),
        'started_at': vendor.subscription_started_at.isoformat() + 'Z' if vendor.subscription_started_at else None,
        'renews_at': vendor.subscription_renews_at.isoformat() + 'Z' if vendor.subscription_renews_at else None,
        'monthly_fee': platform_subscription_fee(),
        'paid_monthly_fee': float(vendor.subscription_monthly_fee or 0),
        'host_commission_rate': subscriber_rate if active else standard_rate,
        'standard_host_commission_rate': standard_rate,
        'subscriber_host_commission_rate': subscriber_rate,
        'payments': [payment.to_dict() for payment in payments],
    }


@app.route('/api/vendor/subscription/renew', methods=['POST'])
@vendor_required
@limiter.limit('6 per minute')
def vendor_renew_subscription():
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    response = require_vendor_csrf()
    if response:
        return response
    if not vendor.is_tour_operator():
        return {'error': 'Monthly subscriptions are available to tour and safari operators.'}, 400
    if not vendor.is_active:
        return {'error': 'Restore your partner access before renewing a subscription.'}, 403
    if not is_daraja_configured():
        return {'error': 'M-Pesa payments are not configured right now. Please try again later.'}, 503

    amount = platform_subscription_fee()
    if amount <= 0:
        return {'error': 'Subscriptions are not open for renewal right now.'}, 400

    payload = json_payload()
    try:
        mpesa_phone = normalize_mpesa_phone(
            str(payload.get('country_code', '+254')).strip(),
            str(payload.get('phone', '')).strip(),
        )
    except ValueError as exc:
        return {'error': str(exc)}, 400

    if VendorSubscriptionPayment.query.filter_by(vendor_id=vendor.id, status='pending').first():
        return {
            'error': 'A subscription payment is already waiting for confirmation. Finish it on your phone, then try again in a few minutes.'
        }, 409

    payment = VendorSubscriptionPayment(
        vendor_id=vendor.id,
        amount=amount,
        phone=mpesa_phone,
        status='pending',
    )
    db.session.add(payment)
    db.session.commit()
    try:
        request_result = initiate_stk_push(mpesa_phone, int(round(amount)), f'SUB{payment.id}')
    except DarajaError as exc:
        if exc.outcome_unknown:
            # The prompt may still have reached the phone, so keep the reference
            # visible for the partner instead of inviting a second payment.
            payment.status = 'failed'
            db.session.commit()
            app.logger.warning('M-Pesa subscription request unconfirmed: %s', exc)
            return {
                'message': 'The M-Pesa request may have been sent. Check your phone and contact support with this reference before trying again.',
                'payment_reference': payment.reference,
                'payment_pending': True,
            }, 202
        payment.status = 'failed'
        db.session.commit()
        return {'error': str(exc)}, 502

    payment.checkout_request_id = request_result['checkout_request_id']
    payment.merchant_request_id = request_result['merchant_request_id']
    db.session.commit()
    return {
        'message': request_result['customer_message'],
        'payment_reference': payment.reference,
        'subscription': vendor_subscription_payload(vendor),
    }, 202


@app.route('/api/vendor/subscription/status/<string:reference>')
@vendor_required
@limiter.limit('60 per minute')
def vendor_subscription_status(reference):
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    payment = VendorSubscriptionPayment.query.filter_by(
        reference=reference, vendor_id=vendor.id
    ).first()
    if not payment:
        return {'error': 'Subscription payment not found.'}, 404
    return {
        'payment': payment.to_dict(),
        'subscription': vendor_subscription_payload(vendor),
    }


@app.route('/api/admin/vendors/<int:vendor_id>/subscription', methods=['POST'])
@admin_required
def admin_update_vendor_subscription(vendor_id):
    response = require_admin_csrf()
    if response:
        return response
    vendor = db.session.get(VendorAccount, vendor_id)
    if not vendor:
        return {'error': 'Partner account not found.'}, 404
    payload = json_payload()
    action = payload.get('action')
    if action == 'activate':
        try:
            months = int(payload.get('months', 1))
        except (TypeError, ValueError):
            months = 0
        if not 1 <= months <= 12:
            return {'error': 'Choose between 1 and 12 subscription months.'}, 400
        now = datetime.utcnow()
        start = vendor.subscription_renews_at if vendor.subscription_is_active() else now
        if not start or start < now:
            start = now
        vendor.subscription_status = 'active'
        vendor.subscription_plan = 'complimentary'
        vendor.subscription_started_at = vendor.subscription_started_at or now
        vendor.subscription_renews_at = start + VENDOR_SUBSCRIPTION_PERIOD * months
        vendor.subscription_monthly_fee = 0.0
    elif action == 'end':
        vendor.subscription_status = 'inactive'
        # Backdate so the account falls back to the standard commission today.
        vendor.subscription_renews_at = datetime.utcnow() - timedelta(days=1)
    else:
        return {'error': 'Choose a valid subscription action.'}, 400
    db.session.commit()
    return {'vendor': vendor.to_dict()}


def vendor_booking_rows(vendor_id):
    """List a vendor's tour and accommodation bookings for the dashboard."""
    tour_rows = db.session.query(Booking, Tour.name).join(
        Tour, Tour.slug == Booking.tour
    ).filter(
        Tour.vendor_id == vendor_id,
        Booking.booking_type != 'property',
    ).all()
    stay_rows = db.session.query(Booking, Property.name, PropertyRoom.name).join(
        Property, Property.slug == Booking.tour
    ).outerjoin(
        PropertyRoom, PropertyRoom.id == Booking.room_id
    ).filter(
        Property.vendor_id == vendor_id,
        Booking.booking_type == 'property',
    ).all()
    rows = [
        {**booking.to_dict(), 'tour_name': tour_name, 'property_name': None, 'room_name': ''}
        for booking, tour_name in tour_rows
    ]
    rows.extend(
        {
            **booking.to_dict(),
            'tour_name': property_name,
            'property_name': property_name,
            'room_name': room_name or '',
        }
        for booking, property_name, room_name in stay_rows
    )
    rows.sort(key=lambda row: row.get('created_at') or '', reverse=True)
    return rows


@app.route('/api/vendor/bookings', methods=['GET'])
@vendor_required
def vendor_bookings():
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    return {'bookings': vendor_booking_rows(vendor.id)}


@app.route('/api/vendor/bookings/<int:booking_id>/status', methods=['POST'])
@vendor_required
def vendor_update_booking_status(booking_id):
    response = require_vendor_csrf()
    if response:
        return response
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    vendor_id = vendor.id
    booking = db.session.query(Booking).outerjoin(
        Tour, Tour.slug == Booking.tour
    ).outerjoin(
        Property, Property.slug == Booking.tour
    ).filter(
        Booking.id == booking_id,
        or_(Tour.vendor_id == vendor_id, Property.vendor_id == vendor_id),
    ).first()
    if not booking:
        return {'error': 'Booking not found.'}, 404

    requested_status = str(json_payload().get('status', '')).strip()
    if booking.booking_type == 'property':
        transitions = {
            'requested': {'cancelled'},
            'confirmed': {'completed', 'cancelled'},
            'completed': set(),
            'cancelled': set(),
        }
    else:
        transitions = {
            'requested': {'confirmed', 'cancelled'},
            'confirmed': {'in_preparation', 'cancelled'},
            'in_preparation': {'completed', 'cancelled'},
            'completed': set(),
            'cancelled': set(),
        }
    if requested_status not in transitions.get(booking.status, set()):
        return {'error': 'That booking status transition is not allowed.'}, 409
    if requested_status != 'cancelled' and booking.payment_status != 'paid':
        return {'error': 'M-Pesa payment must be verified before this booking can be confirmed.'}, 409
    if requested_status == 'cancelled':
        if booking.payment_status == 'pending':
            return {'error': 'This booking has a pending M-Pesa request. Wait for its payment result before cancelling.'}, 409
        try:
            release_booking_availability(booking)
        except ValueError as exc:
            db.session.rollback()
            return {'error': str(exc)}, 409
        if booking.payment_status == 'pending':
            booking.payment_status = 'cancelled'
    booking.status = requested_status
    db.session.commit()
    email_sent = send_booking_status_notification(booking)
    return {'booking': booking.to_dict(), 'email_sent': email_sent}


@app.route('/api/vendor/tours', methods=['POST'])
@vendor_required
def vendor_create_tour():
    response = require_vendor_csrf()
    if response:
        return response
    data = json_payload()
    try:
        values = tour_values(data)
    except ValueError as exc:
        return {'error': str(exc)}, 400
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    slug = unique_slug(str(data.get('slug') or values['name']), Tour)
    tour = Tour(slug=slug, vendor_id=vendor.id, **values)
    db.session.add(tour)
    db.session.commit()
    return {'tour': tour.to_dict()}, 201


@app.route('/api/vendor/tours/<string:slug>', methods=['PUT', 'DELETE'])
@vendor_required
def vendor_update_tour(slug):
    response = require_vendor_csrf()
    if response:
        return response
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    tour = Tour.query.filter_by(slug=slug, vendor_id=vendor.id).first()
    if not tour:
        return {'error': 'Tour not found.'}, 404
    if request.method == 'DELETE':
        if not delete_tour(tour):
            return {'error': BOOKED_TOUR_DELETE_ERROR}, 409
        return '', 204

    try:
        values = tour_values(json_payload())
    except ValueError as exc:
        return {'error': str(exc)}, 400
    apply_values(tour, values)
    return {'tour': tour.to_dict()}


@app.route('/api/vendor/services', methods=['POST'])
@vendor_required
def vendor_create_service():
    response = require_vendor_csrf()
    if response:
        return response
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    data = json_payload()
    try:
        values = service_values(data)
    except ValueError as exc:
        return {'error': str(exc)}, 400
    slug = unique_slug(str(data.get('slug') or values['name']), Service)
    service = Service(slug=slug, vendor_id=vendor.id, **values)
    db.session.add(service)
    db.session.commit()
    return {'service': service.to_dict()}, 201


@app.route('/api/vendor/services/<string:slug>', methods=['PUT', 'DELETE'])
@vendor_required
def vendor_update_service(slug):
    response = require_vendor_csrf()
    if response:
        return response
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    service = Service.query.filter_by(slug=slug, vendor_id=vendor.id).first()
    if not service:
        return {'error': 'Service not found.'}, 404
    if request.method == 'DELETE':
        db.session.delete(service)
        db.session.commit()
        return '', 204
    try:
        values = service_values(json_payload())
    except ValueError as exc:
        return {'error': str(exc)}, 400
    apply_values(service, values)
    return {'service': service.to_dict()}


@app.route('/api/vendor/properties', methods=['POST'])
@vendor_required
def vendor_create_property():
    response = require_vendor_csrf()
    if response:
        return response
    data = json_payload()
    try:
        values = property_values(data)
    except ValueError as exc:
        return {'error': str(exc)}, 400
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    slug = unique_slug(str(data.get('slug') or values['name']), Property)
    listing = Property(
        slug=slug,
        vendor_id=vendor.id,
        owner_name=vendor.name,
        owner_email=vendor.email,
        **values,
    )
    db.session.add(listing)
    db.session.commit()
    return {'property': listing.to_dict()}, 201


@app.route('/api/vendor/properties/<int:property_id>', methods=['PUT', 'DELETE'])
@vendor_required
def vendor_update_property(property_id):
    response = require_vendor_csrf()
    if response:
        return response
    vendor = get_current_vendor()
    if vendor is None:
        return {'error': 'Partner sign-in is required.'}, 401
    listing = Property.query.filter_by(id=property_id, vendor_id=vendor.id).first()
    if not listing:
        return {'error': 'Property not found.'}, 404
    if request.method == 'DELETE':
        delete_property(listing)
        return '', 204

    try:
        values = property_values(json_payload())
    except ValueError as exc:
        return {'error': str(exc)}, 400
    apply_values(listing, values)
    return {'property': listing.to_dict()}


def live_promotions(day=None):
    """Map (listing_type, listing_slug) to the campaign running on a given day."""
    day = day or datetime.now(KENYA_TIMEZONE).date()
    rows = Promotion.query.filter(
        Promotion.starts_on <= day,
        Promotion.ends_on >= day,
    ).all()
    return {(row.listing_type, row.listing_slug): row for row in rows}


def promotion_listing_name(promotion):
    """Name of the promoted listing, or an empty string if it was removed."""
    if promotion.listing_type == 'tour':
        tour = db.session.get(Tour, promotion.listing_slug)
        return tour.name if tour else ''
    listing = Property.query.filter_by(slug=promotion.listing_slug).first()
    return listing.name if listing else ''


@app.route('/api/catalogue', methods=['GET'])
def public_catalogue():
    operators = {
        operator.id: operator
        for operator in VendorAccount.query.filter_by(is_active=True).all()
    }
    insights = catalogue_insights()
    promotions = live_promotions()

    tours = []
    for tour in Tour.query.order_by(Tour.name).all():
        item = tour.to_dict()
        item.update(insights['tours'].get(tour.slug, {}))
        promotion = promotions.get(('tour', tour.slug))
        item['promotion'] = promotion.public_dict() if promotion else None
        operator = operators.get(tour.vendor_id)
        item['operator'] = operator.public_dict() if operator else None
        tours.append(item)

    properties = []
    for listing in Property.query.order_by(Property.name).all():
        item = listing.to_dict()
        item.update(property_listing_insight(insights, listing))
        promotion = promotions.get(('property', listing.slug))
        item['promotion'] = promotion.public_dict() if promotion else None
        operator = operators.get(listing.vendor_id)
        item['operator'] = operator.public_dict() if operator else None
        properties.append(item)

    services = []
    for service in Service.query.filter_by(is_active=True).order_by(Service.name).all():
        item = service.to_dict()
        operator = operators.get(service.vendor_id)
        item['operator'] = operator.public_dict() if operator else None
        services.append(item)

    if promotions:
        # Each catalogue render is one sponsored impression for every live slot.
        for promotion in promotions.values():
            promotion.impressions = (promotion.impressions or 0) + 1
        db.session.commit()

    return {
        'tours': tours,
        'properties': properties,
        'services': services,
        'operators': [
            operator.public_dict() for operator in operators.values() if operator.slug
        ],
        'destinations': [item.to_dict() for item in Destination.query.order_by(Destination.name).all()],
        'whatsapp_business_phone': WHATSAPP_BUSINESS_PHONE,
        'social_links': social_profile_links(),
        'fees': {
            'host_commission_rate': platform_fee_rates()[0],
            'subscriber_host_commission_rate': platform_subscriber_rate(),
            'guest_service_fee_rate': platform_fee_rates()[1],
            'booking_fee': platform_booking_fee(),
            'subscription_monthly_fee': platform_subscription_fee(),
        },
    }


def property_listing_insight(insights, listing):
    """Insight row for an accommodation, including listings without signals."""
    fallback = {
        'rating': 0,
        'review_count': 0,
        'paid_bookings': 0,
        'recent_bookings': 0,
        'price_from': int(listing.price_per_night or 0),
        'price_to': int(listing.price_per_night or 0),
        'room_types': 0,
        'price_comparison': {'median': 0, 'difference_percent': 0.0, 'position': 'unknown', 'label': ''},
        'badges': [],
    }
    return insights['properties'].get(listing.slug, fallback)


@app.route('/api/operators/<string:slug>', methods=['GET'])
@limiter.limit('120 per minute')
def public_operator(slug):
    """Public profile with everything one safari, tour or service operator sells."""
    operator = VendorAccount.query.filter_by(slug=slug, is_active=True).first()
    if not operator:
        return {'error': 'Operator not found.'}, 404
    profile = operator.public_dict()
    insights = catalogue_insights()

    tours = []
    for tour in Tour.query.filter_by(vendor_id=operator.id).order_by(Tour.name).all():
        item = tour.to_dict()
        item.update(insights['tours'].get(tour.slug, {}))
        item['operator'] = profile
        tours.append(item)

    properties = []
    for listing in Property.query.filter_by(vendor_id=operator.id).order_by(Property.name).all():
        item = listing.to_dict()
        item.update(property_listing_insight(insights, listing))
        item['operator'] = profile
        properties.append(item)

    services = []
    for service in Service.query.filter_by(
        vendor_id=operator.id, is_active=True
    ).order_by(Service.name).all():
        item = service.to_dict()
        item['operator'] = profile
        services.append(item)

    return {
        'operator': profile,
        'tours': tours,
        'properties': properties,
        'services': services,
    }


SEARCH_MAX_QUERY_LENGTH = 120
SEARCH_MAX_TERMS = 8
SEARCH_MAX_CANDIDATES = 200
SEARCH_DEFAULT_LIMIT = 20
SEARCH_MAX_LIMIT = 50
SEARCH_STOP_WORDS = {'a', 'an', 'and', 'at', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'with'}
SEARCH_RESULT_TYPES = ('tour', 'accommodation', 'service', 'destination')
SEARCH_RESULT_LABELS = {
    'tour': 'Tour',
    'accommodation': 'Accommodation',
    'service': 'Service',
    'destination': 'Place',
}
SEARCH_SORTS = ('relevance', 'price_low', 'price_high', 'rating', 'popular')
SEARCH_SIGNAL_MAX_BOOST = 6.0
EMPTY_LISTING_INSIGHT = {
    'rating': 0,
    'review_count': 0,
    'paid_bookings': 0,
    'recent_bookings': 0,
    'price_from': 0,
    'price_to': 0,
    'room_types': 0,
    'price_comparison': {'median': 0, 'difference_percent': 0.0, 'position': 'unknown', 'label': ''},
    'badges': [],
}


def search_terms(query):
    """Split a free-text query into unique, meaningful lowercase terms."""
    words = re.findall(r'[0-9a-z\u00c0-\u024f]+', (query or '').lower())
    terms = []
    for word in words:
        if word in SEARCH_STOP_WORDS or (len(word) < 2 and not word.isdigit()):
            continue
        if word not in terms:
            terms.append(word)
    return terms[:SEARCH_MAX_TERMS]


def search_like_pattern(term):
    """Build a LIKE pattern that treats user-supplied wildcards literally."""
    escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


def search_column_filter(columns, terms):
    """Match a row when any term appears in any of the given columns."""
    return or_(*[
        column.ilike(search_like_pattern(term), escape='\\')
        for term in terms
        for column in columns
    ])


def search_snippet(text, terms, limit=200):
    """Trim body text to a short excerpt around the first matching term."""
    collapsed = re.sub(r'\s+', ' ', text or '').strip()
    if not collapsed:
        return ''
    lowered = collapsed.lower()
    positions = [position for position in (lowered.find(term) for term in terms) if position >= 0]
    if not positions:
        excerpt = collapsed[:limit].rstrip()
        return f'{excerpt}…' if len(collapsed) > limit else excerpt
    start = max(0, min(positions) - 60)
    end = min(len(collapsed), start + limit)
    snippet = collapsed[start:end].strip()
    if start > 0:
        snippet = f'…{snippet}'
    if end < len(collapsed):
        snippet = f'{snippet}…'
    return snippet


def score_search_document(document, terms, phrase=''):
    """Score one catalogue document; 0 means the row does not match."""
    title = document['title'].lower()
    keywords = [str(value).lower() for value in document.get('keywords') or [] if value]
    body = (document.get('body') or '').lower()
    haystack = ' '.join([title, *keywords, body])

    score = 0
    matched_terms = 0
    for term in terms:
        if term not in haystack:
            continue
        matched_terms += 1
        score += 6
        if title == term:
            score += 40
        elif title.startswith(term) or re.search(rf'\b{re.escape(term)}', title):
            score += 24
        elif term in title:
            score += 14
        if any(term in keyword for keyword in keywords):
            score += 8
        if term in body:
            score += 3

    if not matched_terms:
        return 0
    # Reward rows that contain the whole query, not just scattered words.
    if phrase and phrase in haystack:
        score += 30
    return score


def search_signal_score(insight):
    """Small data boost so well-booked, well-rated listings float up on ties.

    Kept well below the title-match weight so text relevance still wins.
    """
    rating = float(insight.get('rating') or 0)
    review_count = int(insight.get('review_count') or 0)
    paid_bookings = int(insight.get('paid_bookings') or 0)
    recent_bookings = int(insight.get('recent_bookings') or 0)
    score = 0.0
    if review_count:
        score += min(2.5, rating / 5 * 2.5)
        score += min(1.0, math.log1p(review_count) / 2)
    score += min(2.0, math.log1p(paid_bookings + recent_bookings * 2))
    position = (insight.get('price_comparison') or {}).get('position')
    if position == 'below':
        score += 1.0
    elif position == 'above':
        score -= 0.5
    return round(max(0.0, min(SEARCH_SIGNAL_MAX_BOOST, score)), 1)


def sort_search_results(results, sort='relevance'):
    """Order results by the requested data signal without mutating the input."""
    if sort == 'price_low':
        return sorted(results, key=lambda item: (
            item['price'] is None, item['price'] or 0, -item['score'], item['title'].lower(),
        ))
    if sort == 'price_high':
        return sorted(results, key=lambda item: (
            item['price'] is None, -(item['price'] or 0), -item['score'], item['title'].lower(),
        ))
    if sort == 'rating':
        return sorted(results, key=lambda item: (
            -(item['rating'] or 0), -item['review_count'], -item['score'], item['title'].lower(),
        ))
    if sort == 'popular':
        return sorted(results, key=lambda item: (
            -item['paid_bookings'], -item['recent_bookings'], -(item['rating'] or 0), item['title'].lower(),
        ))
    return sorted(results, key=lambda item: (-item['score'], item['title'].lower()))


def search_catalogue(query):
    """Rank tours, safaris, accommodations, services and places against a query."""
    terms = search_terms(query)
    empty_counts = {result_type: 0 for result_type in SEARCH_RESULT_TYPES}
    if not terms:
        return [], empty_counts

    phrase = ' '.join(terms)
    insights = catalogue_insights()
    destinations = Destination.query.order_by(Destination.name).all()
    destination_names = {item.slug: item.name for item in destinations}
    operators = {vendor.id: vendor for vendor in VendorAccount.query.all()}
    matching_destination_slugs = [
        item.slug for item in destinations
        if any(term in f'{item.name} {item.description} {item.search_location}'.lower() for term in terms)
    ]

    documents = []

    tour_filter = search_column_filter(
        (Tour.name, Tour.description, Tour.category, Tour.itinerary, Tour.inclusions, Tour.pickup_point),
        terms,
    )
    if matching_destination_slugs:
        tour_filter = or_(tour_filter, Tour.destination.in_(matching_destination_slugs))
    for tour in Tour.query.filter(tour_filter).limit(SEARCH_MAX_CANDIDATES).all():
        destination_name = destination_names.get(tour.destination, tour.destination.replace('-', ' ').title())
        operator = operators.get(tour.vendor_id)
        documents.append({
            'type': 'tour',
            'slug': tour.slug,
            'title': tour.name,
            'subtitle': ' · '.join(part for part in (tour.category, destination_name) if part),
            'keywords': (
                tour.category,
                destination_name,
                tour.duration,
                tour.pickup_point,
                TOUR_TYPES.get(tour.tour_type or 'experience', ''),
                operator.name if operator else '',
            ),
            'body': ' '.join(part for part in (tour.description, tour.itinerary, tour.inclusions) if part),
            'image_url': tour.image_url,
            'price': tour.price,
            'price_unit': 'per guest',
            'url': f'/tour-details.html?id={urllib.parse.quote(tour.slug)}',
            'insight': insights['tours'].get(tour.slug, EMPTY_LISTING_INSIGHT),
        })

    accommodation_filter = search_column_filter(
        (Property.name, Property.description, Property.property_type, Property.location, Property.amenities),
        terms,
    )
    if matching_destination_slugs:
        accommodation_filter = or_(accommodation_filter, Property.destination.in_(matching_destination_slugs))
    for listing in Property.query.filter(accommodation_filter).limit(SEARCH_MAX_CANDIDATES).all():
        insight = insights['properties'].get(listing.slug, EMPTY_LISTING_INSIGHT)
        documents.append({
            'type': 'accommodation',
            'slug': listing.slug or '',
            'title': listing.name,
            'subtitle': ' · '.join(part for part in (listing.property_type.title(), listing.location) if part),
            'keywords': (
                listing.property_type,
                listing.location,
                destination_names.get(listing.destination, ''),
                listing.amenities,
            ),
            'body': listing.description,
            'image_url': listing.image_url,
            'price': insight.get('price_from') or listing.price_per_night,
            'price_unit': 'per night',
            'url': (
                f'/booking.html?stay={urllib.parse.quote(listing.slug)}&guests={listing.guests}'
                if listing.slug else '/booking.html'
            ),
            'insight': insight,
        })

    service_filter = search_column_filter(
        (
            Service.name,
            Service.description,
            Service.location,
            Service.coverage,
            Service.inclusions,
        ),
        terms,
    )
    if matching_destination_slugs:
        service_filter = or_(service_filter, Service.destination.in_(matching_destination_slugs))
    service_query = Service.query.outerjoin(
        VendorAccount, VendorAccount.id == Service.vendor_id
    ).filter(
        Service.is_active.is_(True),
        or_(service_filter, search_column_filter((VendorAccount.name,), terms)),
    )
    for service in service_query.limit(SEARCH_MAX_CANDIDATES).all():
        operator = operators.get(service.vendor_id)
        destination_name = destination_names.get(
            service.destination, service.destination.replace('-', ' ').title()
        )
        documents.append({
            'type': 'service',
            'slug': service.slug,
            'title': service.name,
            'subtitle': ' · '.join(part for part in (
                SERVICE_TYPES.get(service.service_type, ''), destination_name,
            ) if part),
            'keywords': (
                SERVICE_TYPES.get(service.service_type, ''),
                service.location,
                destination_name,
                service.coverage,
                operator.name if operator else '',
            ),
            'body': ' '.join(part for part in (service.description, service.inclusions) if part),
            'image_url': service.image_url,
            'price': service.price_from,
            'price_unit': service.price_unit,
            'url': (
                f'/operators/{urllib.parse.quote(operator.slug)}#service-{urllib.parse.quote(service.slug)}'
                if operator and operator.slug else '/services.html'
            ),
            'insight': EMPTY_LISTING_INSIGHT,
        })

    for item in destinations:
        documents.append({
            'type': 'destination',
            'slug': item.slug,
            'title': item.name,
            'subtitle': item.search_location or 'Kenya',
            'keywords': (item.search_location, item.site_type),
            'body': item.description,
            'image_url': item.image_url,
            'price': None,
            'price_unit': '',
            'url': f'/tours.html?destination={urllib.parse.quote(item.slug)}',
            'insight': EMPTY_LISTING_INSIGHT,
        })

    ranked = []
    for document in documents:
        relevance = score_search_document(document, terms, phrase)
        if not relevance:
            continue
        insight = document.get('insight') or EMPTY_LISTING_INSIGHT
        signal = search_signal_score(insight) if document['type'] != 'destination' else 0.0
        ranked.append({
            'type': document['type'],
            'type_label': SEARCH_RESULT_LABELS[document['type']],
            'slug': document['slug'],
            'title': document['title'],
            'subtitle': document['subtitle'],
            'snippet': search_snippet(document.get('body'), terms),
            'image_url': document['image_url'],
            'price': document['price'],
            'price_to': insight.get('price_to') or document['price'],
            'price_unit': document['price_unit'],
            'room_types': insight.get('room_types', 0),
            'url': document['url'],
            'score': round(relevance + signal, 1),
            'relevance_score': relevance,
            'signal_score': signal,
            'rating': insight.get('rating', 0),
            'review_count': insight.get('review_count', 0),
            'paid_bookings': insight.get('paid_bookings', 0),
            'recent_bookings': insight.get('recent_bookings', 0),
            'badges': insight.get('badges', []),
            'price_comparison': insight.get('price_comparison', EMPTY_LISTING_INSIGHT['price_comparison']),
        })

    ranked.sort(key=lambda item: (-item['score'], item['title'].lower()))
    counts = {result_type: 0 for result_type in SEARCH_RESULT_TYPES}
    for result in ranked:
        counts[result['type']] += 1
    return ranked, counts


def attach_search_promotions(results):
    """Attach a running sponsored placement to tour and accommodation results."""
    promotions = live_promotions()
    for result in results:
        listing_type = {'tour': 'tour', 'accommodation': 'property'}.get(result.get('type'))
        campaign = promotions.get((listing_type, result.get('slug'))) if listing_type and result.get('slug') else None
        result['promotion'] = campaign.public_dict() if campaign else None
    return results


@app.route('/api/search', methods=['GET'])
@limiter.limit('180 per minute')
def public_search():
    query = (request.args.get('q') or '').strip()[:SEARCH_MAX_QUERY_LENGTH]
    terms = search_terms(query)
    if not terms:
        return {'error': 'Enter at least two letters to search.'}, 400

    result_type = (request.args.get('type') or 'all').strip().lower()
    if result_type not in ('all', *SEARCH_RESULT_TYPES):
        return {'error': 'Unknown search type.'}, 400

    sort = (request.args.get('sort') or 'relevance').strip().lower()
    if sort not in SEARCH_SORTS:
        return {'error': 'Unknown search order.'}, 400

    try:
        limit = int(request.args.get('limit', SEARCH_DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return {'error': 'Limit must be a whole number.'}, 400
    limit = max(1, min(limit, SEARCH_MAX_LIMIT))

    results, counts = search_catalogue(query)
    if result_type != 'all':
        results = [result for result in results if result['type'] == result_type]
    results = attach_search_promotions(results)
    results = sort_search_results(results, sort)
    if sort == 'relevance':
        # Sponsored results lead only the default order; price or rating sorts stay truthful.
        results.sort(key=lambda result: -(result['promotion']['rank'] if result.get('promotion') else 0))

    return {
        'query': query,
        'terms': terms,
        'type': result_type,
        'sort': sort,
        'counts': counts,
        'total': len(results),
        'results': results[:limit],
    }


RECOMMENDATION_DEFAULT_LIMIT = 3
RECOMMENDATION_MAX_LIMIT = 6
RECOMMENDATION_TYPES = ('tour', 'accommodation')


def discovery_listing(kind, listing, insight, destination_names):
    """Public listing summary enriched with the data signals used for ranking."""
    destination = listing.destination or ''
    summary = {
        'type': kind,
        'type_label': SEARCH_RESULT_LABELS['tour'] if kind == 'tour' else SEARCH_RESULT_LABELS['accommodation'],
        'slug': listing.slug,
        'name': listing.name,
        'destination': destination,
        'location': destination_names.get(destination, destination.replace('-', ' ').title()),
        'image_url': listing.image_url,
        'rating': insight.get('rating', 0),
        'review_count': insight.get('review_count', 0),
        'paid_bookings': insight.get('paid_bookings', 0),
        'recent_bookings': insight.get('recent_bookings', 0),
        'badges': insight.get('badges', []),
        'price_comparison': insight.get('price_comparison', EMPTY_LISTING_INSIGHT['price_comparison']),
        'room_types': insight.get('room_types', 0),
    }
    if kind == 'tour':
        summary.update({
            'category': listing.category,
            'price_from': int(insight.get('price_from') or listing.price or 0),
            'price_to': int(insight.get('price_to') or listing.price or 0),
            'price_unit': 'per guest',
            'url': f'/tour-details.html?id={urllib.parse.quote(listing.slug)}',
        })
    else:
        summary.update({
            'category': listing.property_type.title(),
            'price_from': int(insight.get('price_from') or listing.price_per_night or 0),
            'price_to': int(insight.get('price_to') or listing.price_per_night or 0),
            'price_unit': 'per night',
            'url': (
                f'/booking.html?stay={urllib.parse.quote(listing.slug)}&guests={listing.guests}'
                if listing.slug else '/booking.html'
            ),
        })
    return summary


def recommendation_similarity(seed, candidate):
    """Score how closely one listing resembles the one being viewed."""
    score = 0.0
    if seed['destination'] and seed['destination'] == candidate['destination']:
        score += 4
    if seed['category'] and seed['category'] == candidate['category']:
        score += 3
    seed_price = float(seed['price_from'] or 0)
    candidate_price = float(candidate['price_from'] or 0)
    if seed_price and candidate_price:
        difference = abs(candidate_price - seed_price) / seed_price
        if difference <= 0.25:
            score += 2
        elif difference <= 0.5:
            score += 1
    score += min(2.0, float(candidate['rating'] or 0) / 5 * 2)
    score += min(2.0, math.log1p(candidate['paid_bookings']))
    return round(score, 2)


def recommendation_reason(seed, candidate, basis):
    """Short, translatable explanation for why a listing is recommended."""
    if basis == 'trending':
        if candidate['recent_bookings'] >= DISCOVERY_POPULAR_MIN_RECENT:
            return 'Trending now'
        if 'Top rated' in candidate['badges']:
            return 'Top rated'
        if 'Best value' in candidate['badges']:
            return 'Best value'
        return 'Popular with travelers'
    same_destination = seed.get('destination') and seed['destination'] == candidate['destination']
    same_style = seed.get('category') and seed['category'] == candidate['category']
    if same_destination and same_style:
        return 'Same destination and style'
    if same_destination:
        return 'Same destination'
    if same_style:
        return 'Similar style'
    if candidate['badges']:
        return candidate['badges'][0]
    return 'Popular with travelers'


@app.route('/api/recommendations', methods=['GET'])
@limiter.limit('180 per minute')
def public_recommendations():
    """Recommend listings from ratings, verified bookings and price fit."""
    kind = (request.args.get('type') or '').strip().lower()
    if kind and kind not in RECOMMENDATION_TYPES:
        return {'error': 'Unknown recommendation type.'}, 400
    slug = (request.args.get('slug') or '').strip()[:160]
    destination = (request.args.get('destination') or '').strip()[:120]
    excluded = {
        value.strip() for value in (request.args.get('exclude') or '').split(',') if value.strip()
    }
    try:
        limit = int(request.args.get('limit', RECOMMENDATION_DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return {'error': 'Limit must be a whole number.'}, 400
    limit = max(1, min(limit, RECOMMENDATION_MAX_LIMIT))

    insights = catalogue_insights()
    destination_names = {item.slug: item.name for item in Destination.query.all()}

    seed = None
    if slug:
        tour = db.session.get(Tour, slug) if kind in ('', 'tour') else None
        if tour is not None:
            seed = discovery_listing(
                'tour', tour, insights['tours'].get(tour.slug, EMPTY_LISTING_INSIGHT), destination_names,
            )
            kind = 'tour'
        if seed is None and kind in ('', 'accommodation'):
            listing = Property.query.filter_by(slug=slug).first()
            if listing is not None:
                seed = discovery_listing(
                    'accommodation', listing,
                    insights['properties'].get(listing.slug, EMPTY_LISTING_INSIGHT), destination_names,
                )
                kind = 'accommodation'

    candidates = []
    if kind in ('', 'tour'):
        candidates.extend(
            discovery_listing('tour', tour, insights['tours'].get(tour.slug, EMPTY_LISTING_INSIGHT), destination_names)
            for tour in Tour.query.all()
        )
    if kind in ('', 'accommodation'):
        candidates.extend(
            discovery_listing(
                'accommodation', listing,
                insights['properties'].get(listing.slug, EMPTY_LISTING_INSIGHT), destination_names,
            )
            for listing in Property.query.all()
            if listing.slug
        )
    candidates = [
        item for item in candidates
        if item['slug'] != slug
        and item['slug'] not in excluded
        and (not destination or item['destination'] == destination)
    ]

    basis = 'similar' if seed else 'trending'
    if seed:
        candidates.sort(key=lambda item: (
            -recommendation_similarity(seed, item),
            -(item['rating'] or 0),
            -item['paid_bookings'],
            item['name'].lower(),
        ))
    else:
        candidates.sort(key=lambda item: (
            -item['recent_bookings'],
            -item['paid_bookings'],
            -(item['rating'] or 0),
            item['name'].lower(),
        ))

    return {
        'basis': basis,
        'seed': {'type': seed['type'], 'slug': seed['slug'], 'name': seed['name']} if seed else None,
        'recommendations': [
            {**item, 'reason': recommendation_reason(seed or {}, item, basis)}
            for item in candidates[:limit]
        ],
    }


def _fetch_json(url):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme != 'https' or parsed_url.hostname not in {'open.er-api.com', 'ipapi.co'}:
        raise ValueError('Currency service URL is not allowed')

    request_object = urllib.request.Request(
        url,
        headers={'Accept': 'application/json', 'User-Agent': f'{BRAND_NAME}/1.0'}
    )
    try:
        # Only allow-listed HTTPS provider hosts reach this call.
        with urllib.request.urlopen(request_object, timeout=CURRENCY_API_TIMEOUT) as response:  # nosec B310
            payload = response.read(1024 * 1024)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError('Currency service request failed') from exc

    try:
        result = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Currency service returned invalid JSON') from exc
    if not isinstance(result, dict):
        raise ValueError('Currency service returned an invalid response')
    return result


def _get_exchange_rates():
    now = time.time()
    with _currency_cache_lock:
        if _exchange_rates_cache['rates'] and _exchange_rates_cache['expires_at'] > now:
            return _exchange_rates_cache['rates'], _exchange_rates_cache['updated_at']

    data = _fetch_json('https://open.er-api.com/v6/latest/KES')
    rates = data.get('rates')
    if data.get('result') != 'success' or not isinstance(rates, dict) or rates.get('KES') != 1:
        raise ValueError('Exchange rate service returned invalid rates')

    valid_rates = {
        code: float(rate)
        for code, rate in rates.items()
        if re.fullmatch(r'[A-Z]{3}', code)
        and isinstance(rate, (int, float))
        and not isinstance(rate, bool)
        and math.isfinite(rate)
        and rate > 0
    }
    if valid_rates.get('KES') != 1:
        raise ValueError('Exchange rate service did not return KES rates')

    updated_at = data.get('time_last_update_utc')
    with _currency_cache_lock:
        _exchange_rates_cache.update({
            'expires_at': now + CURRENCY_CACHE_TTL,
            'rates': valid_rates,
            'updated_at': updated_at if isinstance(updated_at, str) else None,
        })
    return valid_rates, _exchange_rates_cache['updated_at']


def _get_client_public_ip():
    candidates = [*request.access_route, request.remote_addr]
    for candidate in candidates:
        try:
            address = ipaddress.ip_address(candidate)
        except (TypeError, ValueError):
            continue
        if address.is_global:
            return str(address)
    return None


def _get_geolocation(ip_address):
    now = time.time()
    with _currency_cache_lock:
        cached = _geolocation_cache.get(ip_address)
        if cached and cached['expires_at'] > now:
            return cached

    url = f'https://ipapi.co/{urllib.parse.quote(ip_address, safe="")}/json/'
    data = _fetch_json(url)
    currency = data.get('currency')
    country_code = data.get('country_code')
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency):
        raise ValueError('Geolocation service returned an invalid currency')

    result = {
        'currency': currency,
        'country_code': country_code if isinstance(country_code, str) and re.fullmatch(r'[A-Z]{2}', country_code) else None,
        'expires_at': now + CURRENCY_CACHE_TTL,
    }
    with _currency_cache_lock:
        if len(_geolocation_cache) >= 1024:
            oldest = min(_geolocation_cache, key=lambda key: _geolocation_cache[key]['expires_at'])
            del _geolocation_cache[oldest]
        _geolocation_cache[ip_address] = result
    return result


@app.route('/api/currency', methods=['GET'])
def currency_info():
    try:
        rates, updated_at = _get_exchange_rates()
    except ValueError as exc:
        app.logger.warning('Currency rate lookup failed: %s', exc)
        return {'error': 'Currency rates are temporarily unavailable.'}, 503

    currency = 'KES'
    country_code = None
    detected = False
    ip_address = _get_client_public_ip()
    if ip_address:
        try:
            location = _get_geolocation(ip_address)
            country_code = location['country_code']
            if location['currency'] in rates:
                currency = location['currency']
                detected = True
            else:
                app.logger.warning('Exchange rates do not include the detected currency %s.', location['currency'])
        except ValueError as exc:
            app.logger.warning('IP geolocation lookup failed: %s', exc)

    return {
        'base': 'KES',
        'currency': currency,
        'country_code': country_code,
        'detected': detected,
        'rates': rates,
        'updated_at': updated_at,
    }


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit('3 per hour', methods=['POST'])
def register():
    if request.method == 'GET':
        return frontend_page()

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not name or not email or not password:
        return redirect('/register.html?error=Please%20complete%20all%20fields.')
    if len(password) < 8:
        return redirect('/register.html?error=Password%20must%20be%20at%20least%208%20characters.')
    if password != confirm_password:
        return redirect('/register.html?error=Passwords%20do%20not%20match.')
    if User.query.filter_by(email=email).first():
        return redirect('/register.html?error=An%20account%20with%20that%20email%20already%20exists.')

    user = User(name=name, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    session.clear()
    session['user_id'] = user.id
    session['user_name'] = user.name
    session['customer_csrf'] = secrets.token_urlsafe(32)
    return redirect(customer_sign_in_redirect(request.form.get('next'), '/my-bookings'))


CUSTOMER_SIGN_IN_REDIRECTS = {'/wishlist.html', '/my-bookings', '/booking.html'}


def customer_sign_in_redirect(requested, default='/booking.html'):
    """Continue to the page that asked for sign-in, but only for known internal pages."""
    return requested if requested in CUSTOMER_SIGN_IN_REDIRECTS else default


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per hour', key_func=auth_account_key, methods=['POST'], deduct_when=failed_auth_attempt)
@limiter.limit('5 per minute', key_func=auth_attempt_key, methods=['POST'])
@limiter.limit('30 per hour', methods=['POST'])
def login():
    if request.method == 'GET':
        return frontend_page()

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active or not check_password_hash(user.password_hash, password):
        return redirect('/login.html?error=Invalid%20email%20or%20password.')

    session.clear()
    session['user_id'] = user.id
    session['user_name'] = user.name
    session['customer_csrf'] = secrets.token_urlsafe(32)
    return redirect(customer_sign_in_redirect(request.form.get('next')))

@app.route('/logout', methods=['POST'])
@customer_required
def logout():
    response = require_customer_csrf()
    if response:
        return response
    session.clear()
    return '', 204


def booking_change_deadline(booking):
    try:
        starts_at = datetime.strptime(f'{booking.date} {booking.time}', '%Y-%m-%d %H:%M')
    except ValueError as exc:
        raise ValueError('This booking has an invalid departure time and cannot be changed online.') from exc
    now = datetime.now(KENYA_TIMEZONE).replace(tzinfo=None)
    if starts_at - now < timedelta(hours=48):
        raise ValueError('Bookings can only be cancelled or rescheduled at least 48 hours before departure.')


def booking_stay_change_deadline(booking):
    window_hours = int(get_admin_setting('cancellation_window_hours', 48))
    try:
        cutoff = check_in_cutoff(booking.check_in, window_hours)
    except ValueError as exc:
        raise ValueError('This stay has an invalid check-in date and cannot be changed online.') from exc
    now = datetime.now(KENYA_TIMEZONE).replace(tzinfo=None)
    if cutoff - now < timedelta(0):
        raise ValueError(f'Stay bookings can only be cancelled at least {window_hours} hours before check-in.')


@app.route('/api/customer/profile', methods=['GET'])
@customer_required
def customer_profile():
    user = db.session.get(User, session['user_id'])
    if user is None:
        return {'error': 'Sign in to view and manage your bookings.'}, 401
    session.setdefault('customer_csrf', secrets.token_urlsafe(32))
    return {'customer': {'id': user.id, 'name': user.name, 'email': user.email}, 'csrf_token': session['customer_csrf']}


@app.route('/api/customer/bookings', methods=['GET'])
@customer_required
def customer_bookings():
    user = db.session.get(User, session['user_id'])
    if user is None:
        return {'error': 'Sign in to view and manage your bookings.'}, 401
    bookings = Booking.query.filter_by(user_id=user.id).order_by(Booking.created_at.desc()).all()
    stay_slugs = {booking.tour for booking in bookings if booking.booking_type == 'property'}
    stay_names = {
        listing.slug: listing.name for listing in Property.query.filter(Property.slug.in_(stay_slugs)).all()
    } if stay_slugs else {}
    tour_slugs = {booking.tour for booking in bookings if booking.booking_type != 'property'}
    known_tours = {
        tour.slug for tour in Tour.query.filter(Tour.slug.in_(tour_slugs)).all()
    } if tour_slugs else set()
    booked_rooms = {booking.room_id for booking in bookings if booking.room_id}
    room_names = {
        room.id: room.name for room in PropertyRoom.query.filter(PropertyRoom.id.in_(booked_rooms)).all()
    } if booked_rooms else {}
    booking_ids = [booking.id for booking in bookings]
    reviewed = {
        review.booking_id: review
        for review in Review.query.filter(Review.booking_id.in_(booking_ids)).all()
    } if booking_ids else {}
    rows = []
    for booking in bookings:
        row = booking.to_dict()
        if booking.booking_type == 'property':
            row['property_name'] = stay_names.get(booking.tour) or booking.tour.replace('-', ' ').title()
            row['room_name'] = room_names.get(booking.room_id, '')
        review = reviewed.get(booking.id)
        can_review, review_status = review_capability(booking, review)
        live_listing = booking.tour in (stay_names if booking.booking_type == 'property' else known_tours)
        if can_review and not live_listing:
            can_review, review_status = False, 'ineligible'
        row['can_review'] = can_review
        row['review_status'] = review_status
        row['review'] = review.to_dict() if review else None
        rows.append(row)
    return {'bookings': rows, 'pending_reviews': sum(1 for row in rows if row['can_review'])}


WISHLIST_LIMIT = 100
WISHLIST_LISTING_TYPES = {'tour', 'property'}


def saved_listing_payload(row, tours, properties, insights, destination_names):
    """Card data for one saved listing; removed listings stay until deleted."""
    listing = tours.get(row.listing_slug) if row.listing_type == 'tour' else properties.get(row.listing_slug)
    payload = {
        **row.to_dict(),
        'listing_type_label': 'Experience' if row.listing_type == 'tour' else 'Place to stay',
        'name': row.listing_slug.replace('-', ' ').title(),
        'image_url': None,
        'destination': '',
        'destination_name': '',
        'price': 0,
        'price_unit': 'per guest' if row.listing_type == 'tour' else 'per night',
        'rating': 0,
        'review_count': 0,
        'url': '',
        'still_listed': listing is not None,
    }
    if listing is None:
        return payload

    if row.listing_type == 'tour':
        insight = insights['tours'].get(listing.slug) or {}
        payload.update({
            'name': listing.name,
            'image_url': listing.image_url,
            'destination': listing.destination,
            'price': int(listing.price or 0),
            'url': f'/tour-details.html?id={urllib.parse.quote(listing.slug)}',
        })
    else:
        insight = property_listing_insight(insights, listing)
        payload.update({
            'name': listing.name,
            'image_url': listing.image_url,
            'destination': listing.destination,
            'price': int(insight.get('price_from') or listing.price_per_night or 0),
            'url': (
                f'/booking.html?stay={urllib.parse.quote(listing.slug)}&guests={listing.guests}'
                if listing.slug else ''
            ),
        })
    payload.update({
        'destination_name': destination_names.get(
            listing.destination, (listing.destination or '').replace('-', ' ').title()
        ),
        'rating': insight.get('rating') or 0,
        'review_count': insight.get('review_count') or 0,
    })
    return payload


def saved_listing_payloads(rows):
    tours = {tour.slug: tour for tour in Tour.query.all()}
    properties = {listing.slug: listing for listing in Property.query.all() if listing.slug}
    insights = catalogue_insights()
    destination_names = {item.slug: item.name for item in Destination.query.all()}
    return [saved_listing_payload(row, tours, properties, insights, destination_names) for row in rows]


@app.route('/api/customer/saved', methods=['GET'])
@customer_required
@limiter.limit('240 per minute')
def customer_saved_items():
    """The signed-in customer's wishlist, resolved against the live catalogue."""
    user = db.session.get(User, session['user_id'])
    if user is None:
        return {'error': 'Sign in to see your saved listings.'}, 401
    session.setdefault('customer_csrf', secrets.token_urlsafe(32))
    rows = SavedItem.query.filter_by(user_id=user.id).order_by(
        SavedItem.created_at.desc(), SavedItem.id.desc()
    ).all()
    items = saved_listing_payloads(rows)
    return {
        'items': items,
        'count': len(items),
        'limit': WISHLIST_LIMIT,
        'csrf_token': session['customer_csrf'],
    }


@app.route('/api/customer/saved', methods=['POST'])
@customer_required
@limiter.limit('120 per hour', methods=['POST'])
def customer_save_listing():
    """Save one tour or stay to the wishlist; saving twice is not an error."""
    response = require_customer_csrf()
    if response:
        return response
    data = json_payload()
    listing_type = str(data.get('listing_type') or '').strip().lower()
    listing_slug = str(data.get('listing_slug') or '').strip()
    if listing_type not in WISHLIST_LISTING_TYPES:
        return {'error': 'Choose a tour or a place to stay to save.'}, 400
    if not listing_slug or len(listing_slug) > 160:
        return {'error': 'Choose a listing to save.'}, 400

    listing = (
        Tour.query.filter_by(slug=listing_slug).first()
        if listing_type == 'tour'
        else Property.query.filter_by(slug=listing_slug).first()
    )
    if listing is None:
        return {'error': 'That listing is no longer available.'}, 404

    user_id = session['user_id']
    existing = SavedItem.query.filter_by(
        user_id=user_id, listing_type=listing_type, listing_slug=listing_slug,
    ).first()
    if existing is not None:
        return {'item': saved_listing_payloads([existing])[0], 'already_saved': True}, 200

    if SavedItem.query.filter_by(user_id=user_id).count() >= WISHLIST_LIMIT:
        return {
            'error': f'Your wishlist is full. Remove a few listings before adding more (up to {WISHLIST_LIMIT}).',
        }, 409

    row = SavedItem(user_id=user_id, listing_type=listing_type, listing_slug=listing_slug)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        saved = SavedItem.query.filter_by(
            user_id=user_id, listing_type=listing_type, listing_slug=listing_slug,
        ).first()
        if saved is None:
            return {'error': 'This listing could not be saved.'}, 409
        return {'item': saved_listing_payloads([saved])[0], 'already_saved': True}, 200
    return {'item': saved_listing_payloads([row])[0], 'already_saved': False}, 201


@app.route('/api/customer/saved/<int:item_id>', methods=['DELETE'])
@customer_required
def customer_remove_saved_item(item_id):
    response = require_customer_csrf()
    if response:
        return response
    row = SavedItem.query.filter_by(id=item_id, user_id=session['user_id']).first()
    if row is None:
        return {'error': 'That saved listing was not found.'}, 404
    db.session.delete(row)
    db.session.commit()
    return {'removed': item_id}, 200


@app.route('/api/customer/saved', methods=['DELETE'])
@customer_required
def customer_clear_saved_items():
    response = require_customer_csrf()
    if response:
        return response
    removed = SavedItem.query.filter_by(user_id=session['user_id']).delete()
    db.session.commit()
    return {'removed': removed}, 200


@app.route('/api/customer/bookings/<int:booking_id>/cancel', methods=['POST'])
@customer_required
def customer_cancel_booking(booking_id):
    response = require_customer_csrf()
    if response:
        return response
    booking = Booking.query.filter_by(id=booking_id, user_id=session['user_id']).first()
    if not booking:
        return {'error': 'Booking not found.'}, 404
    if booking.status not in {'requested', 'confirmed'}:
        return {'error': 'Only requested or confirmed bookings can be cancelled.'}, 409
    if booking.payment_status == 'pending':
        return {'error': 'Your M-Pesa request is still pending. Wait for its payment result before cancelling.'}, 409
    try:
        if booking.booking_type == 'property':
            booking_stay_change_deadline(booking)
        else:
            booking_change_deadline(booking)
        release_booking_availability(booking)
    except ValueError as exc:
        db.session.rollback()
        return {'error': str(exc)}, 400
    booking.status = 'cancelled'
    if booking.payment_status == 'pending':
        booking.payment_status = 'cancelled'
    refund_queued = queue_cancellation_refund(booking, 'customer')
    db.session.commit()
    if refund_queued:
        send_refund_notification(booking, paid=False)
    return {'booking': booking.to_dict(), 'refund_queued': refund_queued}


@app.route('/api/customer/bookings/<int:booking_id>/reschedule', methods=['POST'])
@customer_required
def customer_reschedule_booking(booking_id):
    response = require_customer_csrf()
    if response:
        return response
    booking = Booking.query.filter_by(id=booking_id, user_id=session['user_id']).first()
    if not booking:
        return {'error': 'Booking not found.'}, 404
    if booking.status not in {'requested', 'confirmed'}:
        return {'error': 'Only requested or confirmed bookings can be rescheduled.'}, 409
    if booking.booking_type == 'property':
        return {'error': 'Stay bookings cannot be rescheduled online. Cancel and book new dates instead.'}, 409
    data = json_payload()
    try:
        booking_change_deadline(booking)
    except ValueError as exc:
        return {'error': str(exc)}, 400
    schedule = TourSchedule.query.filter_by(id=data.get('schedule_id'), tour_slug=booking.tour).first()
    if not schedule:
        return {'error': 'Choose an available departure for this tour.'}, 400
    if schedule.id == booking.schedule_id:
        return {'error': 'Choose a different departure to reschedule.'}, 400
    if schedule.starts_at - datetime.now(KENYA_TIMEZONE).replace(tzinfo=None) < timedelta(hours=48):
        return {'error': 'The new departure must be at least 48 hours away.'}, 400
    try:
        reserve_schedule(schedule.id, booking.guests)
        release_schedule(booking.schedule_id, booking.guests)
    except ValueError as exc:
        db.session.rollback()
        return {'error': str(exc)}, 409
    booking.schedule_id = schedule.id
    booking.date = schedule.starts_at.date().isoformat()
    booking.time = schedule.starts_at.strftime('%H:%M')
    db.session.commit()
    email_sent = send_booking_confirmation(booking)
    return {'booking': booking.to_dict(), 'email_sent': email_sent}


@app.route('/properties', methods=['GET'])
def properties():
    listings = Property.query.order_by(Property.name).all()
    return {'properties': [property_listing.to_dict() for property_listing in listings]}


@app.route('/review-submit', methods=['POST'])
@limiter.limit('5 per hour', methods=['POST'])
def review_submit():
    """Publish a review for a paid booking the signed-in customer already used."""
    data = request.get_json(silent=True) if request.is_json else request.form
    data = data or {}
    user = db.session.get(User, session['user_id']) if session.get('user_id') else None
    if user is None or not user.is_active:
        return {'error': 'Sign in to review a booking from your account.'}, 401
    response = require_customer_csrf()
    if response:
        return response
    try:
        booking_id = int(data.get('booking_id') or 0)
    except (TypeError, ValueError):
        booking_id = 0
    booking = Booking.query.filter_by(id=booking_id, user_id=user.id).first()
    if booking is None:
        return {'error': 'Choose a booking from your account to review.'}, 404
    target_type, target_id, place = booking_review_target(booking)
    if target_type is None:
        return {'error': 'This booking is no longer linked to a listing.'}, 409
    can_review, reason, _ = booking_review_state(booking)
    if not can_review:
        return {'error': review_blocked_message(reason)}, 409

    try:
        rating = int(data.get('rating', 0))
    except (TypeError, ValueError):
        rating = 0
    comment = str(data.get('comment', '')).strip()
    if rating not in range(1, 6) or not comment or len(comment) > 3000:
        return {'error': 'Choose a star rating and write a review of up to 3,000 characters.'}, 400

    review = Review(
        booking_id=booking.id,
        user_id=user.id,
        reviewer_name=user.name,
        reviewer_email=user.email,
        place=place,
        target_type=target_type,
        target_id=target_id,
        rating=rating,
        comment=comment,
    )
    db.session.add(review)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {'error': review_blocked_message('reviewed')}, 409
    return {'review': review.to_dict(), 'can_review': False}, 201


@app.route('/reviews', methods=['GET'])
def reviews():
    query = Review.query
    target_type = request.args.get('target_type', '')
    target_id = request.args.get('target_id', '')
    if target_type and target_id:
        query = query.filter_by(target_type=target_type, target_id=target_id)
    recent_reviews = query.order_by(Review.created_at.desc()).limit(50).all()
    summary = {'rating': 0, 'review_count': 0}
    if target_type and target_id:
        summary = review_ratings(target_type, [target_id]).get(target_id, summary)
    return {'reviews': [review.to_dict() for review in recent_reviews], 'summary': summary}


COMMUNITY_REVIEW_TYPES = {'tour': 'Experience', 'property': 'Place to stay'}


@app.route('/api/community/reviews', methods=['GET'])
@limiter.limit('120 per minute')
def community_reviews():
    """Recent guest reviews across every listing, linked back to what was reviewed."""
    try:
        limit = min(max(int(request.args.get('limit', 24)), 1), 60)
    except (TypeError, ValueError):
        return {'error': 'Limit must be a whole number.'}, 400
    target_type = (request.args.get('target_type') or '').strip().lower()
    if target_type and target_type not in COMMUNITY_REVIEW_TYPES:
        return {'error': 'Choose tour or property reviews.'}, 400

    query = Review.query.filter(Review.target_type.in_(tuple(COMMUNITY_REVIEW_TYPES)))
    if target_type:
        query = query.filter(Review.target_type == target_type)
    rows = query.order_by(Review.created_at.desc()).limit(limit).all()

    tours = {tour.slug: tour for tour in Tour.query.all()}
    stays = {listing.slug: listing for listing in Property.query.all()}
    reviews = []
    for review in rows:
        listing = tours.get(review.target_id) if review.target_type == 'tour' else stays.get(review.target_id)
        if not listing:
            continue
        reviews.append({
            **review.to_dict(),
            'listing_name': listing.name,
            'listing_image': listing.image_url,
            'destination': listing.destination,
            'url': (
                f'/tour-details.html?id={urllib.parse.quote(review.target_id)}'
                if review.target_type == 'tour'
                else f'/booking.html?stay={urllib.parse.quote(review.target_id)}'
            ),
        })

    distribution = {star: 0 for star in (5, 4, 3, 2, 1)}
    ratings = [review.rating for review in rows]
    for rating in ratings:
        if rating in distribution:
            distribution[rating] += 1
    total = len(ratings)
    return {
        'reviews': reviews,
        'summary': {
            'review_count': total,
            'rating': round(sum(ratings) / total, 2) if total else 0,
            'distribution': [
                {'rating': star, 'count': count, 'share': round(count / total * 100) if total else 0}
                for star, count in distribution.items()
            ],
            'tour_count': Review.query.filter_by(target_type='tour').count(),
            'property_count': Review.query.filter_by(target_type='property').count(),
        },
    }


@app.route('/hospitality.html')
def removed_hospitality_page():
    return {'error': 'Not found'}, 404


@app.route('/uploads/<path:filename>')
def uploaded_catalog_image(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/images/<path:filename>')
def bundled_image(filename):
    """Serve the bundled catalogue images used by the React frontend."""
    return send_from_directory(os.path.join(BASE_DIR, 'images'), filename)


@app.route('/pictures/<path:filename>')
def bundled_picture(filename):
    """Serve the bundled property and destination pictures."""
    return send_from_directory(os.path.join(BASE_DIR, 'pictures'), filename)


@app.route('/<path:filename>')
def static_files(filename):
    allowed_extensions = {'.html', '.css', '.js', '.svg', '.ico', '.jpg', '.jpeg', '.png', '.gif', '.webp'}
    extension = os.path.splitext(filename)[1].lower()
    if extension not in allowed_extensions or filename.startswith(('.', '_', 'templates/')):
        return {'error': 'Not found'}, 404
    frontend_index = os.path.join(FRONTEND_DIST, 'index.html')
    frontend_file = os.path.join(FRONTEND_DIST, filename)
    if os.path.isfile(frontend_file):
        return send_from_directory(FRONTEND_DIST, filename)
    if filename.endswith('.html') and os.path.isfile(frontend_index):
        return send_from_directory(FRONTEND_DIST, 'index.html')
    if filename == 'logo.svg' and os.path.isfile(os.path.join(BASE_DIR, filename)):
        return send_from_directory(BASE_DIR, filename)
    return {'error': 'Not found'}, 404

@app.route('/api/newsletter', methods=['POST'])
@limiter.limit('10 per hour', methods=['POST'])
def newsletter_signup():
    """Collect newsletter addresses from the footer and home page forms."""
    payload = request.get_json(silent=True) if request.is_json else request.form
    payload = payload or {}
    email = str(payload.get('email') or '').strip().lower()[:160]
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        return {'error': 'Enter a valid email address.'}, 400
    source = re.sub(r'[^a-z0-9_-]', '', str(payload.get('source') or 'website').lower())[:40] or 'website'

    subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
    if subscriber:
        if not subscriber.is_active:
            subscriber.is_active = True
            subscriber.source = source
            db.session.commit()
        return {'message': 'You are already on the list.', 'already_subscribed': True}, 200

    db.session.add(NewsletterSubscriber(email=email, source=source))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {'message': 'You are already on the list.', 'already_subscribed': True}, 200
    return {'message': 'You are on the list. Karibu!', 'already_subscribed': False}, 201


CHAT_MESSAGE_LIMIT = 2000
CHAT_TOKEN_PATTERN = re.compile(r'^[a-f0-9]{32}$')


def clean_chat_body(value):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value or '')).strip()[:CHAT_MESSAGE_LIMIT]


def clean_chat_name(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:100]


def clean_chat_email(value):
    email = str(value or '').strip().lower()[:160]
    return email if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) else ''


def clean_chat_page(value):
    page = str(value or '').strip()[:160]
    return page if page.startswith('/') else ''


def chat_token_from_request(payload=None):
    """Read the visitor token from the header or a JSON body.

    The token is the only key to a thread, so anything that is not a full
    32-character hex string is treated as no token at all.
    """
    token = request.headers.get('X-Chat-Token', '')
    if not token and isinstance(payload, dict):
        token = payload.get('token') or ''
    token = str(token).strip().lower()
    return token if CHAT_TOKEN_PATTERN.fullmatch(token) else ''


def find_chat_conversation(token):
    if not token:
        return None
    return ChatConversation.query.filter_by(token=token).first()


def chat_thread_payload(conversation, *, after=0):
    query = ChatMessage.query.filter_by(conversation_id=conversation.id)
    if after:
        query = query.filter(ChatMessage.id > after)
    messages = query.order_by(ChatMessage.id.asc()).limit(200).all()
    return {
        'token': conversation.token,
        'status': conversation.status,
        'name': conversation.name or '',
        'email': conversation.email or '',
        'messages': [message.to_dict() for message in messages],
    }


def send_chat_notification(conversation, message):
    """Best-effort email so the team notices a chat that is waiting."""
    if not EMAIL_TO:
        app.logger.warning('Email notification skipped: missing EMAIL_TO configuration.')
        return False

    email = EmailMessage()
    email['Subject'] = f'New live chat from {conversation.name or "a visitor"}'
    email['From'] = EMAIL_FROM
    email['To'] = EMAIL_TO
    email.set_content(
        f"Name: {conversation.name or 'Not given'}\n"
        f"Email: {conversation.email or 'Not given'}\n"
        f"Page: {conversation.page or 'Unknown'}\n"
        f"Message:\n{message.body}\n"
        f"Sent at: {message.created_at.isoformat()}Z\n"
        "Reply in the admin inbox: /dashboard\n"
    )
    return send_email_message(email, context=f'live chat {conversation.id}')


@app.route('/api/support/chat', methods=['GET'])
@limiter.limit('180 per minute')
def support_chat_thread():
    """Poll the visitor's thread; a missing token simply means no chat yet."""
    conversation = find_chat_conversation(chat_token_from_request())
    if conversation is None:
        return {'token': '', 'status': '', 'messages': []}, 200

    after = request.args.get('after', type=int) or 0
    payload = chat_thread_payload(conversation, after=after)
    if conversation.visitor_unread:
        conversation.visitor_unread = 0
        db.session.commit()
    return payload, 200


@app.route('/api/support/chat', methods=['POST'])
@limiter.limit('120 per hour', methods=['POST'])
def support_chat_send():
    """Start a thread on the first message, then append to it."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {'error': 'Chat messages must be sent as JSON.'}, 400

    body = clean_chat_body(payload.get('body'))
    if not body:
        return {'error': 'Type a message before sending.'}, 400

    conversation = find_chat_conversation(chat_token_from_request(payload))
    started = conversation is None
    if started:
        conversation = ChatConversation(
            token=secrets.token_hex(16),
            page=clean_chat_page(payload.get('page')),
        )
        db.session.add(conversation)
        db.session.flush()

    name = clean_chat_name(payload.get('name'))
    email = clean_chat_email(payload.get('email'))
    if name:
        conversation.name = name
    if email:
        conversation.email = email

    now = datetime.utcnow()
    message = ChatMessage(
        conversation_id=conversation.id,
        sender=ChatMessage.VISITOR,
        body=body,
        created_at=now,
    )
    db.session.add(message)
    conversation.status = ChatConversation.OPEN
    conversation.staff_unread = (conversation.staff_unread or 0) + 1
    conversation.message_count = (conversation.message_count or 0) + 1
    conversation.last_message_at = now
    conversation.updated_at = now
    db.session.commit()

    if started:
        send_chat_notification(conversation, message)

    return chat_thread_payload(conversation), 201


@app.route('/api/admin/chat', methods=['GET'])
@admin_required
@limiter.limit('240 per minute')
def admin_chat_inbox():
    """Conversation list for the live chat inbox."""
    status_filter = request.args.get('status', 'open')
    query = ChatConversation.query
    if status_filter in {ChatConversation.OPEN, ChatConversation.CLOSED}:
        query = query.filter(ChatConversation.status == status_filter)
    conversations = query.order_by(ChatConversation.updated_at.desc()).limit(60).all()

    unread_count = db.session.query(db.func.coalesce(db.func.sum(ChatConversation.staff_unread), 0)).scalar()
    return {
        'csrf_token': session.get('admin_csrf', ''),
        'conversations': [conversation.to_dict() for conversation in conversations],
        'open_count': ChatConversation.query.filter_by(status=ChatConversation.OPEN).count(),
        'unread_count': int(unread_count or 0),
    }, 200


@app.route('/api/admin/chat/<int:conversation_id>', methods=['GET'])
@admin_required
@limiter.limit('240 per minute')
def admin_chat_thread(conversation_id):
    conversation = db.session.get(ChatConversation, conversation_id)
    if conversation is None:
        return {'error': 'That conversation no longer exists.'}, 404

    after = request.args.get('after', type=int) or 0
    payload = chat_thread_payload(conversation, after=after)
    payload['conversation'] = conversation.to_dict()
    payload['csrf_token'] = session.get('admin_csrf', '')
    if conversation.staff_unread:
        conversation.staff_unread = 0
        db.session.commit()
    return payload, 200


@app.route('/api/admin/chat/<int:conversation_id>', methods=['POST'])
@admin_required
@limiter.limit('240 per hour', methods=['POST'])
def admin_chat_reply(conversation_id):
    response = require_admin_csrf()
    if response is not None:
        return response

    conversation = db.session.get(ChatConversation, conversation_id)
    if conversation is None:
        return {'error': 'That conversation no longer exists.'}, 404

    payload = request.get_json(silent=True)
    payload = payload if isinstance(payload, dict) else {}
    action = str(payload.get('action') or 'reply').strip().lower()

    if action in {'close', 'reopen'}:
        conversation.status = ChatConversation.CLOSED if action == 'close' else ChatConversation.OPEN
        conversation.updated_at = datetime.utcnow()
        if action == 'reopen':
            conversation.staff_unread = 0
        db.session.commit()
        return {'conversation': conversation.to_dict()}, 200

    body = clean_chat_body(payload.get('body'))
    if not body:
        return {'error': 'Type a reply before sending.'}, 400

    admin = db.session.get(AdminAccount, session['admin_id'])
    now = datetime.utcnow()
    message = ChatMessage(
        conversation_id=conversation.id,
        sender=ChatMessage.STAFF,
        author=clean_chat_name(admin.name if admin else ''),
        body=body,
        created_at=now,
    )
    db.session.add(message)
    conversation.status = ChatConversation.OPEN
    conversation.staff_unread = 0
    conversation.visitor_unread = (conversation.visitor_unread or 0) + 1
    conversation.message_count = (conversation.message_count or 0) + 1
    conversation.last_message_at = now
    conversation.updated_at = now
    db.session.commit()

    return {'message': message.to_dict(), 'conversation': conversation.to_dict()}, 201


@app.route('/contact-submit', methods=['POST'])
@limiter.limit('10 per hour', methods=['POST'])
def contact_submit():
    form_data = request.get_json(silent=True) if request.is_json else request.form
    form_data = form_data or {}
    submission = {
        'name': form_data.get('name', 'Guest'),
        'email': form_data.get('email', ''),
        'subject': form_data.get('subject', ''),
        'message': form_data.get('message', ''),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

    email_sent = send_email_notification(submission)
    submission['email_sent'] = email_sent
    saved_submission = save_submission(submission)
    app.logger.info('Contact submission saved: %s', saved_submission.to_dict())

    if request.is_json:
        return {'message': 'Your message has been received.', 'email_sent': email_sent}, 201

    return redirect('/contact.html?sent=1')

def booking_request_error(message, status_code):
    """Return a booking validation error as JSON or as a legacy form redirect."""
    if request.is_json:
        return {'error': message}, status_code
    return redirect('/booking.html?error=' + urllib.parse.quote(message))


@app.route('/booking-confirmation', methods=['POST'])
@limiter.limit('10 per hour', methods=['POST'])
def booking_confirmation():
    data = request.get_json(silent=True) if request.is_json else request.form
    data = data or {}
    if not is_daraja_configured():
        message = 'M-Pesa payments are not configured right now. Please try again later.'
        if request.is_json:
            return {'error': message}, 503
        return redirect('/booking.html?error=' + urllib.parse.quote(message))

    country_code = str(data.get('country_code', '')).strip()
    phone = str(data.get('phone', '')).strip()
    try:
        mpesa_phone = normalize_mpesa_phone(country_code, phone)
    except ValueError as exc:
        if request.is_json:
            return {'error': str(exc)}, 400
        return redirect('/booking.html?error=' + urllib.parse.quote(str(exc)))

    tour = str(data.get('tour', ''))
    guests = data.get('guests', '1')
    wants_stay = (
        str(data.get('booking_type', '')).strip().lower() == 'property'
        or bool(str(data.get('room_id', '')).strip())
    )

    stay = None
    if wants_stay:
        property_listing = Property.query.filter_by(slug=tour).first()
        if property_listing is None:
            return booking_request_error('Choose an available accommodation before booking.', 400)
        try:
            guest_count = int(guests)
            room_id = int(data.get('room_id') or 0)
        except (TypeError, ValueError):
            return booking_request_error('Choose a room and the number of guests.', 400)
        room = PropertyRoom.query.filter_by(
            id=room_id, property_id=property_listing.id, is_active=True
        ).first()
        if room is None:
            return booking_request_error('That room is no longer available. Please pick another room.', 400)
        if guest_count < 1:
            return booking_request_error('Choose at least one guest.', 400)
        if guest_count > int(room.guests):
            return booking_request_error(f'{room.name} sleeps up to {room.guests} guest(s).', 400)
        try:
            quote = stay_option(room, data.get('check_in'), data.get('check_out'))
        except ValueError as exc:
            return booking_request_error(str(exc), 400)
        if not quote['is_available']:
            return booking_request_error('Those dates are no longer available.', 409)
        if quote['total'] < 1:
            return booking_request_error('This room is not priced for those dates yet.', 400)
        try:
            reserve_room_nights(room, quote['check_in'], quote['check_out'])
        except ValueError as exc:
            db.session.rollback()
            return booking_request_error(str(exc), 409)
        total_amount = quote['total']
        stay = {
            'property': property_listing,
            'room': room,
            'check_in': quote['check_in'],
            'check_out': quote['check_out'],
            'nights': quote['nights'],
        }
    else:
        try:
            guest_count = int(guests)
            total_amount = calculate_booking_price(tour, guest_count)
        except (TypeError, ValueError):
            message = 'Please select a valid tour and guest count.'
            if request.is_json:
                return {'error': message}, 400
            return redirect('/booking.html?error=Please%20select%20a%20valid%20tour%20and%20guest%20count')

    # Subscribed tour operators are charged the lower commission, so the quote
    # needs to know who owns the listing being booked.
    listing_vendor_id = (
        stay['property'].vendor_id
        if stay
        else db.session.query(Tour.vendor_id).filter(Tour.slug == tour).scalar()
    )
    try:
        fees = booking_fee_quote(total_amount, listing_vendor_id)
    except ValueError as exc:
        return booking_request_error(str(exc), 400)

    tour_item = None if stay else db.session.get(Tour, tour)
    schedule = None
    if tour_item:
        schedule = TourSchedule.query.filter_by(
            id=int(data.get('schedule_id') or 0),
            tour_slug=tour_item.slug,
            is_active=True,
        ).first()
        if not schedule or schedule.starts_at <= datetime.now(KENYA_TIMEZONE).replace(tzinfo=None):
            message = 'Choose an available departure before submitting your booking.'
            if request.is_json:
                return {'error': message}, 400
            return redirect('/booking.html?error=Choose%20an%20available%20departure')
        if guest_count < tour_item.min_group_size or guest_count > tour_item.max_group_size:
            message = f'Group size for this tour must be between {tour_item.min_group_size} and {tour_item.max_group_size}.'
            if request.is_json:
                return {'error': message}, 400
            return redirect('/booking.html?error=' + urllib.parse.quote(message))
        try:
            reserve_schedule(schedule.id, guest_count)
        except ValueError as exc:
            db.session.rollback()
            if request.is_json:
                return {'error': str(exc)}, 409
            return redirect('/booking.html?error=' + urllib.parse.quote(str(exc)))

    if stay:
        booking = {
            'user_id': session.get('user_id'),
            'schedule_id': None,
            'name': data.get('name', 'Guest'),
            'email': data.get('email', ''),
            'phone': f'+{mpesa_phone}',
            'tour': stay['property'].slug,
            'date': stay['check_in'],
            'time': '',
            'guests': guest_count,
            'message': data.get('message', ''),
            'amount': fees['total'],
            'subtotal_amount': fees['subtotal'],
            'service_fee_amount': fees['guest_service_fee'],
            'booking_fee_amount': fees['booking_fee'],
            'host_commission_amount': fees['host_commission'],
            'host_payout_amount': fees['host_payout'],
            'host_commission_rate': fees['host_commission_rate'],
            'guest_service_fee_rate': fees['guest_service_fee_rate'],
            # Kept for older admin exports that still read the legacy rate.
            'commission_rate': fees['host_commission_rate'],
            'traffic_source': session.get('analytics_source', 'Unattributed'),
            'payment_status': 'pending',
            'booking_type': 'property',
            'property_id': stay['property'].id,
            'room_id': stay['room'].id,
            'check_in': stay['check_in'],
            'check_out': stay['check_out'],
            'nights': stay['nights'],
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }
    else:
        booking = {
            'user_id': session.get('user_id'),
            'schedule_id': schedule.id if schedule else None,
            'name': data.get('name', 'Guest'),
            'email': data.get('email', ''),
            'phone': f'+{mpesa_phone}',
            'tour': tour,
            'date': schedule.starts_at.date().isoformat() if schedule else data.get('date', ''),
            'time': schedule.starts_at.strftime('%H:%M') if schedule else data.get('time', ''),
            'guests': guests,
            'message': data.get('message', ''),
            'amount': fees['total'],
            'subtotal_amount': fees['subtotal'],
            'service_fee_amount': fees['guest_service_fee'],
            'booking_fee_amount': fees['booking_fee'],
            'host_commission_amount': fees['host_commission'],
            'host_payout_amount': fees['host_payout'],
            'host_commission_rate': fees['host_commission_rate'],
            'guest_service_fee_rate': fees['guest_service_fee_rate'],
            # Kept for older admin exports that still read the legacy rate.
            'commission_rate': fees['host_commission_rate'],
            'traffic_source': session.get('analytics_source', 'Unattributed'),
            'payment_status': 'pending',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
    saved_booking = save_booking(booking)
    app.logger.info('Booking request saved: %s', saved_booking.to_dict())

    try:
        payment_request = create_daraja_stk_push(saved_booking)
    except DarajaError as exc:
        if exc.outcome_unknown:
            app.logger.exception('Daraja payment initiation outcome is unknown for booking %s.', saved_booking.id)
            email_sent = send_booking_confirmation(saved_booking)
            if request.is_json:
                return {
                    'booking': saved_booking.to_dict(),
                    'payment_reference': saved_booking.payment_reference,
                    'payment_pending': True,
                    'message': 'We could not confirm whether the M-Pesa prompt was sent. Check your phone and payment status before trying again.',
                    'email_sent': email_sent,
                    'managed': saved_booking.user_id is not None,
                }, 202
            return redirect('/booking-confirmation.html?' + urllib.parse.urlencode({
                'booking_id': saved_booking.id,
                'reference': saved_booking.payment_reference,
                'email': 'sent' if email_sent else 'unavailable',
                'managed': str(saved_booking.user_id is not None).lower(),
                'pending': 'unknown',
            }))
        app.logger.error('Daraja rejected payment initiation for booking %s: %s', saved_booking.id, exc)
        try:
            release_booking_availability(saved_booking)
            saved_booking.payment_status = 'failed'
            saved_booking.status = 'cancelled'
            db.session.commit()
        except ValueError:
            db.session.rollback()
            app.logger.exception('Could not release failed M-Pesa booking %s.', saved_booking.id)
        if request.is_json:
            return {'error': 'M-Pesa could not start the payment. Your booking was not confirmed; please try again.'}, 503
        return redirect('/booking.html?error=' + urllib.parse.quote(
            'M-Pesa could not start the payment. Your booking was not confirmed; please try again.'
        ))
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception('Could not save the Daraja payment reference for booking %s.', saved_booking.id)
        if request.is_json:
            return {
                'booking': saved_booking.to_dict(),
                'payment_reference': saved_booking.payment_reference,
                'payment_pending': True,
                'message': 'The M-Pesa request may have been sent. Check your phone and contact support before trying again.',
            }, 202
        return redirect('/booking-confirmation.html?' + urllib.parse.urlencode({
            'booking_id': saved_booking.id,
            'reference': saved_booking.payment_reference,
            'pending': 'unknown',
        }))

    email_sent = send_booking_confirmation(saved_booking)
    if request.is_json:
        return {
            'booking': saved_booking.to_dict(),
            'payment_reference': saved_booking.payment_reference,
            'payment_pending': True,
            'message': payment_request['customer_message'],
            'email_sent': email_sent,
            'managed': saved_booking.user_id is not None,
        }, 201
    return redirect('/booking-confirmation.html?' + urllib.parse.urlencode({
        'booking_id': saved_booking.id,
        'reference': saved_booking.payment_reference,
        'email': 'sent' if email_sent else 'unavailable',
        'managed': str(saved_booking.user_id is not None).lower(),
    }))


@app.route('/api/payment-status/<string:payment_reference>')
@limiter.limit('60 per minute')
def payment_status(payment_reference):
    booking = Booking.query.filter_by(payment_reference=payment_reference).first()
    if not booking:
        return {'error': 'Payment status not found.'}, 404
    return {
        'payment_status': booking.payment_status,
        'booking_status': booking.status,
        'mpesa_receipt_number': booking.mpesa_receipt_number,
        'document_urls': {
            'invoice': f'/api/payment-documents/{urllib.parse.quote(payment_reference, safe="")}/invoice',
            'receipt': (
                f'/api/payment-documents/{urllib.parse.quote(payment_reference, safe="")}/receipt'
                if booking.mpesa_receipt_number and booking.payment_status in {'paid', 'refunded'}
                else None
            ),
        },
    }


@app.route('/api/payment-documents/<string:payment_reference>/<string:document_type>')
@limiter.limit('30 per minute')
def payment_document(payment_reference, document_type):
    if document_type not in {'invoice', 'receipt'}:
        return {'error': 'Payment document not found.'}, 404
    booking = Booking.query.filter_by(payment_reference=payment_reference).first()
    if not booking:
        return {'error': 'Payment document not found.'}, 404
    if document_type == 'receipt' and (
        not booking.mpesa_receipt_number or booking.payment_status not in {'paid', 'refunded'}
    ):
        return {'error': 'Payment document not found.'}, 404

    pdf = generate_booking_document(booking, document_type)
    return send_file(
        BytesIO(pdf),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{BRAND_NAME}-{document_type.title()}-{booking.id}.pdf',
        max_age=0,
    )


@app.route('/daraja/callback', methods=['POST'])
def daraja_callback():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return 'Invalid callback payload', 400
    result, status = process_daraja_callback(payload)
    return result, status


@app.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    return frontend_page()

@app.route('/submissions', methods=['GET'])
@admin_required
def submissions():
    all_submissions = Submission.query.order_by(Submission.timestamp.desc()).all()
    return {'submissions': [s.to_dict() for s in all_submissions]}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    )
