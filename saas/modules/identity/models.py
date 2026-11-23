import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from saas.extensions import db

_NAIROBI = ZoneInfo('Africa/Nairobi')


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedItem(db.Model):
    """One listing a signed-in customer keeps on their wishlist.

    Only the listing type and slug are stored, so a saved card always shows
    the current price and availability instead of a stale copy.
    """

    __tablename__ = 'saved_item'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'listing_type', 'listing_slug', name='uq_saved_item_listing'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    listing_type = db.Column(db.String(20), nullable=False)
    listing_slug = db.Column(db.String(160), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'listing_type': self.listing_type,
            'listing_slug': self.listing_slug,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


class AdminAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Business types a partner can publish under. Safari and tour operators often
# register for several of these at once.
VENDOR_BUSINESS_TYPES = {
    'safari': 'Safari operator',
    'tours': 'Tour operator',
    'accommodation': 'Accommodation host',
    'transport': 'Transport & transfers',
    'services': 'Other travel services',
}

# Business types whose owners can take the discounted monthly subscription.
TOUR_OPERATOR_BUSINESS_TYPES = {'safari', 'tours'}


class VendorAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=True, index=True)
    business_types = db.Column(db.String(255), nullable=False, default='')
    description = db.Column(db.Text, nullable=False, default='')
    location = db.Column(db.String(120), nullable=False, default='')
    phone = db.Column(db.String(50), nullable=False, default='')
    website = db.Column(db.String(255), nullable=False, default='')
    logo_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # Monthly subscription: tour and safari operators who keep it paid pay a
    # lower host commission on every booking taken while it is active.
    subscription_status = db.Column(db.String(20), nullable=False, default='inactive')
    subscription_plan = db.Column(db.String(40), nullable=False, default='')
    subscription_started_at = db.Column(db.DateTime, nullable=True)
    subscription_renews_at = db.Column(db.DateTime, nullable=True)
    subscription_monthly_fee = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def business_type_list(self):
        values = {item.strip() for item in (self.business_types or '').split(',') if item.strip()}
        return [key for key in VENDOR_BUSINESS_TYPES if key in values]

    def is_tour_operator(self):
        """True when the account lists tours or safaris, so it can subscribe."""
        return any(
            key in TOUR_OPERATOR_BUSINESS_TYPES for key in self.business_type_list()
        )

    def subscription_is_active(self, today=None):
        """A prepaid month stays live until its renewal date in Kenya time."""
        if (self.subscription_status or '') != 'active' or not self.subscription_renews_at:
            return False
        today = today or datetime.now(_NAIROBI).date()
        return self.subscription_renews_at.date() >= today

    def subscription_dict(self):
        active = self.subscription_is_active()
        return {
            'status': 'active' if active else 'inactive',
            'plan': self.subscription_plan or '',
            'is_active': active,
            'is_tour_operator': self.is_tour_operator(),
            'started_at': self.subscription_started_at.isoformat() + 'Z' if self.subscription_started_at else None,
            'renews_at': self.subscription_renews_at.isoformat() + 'Z' if self.subscription_renews_at else None,
            'monthly_fee': float(self.subscription_monthly_fee or 0),
        }

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'slug': self.slug,
            'business_types': self.business_type_list(),
            'business_type_labels': [VENDOR_BUSINESS_TYPES[key] for key in self.business_type_list()],
            'description': self.description or '',
            'location': self.location or '',
            'phone': self.phone or '',
            'website': self.website or '',
            'logo_url': self.logo_url,
            'is_active': self.is_active,
            'subscription': self.subscription_dict(),
        }

    def public_dict(self):
        """Operator details safe to publish; the sign-in email stays private."""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug or '',
            'business_types': self.business_type_list(),
            'business_type_labels': [VENDOR_BUSINESS_TYPES[key] for key in self.business_type_list()],
            'description': self.description or '',
            'location': self.location or '',
            'phone': self.phone or '',
            'website': self.website or '',
            'logo_url': self.logo_url,
        }


class VendorSubscriptionPayment(db.Model):
    """One month of a partner subscription payment."""

    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_account.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    phone = db.Column(db.String(20), nullable=False, default='')
    status = db.Column(db.String(20), nullable=False, default='pending')
    payment_method = db.Column(db.String(20), nullable=False, default='paystack')
    payment_channel = db.Column(db.String(40), nullable=True)
    paystack_reference = db.Column(db.String(100), nullable=True)
    reference = db.Column(db.String(64), nullable=False, default=lambda: secrets.token_urlsafe(24))
    # Legacy M-Pesa fields remain for historical subscription receipts.
    checkout_request_id = db.Column(db.String(100), nullable=True)
    merchant_request_id = db.Column(db.String(100), nullable=True)
    mpesa_receipt_number = db.Column(db.String(30), nullable=True)
    period_start = db.Column(db.DateTime, nullable=True)
    period_end = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.Index('uq_subscription_payment_reference', 'reference', unique=True),
        db.Index('uq_subscription_checkout_request_id', 'checkout_request_id', unique=True),
        db.Index('uq_subscription_mpesa_receipt_number', 'mpesa_receipt_number', unique=True),
        db.Index('uq_subscription_paystack_reference', 'paystack_reference', unique=True),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'amount': float(self.amount or 0),
            'status': self.status,
            'payment_method': self.payment_method or 'paystack',
            'payment_channel': self.payment_channel,
            'paystack_reference': self.paystack_reference,
            'reference': self.reference,
            'mpesa_receipt_number': self.mpesa_receipt_number,
            'period_start': self.period_start.isoformat() + 'Z' if self.period_start else None,
            'period_end': self.period_end.isoformat() + 'Z' if self.period_end else None,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'paid_at': self.paid_at.isoformat() + 'Z' if self.paid_at else None,
        }
