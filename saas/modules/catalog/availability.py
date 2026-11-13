"""Nightly inventory, rates and reservations for accommodation rooms."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from saas.extensions import db
from saas.modules.catalog.models import PropertyAvailability

KENYA_TIMEZONE = ZoneInfo('Africa/Nairobi')
MAX_STAY_NIGHTS = 30
MAX_CALENDAR_DAYS = 120
CHECK_IN_HOUR = 14

UNSET = object()


def parse_stay_date(value):
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except (TypeError, ValueError) as exc:
        raise ValueError('Choose valid check-in and check-out dates.') from exc


def stay_nights(check_in, check_out):
    start = parse_stay_date(check_in)
    end = parse_stay_date(check_out)
    nights = (end - start).days
    if nights < 1:
        raise ValueError('Choose a check-out date after check-in.')
    if nights > MAX_STAY_NIGHTS:
        raise ValueError(f'Stays are limited to {MAX_STAY_NIGHTS} nights.')
    if start < datetime.now(KENYA_TIMEZONE).date():
        raise ValueError('Check-in cannot be in the past.')
    return start, end, nights


def dates_between(start, end):
    return [start + timedelta(days=offset) for offset in range((end - start).days)]


def check_in_cutoff(check_in, window_hours):
    """Return the latest moment a stay dated ``check_in`` can still be changed."""
    return datetime.combine(parse_stay_date(check_in), datetime.min.time()).replace(hour=CHECK_IN_HOUR) \
        - timedelta(hours=window_hours)


def availability_rows(room_id, dates):
    if not dates:
        return {}
    rows = PropertyAvailability.query.filter(
        PropertyAvailability.room_id == room_id,
        PropertyAvailability.date.in_(dates),
    ).all()
    return {row.date: row for row in rows}


def nightly_rate(room, override):
    if override is not None and override.rate:
        return int(override.rate)
    return int(room.base_rate)


def available_units(room, override):
    if override is None:
        return max(0, int(room.total_units))
    if override.is_closed:
        return 0
    units = override.units_available if override.units_available is not None else room.total_units
    return max(0, int(units) - int(override.reserved_count or 0))


def stay_option(room, check_in, check_out):
    """Quote a room for a date range, including the remaining units per night."""
    start, end, nights = stay_nights(check_in, check_out)
    dates = dates_between(start, end)
    rows = availability_rows(room.id, dates)
    remaining = None
    total = 0
    nightly = []
    for day in dates:
        override = rows.get(day)
        units = available_units(room, override)
        remaining = units if remaining is None else min(remaining, units)
        rate = nightly_rate(room, override)
        total += rate
        nightly.append({'date': day.isoformat(), 'rate': rate, 'remaining': units})
    return {
        'check_in': start.isoformat(),
        'check_out': end.isoformat(),
        'nights': nights,
        'total': total,
        'remaining': max(0, remaining or 0),
        'is_available': bool(remaining and remaining > 0),
        'nightly': nightly,
    }


def ensure_availability_rows(room, dates):
    rows = availability_rows(room.id, dates)
    missing = [day for day in dates if day not in rows]
    if not missing:
        return rows
    for day in missing:
        db.session.add(PropertyAvailability(
            room_id=room.id,
            date=day,
            units_available=None,
            rate=None,
            is_closed=False,
            reserved_count=0,
        ))
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        raise ValueError('Those dates changed while saving. Please try again.')
    return availability_rows(room.id, dates)


def reserve_room_nights(room, check_in, check_out):
    """Hold one unit per night, refusing the whole stay if any night is sold out."""
    start, end, _ = stay_nights(check_in, check_out)
    dates = dates_between(start, end)
    ensure_availability_rows(room, dates)
    for day in dates:
        reserved = db.session.query(PropertyAvailability).filter(
            PropertyAvailability.room_id == room.id,
            PropertyAvailability.date == day,
            PropertyAvailability.is_closed.is_(False),
            db.func.coalesce(PropertyAvailability.units_available, room.total_units)
            - PropertyAvailability.reserved_count >= 1,
        ).update(
            {PropertyAvailability.reserved_count: PropertyAvailability.reserved_count + 1},
            synchronize_session=False,
        )
        if not reserved:
            db.session.rollback()
            raise ValueError('Those dates are no longer available.')
    return dates


def release_room_nights(room, check_in, check_out):
    """Return held units after a failed payment or a cancellation."""
    try:
        start, end, _ = stay_nights(check_in, check_out)
    except ValueError:
        return
    for day in dates_between(start, end):
        db.session.query(PropertyAvailability).filter(
            PropertyAvailability.room_id == room.id,
            PropertyAvailability.date == day,
            PropertyAvailability.reserved_count >= 1,
        ).update(
            {PropertyAvailability.reserved_count: PropertyAvailability.reserved_count - 1},
            synchronize_session=False,
        )


def calendar_range(start, end):
    start_date = parse_stay_date(start)
    end_date = parse_stay_date(end)
    if end_date < start_date:
        raise ValueError('Choose an end date on or after the start date.')
    if (end_date - start_date).days > MAX_CALENDAR_DAYS:
        raise ValueError(f'Choose a range of {MAX_CALENDAR_DAYS} days or fewer.')
    return start_date, end_date


def room_calendar(room, start, end):
    start_date, end_date = calendar_range(start, end)
    days = [start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)]
    rows = availability_rows(room.id, days)
    calendar = []
    for day in days:
        override = rows.get(day)
        units = room.total_units if override is None or override.units_available is None else override.units_available
        reserved = 0 if override is None else int(override.reserved_count or 0)
        closed = bool(override is not None and override.is_closed)
        calendar.append({
            'date': day.isoformat(),
            'rate': nightly_rate(room, override),
            'units': int(units),
            'reserved': reserved,
            'remaining': 0 if closed else max(0, int(units) - reserved),
            'is_closed': closed,
            'units_available': None if override is None else override.units_available,
            'rate_override': None if override is None else override.rate,
            'has_override': override is not None,
        })
    return calendar


def update_availability_range(room, start, end, *, rate=UNSET, units_available=UNSET, is_closed=UNSET):
    """Apply a rate, unit cap or closure across an inclusive date range."""
    start_date, end_date = calendar_range(start, end)
    days = [start_date + timedelta(days=offset) for offset in range((end_date - start_date).days + 1)]
    rows = ensure_availability_rows(room, days)

    parsed_rate = None
    if rate is not UNSET and rate not in (None, ''):
        try:
            parsed_rate = int(rate)
        except (TypeError, ValueError) as exc:
            raise ValueError('Enter a valid nightly rate.') from exc
        if parsed_rate < 1:
            raise ValueError('Enter a nightly rate of at least 1.')

    parsed_units = None
    if units_available is not UNSET and units_available not in (None, ''):
        try:
            parsed_units = int(units_available)
        except (TypeError, ValueError) as exc:
            raise ValueError('Enter a valid unit count.') from exc
        if parsed_units < 1 or parsed_units > 500:
            raise ValueError('Available units must be between 1 and 500.')

    closed = None
    if is_closed is not UNSET:
        closed = bool(is_closed)

    for day in days:
        row = rows[day]
        if parsed_units is not None and parsed_units < int(row.reserved_count or 0):
            raise ValueError('Available units cannot be below the units already booked for those dates.')
        if rate is not UNSET:
            row.rate = parsed_rate
        if units_available is not UNSET:
            row.units_available = parsed_units
        if closed is not None:
            row.is_closed = closed
    return rows


def clear_availability_day(room, day):
    """Remove a one-day override, keeping any reservations intact."""
    target = parse_stay_date(day)
    row = PropertyAvailability.query.filter_by(room_id=room.id, date=target).first()
    if row is None:
        return
    if row.reserved_count:
        row.units_available = None
        row.rate = None
        row.is_closed = False
    else:
        db.session.delete(row)
