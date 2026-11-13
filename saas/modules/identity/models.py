from datetime import datetime

from saas.extensions import db


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def business_type_list(self):
        values = {item.strip() for item in (self.business_types or '').split(',') if item.strip()}
        return [key for key in VENDOR_BUSINESS_TYPES if key in values]

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
