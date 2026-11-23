from datetime import datetime
from zoneinfo import ZoneInfo

from saas.extensions import db
from saas.fees import GUEST_SERVICE_FEE_RATE, HOST_COMMISSION_RATE
from saas.modules.bookings.models import Booking
from saas.modules.catalog.models import Property, Tour, TourSchedule

KENYA_TIMEZONE = ZoneInfo('Africa/Nairobi')


def parse_local_datetime(value):
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError('Choose a valid date and time.') from exc
    if parsed.tzinfo:
        parsed = parsed.astimezone(KENYA_TIMEZONE).replace(tzinfo=None)
    return parsed


def reserve_schedule(schedule_id, guests):
    result = db.session.query(TourSchedule).filter(
        TourSchedule.id == schedule_id,
        TourSchedule.is_active.is_(True),
        TourSchedule.starts_at > datetime.now(KENYA_TIMEZONE).replace(tzinfo=None),
        TourSchedule.booked_count + guests <= TourSchedule.capacity,
    ).update(
        {TourSchedule.booked_count: TourSchedule.booked_count + guests},
        synchronize_session=False,
    )
    if not result:
        raise ValueError('That departure is no longer available for the selected group size.')
    return db.session.get(TourSchedule, schedule_id)


def release_schedule(schedule_id, guests):
    if schedule_id is None:
        return
    result = db.session.query(TourSchedule).filter(
        TourSchedule.id == schedule_id,
        TourSchedule.booked_count >= guests,
    ).update(
        {TourSchedule.booked_count: TourSchedule.booked_count - guests},
        synchronize_session=False,
    )
    if not result:
        raise ValueError('The booking availability could not be released safely.')


def calculate_booking_price(tour, guests, application):
    if not tour:
        raise ValueError('Tour is required')
    normalized_tour = tour.strip()
    guest_count = int(guests)
    if guest_count < 1:
        raise ValueError('Guests must be at least 1')

    with application.app_context():
        item = db.session.get(Tour, normalized_tour)
        if item:
            price = item.price
        else:
            property_listing = Property.query.filter_by(slug=normalized_tour).first()
            if property_listing:
                price = property_listing.price_per_night
            else:
                raise ValueError(f'Unknown tour or stay: {tour}')
    return price * guest_count


def save_booking(booking):
    new_booking = Booking(
        user_id=booking.get('user_id'),
        schedule_id=booking.get('schedule_id'),
        booking_type=booking.get('booking_type', 'tour'),
        property_id=booking.get('property_id'),
        room_id=booking.get('room_id'),
        check_in=booking.get('check_in'),
        check_out=booking.get('check_out'),
        nights=booking.get('nights'),
        name=booking['name'],
        email=booking['email'],
        phone=booking['phone'],
        tour=booking['tour'],
        date=booking['date'],
        time=booking['time'],
        guests=int(booking['guests']),
        message=booking.get('message', ''),
        amount=float(booking.get('amount', 0) or 0),
        subtotal_amount=float(booking.get('subtotal_amount', 0) or 0),
        service_fee_amount=float(booking.get('service_fee_amount', 0) or 0),
        booking_fee_amount=float(booking.get('booking_fee_amount', 0) or 0),
        host_commission_amount=float(booking.get('host_commission_amount', 0) or 0),
        host_payout_amount=float(booking.get('host_payout_amount', 0) or 0),
        host_commission_rate=float(booking.get('host_commission_rate', HOST_COMMISSION_RATE) or 0),
        guest_service_fee_rate=float(booking.get('guest_service_fee_rate', GUEST_SERVICE_FEE_RATE) or 0),
        commission_rate=float(booking.get('commission_rate', 15) or 15),
        traffic_source=booking.get('traffic_source', 'Unattributed'),
        payment_status=booking.get('payment_status', 'pending'),
        payment_method=booking.get('payment_method', 'paystack'),
        refund_status=booking.get('refund_status', 'none'),
        status=booking.get('status', 'requested'),
        created_at=datetime.fromisoformat(booking['timestamp'][:-1])
        if booking.get('timestamp')
        else datetime.utcnow(),
    )
    db.session.add(new_booking)
    db.session.commit()
    return new_booking
