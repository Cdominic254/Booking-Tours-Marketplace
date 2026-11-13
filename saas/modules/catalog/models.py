from datetime import date, datetime

from saas.extensions import db


TOUR_TYPES = {
    'experience': 'Experience',
    'day-safari': 'Day safari',
    'multi-day-safari': 'Multi-day safari',
    'excursion': 'Excursion',
}

TOUR_GROUP_TYPES = {
    'private': 'Private group',
    'shared': 'Shared group',
}

SERVICE_TYPES = {
    'transfer': 'Airport & hotel transfer',
    'guide': 'Private guide',
    'vehicle': 'Vehicle & driver hire',
    'photography': 'Photography',
    'catering': 'Catering & dining',
    'equipment': 'Equipment hire',
    'other': 'Other travel service',
}

SERVICE_PRICE_UNITS = ('per person', 'per group', 'per day', 'per trip', 'per hour')

# Paid placements sold to partners. A promotion never rewrites the listing: it
# only adds an honest "Sponsored" label and a ranked slot above organic results.
PROMOTION_TIERS = {
    'featured': 'Featured',
    'spotlight': 'Spotlight',
}
PROMOTION_TIER_RANK = {'featured': 1, 'spotlight': 2}
PROMOTION_LISTING_TYPES = {'tour': 'Experience', 'property': 'Place to stay'}


class Tour(db.Model):
    slug = db.Column(db.String(120), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    duration = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(100), nullable=False, default='Experiences')
    itinerary = db.Column(db.Text, nullable=False, default='')
    inclusions = db.Column(db.Text, nullable=False, default='')
    exclusions = db.Column(db.Text, nullable=False, default='')
    pickup_point = db.Column(db.String(200), nullable=False, default='Confirm with your operator')
    min_group_size = db.Column(db.Integer, nullable=False, default=1)
    max_group_size = db.Column(db.Integer, nullable=False, default=12)
    destination = db.Column(db.String(120), nullable=False, default='lamu', index=True)
    image_url = db.Column(db.String(500), nullable=True)
    tour_type = db.Column(db.String(40), nullable=False, default='experience')
    duration_days = db.Column(db.Integer, nullable=False, default=1)
    languages = db.Column(db.Text, nullable=False, default='')
    group_type = db.Column(db.String(20), nullable=False, default='private')
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_account.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'duration': self.duration,
            'price': self.price,
            'category': self.category,
            'itinerary': self.itinerary.splitlines(),
            'inclusions': self.inclusions.splitlines(),
            'exclusions': self.exclusions.splitlines(),
            'pickup_point': self.pickup_point,
            'min_group_size': self.min_group_size,
            'max_group_size': self.max_group_size,
            'destination': self.destination,
            'image_url': self.image_url,
            'tour_type': self.tour_type or 'experience',
            'tour_type_label': TOUR_TYPES.get(self.tour_type or 'experience', TOUR_TYPES['experience']),
            'duration_days': self.duration_days or 1,
            'languages': [item for item in (self.languages or '').splitlines() if item],
            'group_type': self.group_type or 'private',
            'group_type_label': TOUR_GROUP_TYPES.get(self.group_type or 'private', 'Private group'),
        }


class TourSchedule(db.Model):
    __tablename__ = 'tour_schedule'
    __table_args__ = (db.UniqueConstraint('tour_slug', 'starts_at', name='uq_tour_schedule_start'),)

    id = db.Column(db.Integer, primary_key=True)
    tour_slug = db.Column(db.String(120), db.ForeignKey('tour.slug'), nullable=False, index=True)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    capacity = db.Column(db.Integer, nullable=False)
    booked_count = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'tour_slug': self.tour_slug,
            'starts_at': self.starts_at.isoformat(timespec='minutes'),
            'capacity': self.capacity,
            'booked_count': self.booked_count,
            'remaining': self.capacity - self.booked_count,
        }


class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_account.id'), nullable=True, index=True)
    owner_name = db.Column(db.String(100), nullable=False)
    owner_email = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    property_type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    destination = db.Column(db.String(120), nullable=False, default='lamu', index=True)
    amenities = db.Column(db.Text, nullable=False, default='')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    price_per_night = db.Column(db.Integer, nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'name': self.name,
            'property_type': self.property_type,
            'location': self.location,
            'destination': self.destination,
            'amenities': self.amenities.splitlines(),
            'latitude': self.latitude,
            'longitude': self.longitude,
            'price_per_night': self.price_per_night,
            'guests': self.guests,
            'image_url': self.image_url,
            'description': self.description,
        }


class PropertyRoom(db.Model):
    __tablename__ = 'property_room'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    guests = db.Column(db.Integer, nullable=False)
    base_rate = db.Column(db.Integer, nullable=False)
    total_units = db.Column(db.Integer, nullable=False, default=1)
    image_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'property_id': self.property_id,
            'name': self.name,
            'description': self.description,
            'guests': self.guests,
            'base_rate': self.base_rate,
            'total_units': self.total_units,
            'image_url': self.image_url,
            'is_active': self.is_active,
        }


