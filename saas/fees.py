"""Platform pricing for the split fee model.

The marketplace earns a small, transparent margin on each confirmed booking
instead of marking up the published price:

* the host is charged a 4% commission, deducted from what they earn;
* tour and safari operators on a paid monthly subscription pay a lower
  2.5% commission instead of 4%;
* the guest pays a 9% service fee, added to the checkout total;
* the guest also pays a flat KSh 100 booking fee on every booking.

The percentage fees are calculated on the listing subtotal (the host's
published price) and rounded to whole Kenyan shillings, so the price a host
publishes is still the price a guest compares. The flat booking fee never
touches the host's payout.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

HOST_COMMISSION_RATE = 4.0
SUBSCRIBER_HOST_COMMISSION_RATE = 2.5
SUBSCRIPTION_MONTHLY_FEE = 2500.0
GUEST_SERVICE_FEE_RATE = 9.0
BOOKING_FEE = 100.0


def _whole_shillings(value):
    return int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def split_fee_quote(
    subtotal,
    host_rate=HOST_COMMISSION_RATE,
    guest_rate=GUEST_SERVICE_FEE_RATE,
    booking_fee=BOOKING_FEE,
):
    """Split a listing subtotal into the guest total, host payout and platform fees.

    `subtotal` is the host's published price for the booking (guests x price per
    guest, or nights x nightly rate). Rates are percentages and `booking_fee` is
    a flat amount in shillings charged to the guest on every booking.
    """
    try:
        base = Decimal(str(subtotal))
        host_rate = Decimal(str(host_rate))
        guest_rate = Decimal(str(guest_rate))
        flat_fee = Decimal(str(booking_fee))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('The booking total could not be priced.') from exc
    if not base.is_finite() or base < 0:
        raise ValueError('The booking total could not be priced.')
    if not (0 <= host_rate < 100 and 0 <= guest_rate < 100):
        raise ValueError('Platform fees must be between 0% and 100%.')
    if not flat_fee.is_finite() or flat_fee < 0:
        raise ValueError('The booking fee could not be priced.')

    subtotal = _whole_shillings(base)
    guest_service_fee = _whole_shillings(base * guest_rate / Decimal('100'))
    host_commission = _whole_shillings(base * host_rate / Decimal('100'))
    # A quote without a subtotal is not a booking, so no flat fee is charged.
    flat_booking_fee = _whole_shillings(flat_fee) if subtotal > 0 else 0

    return {
        'subtotal': subtotal,
        'guest_service_fee': guest_service_fee,
        'booking_fee': flat_booking_fee,
        'total': subtotal + guest_service_fee + flat_booking_fee,
        'host_commission': host_commission,
        'host_payout': subtotal - host_commission,
        'platform_fee': guest_service_fee + flat_booking_fee + host_commission,
        'host_commission_rate': float(host_rate),
        'guest_service_fee_rate': float(guest_rate),
    }