class Promotion(db.Model):
    """A dated, admin-controlled paid placement for one tour or stay.

    One campaign per listing keeps the admin workflow simple: editing a
    campaign is an upsert, ending it is a delete, and the listing itself is
    never modified. Counters are only a rough measure of the slot's reach.
    """

    __tablename__ = 'promotion'
    __table_args__ = (
        db.UniqueConstraint('listing_type', 'listing_slug', name='uq_promotion_listing'),
    )

    id = db.Column(db.Integer, primary_key=True)
    listing_type = db.Column(db.String(20), nullable=False)
    listing_slug = db.Column(db.String(160), nullable=False, index=True)
    tier = db.Column(db.String(20), nullable=False, default='featured')
    headline = db.Column(db.String(140), nullable=False, default='')
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    impressions = db.Column(db.Integer, nullable=False, default=0)
    clicks = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_live(self, day=None):
        day = day or date.today()
        return self.starts_on <= day <= self.ends_on

    def public_dict(self, day=None):
        """What a visitor may see: a label and a rank, never the campaign data."""
        return {
            'sponsored': True,
            'tier': self.tier,
            'tier_label': PROMOTION_TIERS.get(self.tier, 'Sponsored'),
            'label': self.headline or PROMOTION_TIERS.get(self.tier, 'Sponsored'),
            'rank': PROMOTION_TIER_RANK.get(self.tier, 0),
            'ends_on': self.ends_on.isoformat(),
            'live': self.is_live(day),
        }

    def to_dict(self):
        impressions = self.impressions or 0
        clicks = self.clicks or 0
        return {
            **self.public_dict(),
            'id': self.id,
            'listing_type': self.listing_type,
            'listing_slug': self.listing_slug,
            'headline': self.headline,
            'starts_on': self.starts_on.isoformat(),
            'impressions': impressions,
            'clicks': clicks,
            'click_rate': round(clicks / impressions * 100, 1) if impressions else 0.0,
        }


class PropertyAvailability(db.Model):
    __tablename__ = 'property_availability'
    __table_args__ = (
        db.UniqueConstraint('room_id', 'date', name='uq_property_availability_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('property_room.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    units_available = db.Column(db.Integer, nullable=True)
    rate = db.Column(db.Integer, nullable=True)
    is_closed = db.Column(db.Boolean, nullable=False, default=False)
    reserved_count = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'date': self.date.isoformat(),
            'units_available': self.units_available,
            'rate': self.rate,
            'is_closed': self.is_closed,
            'reserved_count': self.reserved_count,
        }


class Destination(db.Model):
    slug = db.Column(db.String(120), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    search_location = db.Column(db.String(120), nullable=False)
    site_type = db.Column(db.String(20), nullable=False, default='area')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'search_location': self.search_location,
            'site_type': self.site_type,
            'latitude': self.latitude,
            'longitude': self.longitude,
        }


class Review(db.Model):
    __table_args__ = (
        # One review per completed booking; NULLs stay allowed for seeded reviews.
        db.Index('uq_review_booking', 'booking_id', unique=True),
    )

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    reviewer_name = db.Column(db.String(100), nullable=False)
    reviewer_email = db.Column(db.String(120), nullable=False)
    place = db.Column(db.String(150), nullable=False)
    target_type = db.Column(db.String(20), nullable=True)
    target_id = db.Column(db.String(160), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'reviewer_name': self.reviewer_name,
            'place': self.place,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'rating': self.rating,
            'comment': self.comment,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


class Service(db.Model):
    """A non-tour travel service sold by a vendor and arranged by enquiry.

    Transfers, private guides, vehicle hire and similar services do not need
    departures or online payment: travellers send the operator a quote request.
    """

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_account.id'), nullable=True, index=True)
    name = db.Column(db.String(150), nullable=False)
    service_type = db.Column(db.String(40), nullable=False, default='other')
    description = db.Column(db.Text, nullable=False)
    price_from = db.Column(db.Integer, nullable=False)
    price_unit = db.Column(db.String(40), nullable=False, default='per person')
    location = db.Column(db.String(120), nullable=False, default='')
    destination = db.Column(db.String(120), nullable=False, default='lamu', index=True)
    coverage = db.Column(db.Text, nullable=False, default='')
    inclusions = db.Column(db.Text, nullable=False, default='')
    image_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'slug': self.slug,
            'vendor_id': self.vendor_id,
            'name': self.name,
            'service_type': self.service_type,
            'service_type_label': SERVICE_TYPES.get(self.service_type, SERVICE_TYPES['other']),
            'description': self.description,
            'price_from': self.price_from,
            'price_unit': self.price_unit,
            'location': self.location,
            'destination': self.destination,
            'coverage': [item for item in (self.coverage or '').splitlines() if item],
            'inclusions': [item for item in (self.inclusions or '').splitlines() if item],
            'image_url': self.image_url,
            'is_active': self.is_active,
        }
