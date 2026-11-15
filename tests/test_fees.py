"""Split fee model: 4% host commission, 9% guest service fee and a flat booking fee."""
import pytest

import app as application
from saas.fees import (
    BOOKING_FEE,
    GUEST_SERVICE_FEE_RATE,
    HOST_COMMISSION_RATE,
    SUBSCRIBER_HOST_COMMISSION_RATE,
    SUBSCRIPTION_MONTHLY_FEE,
    split_fee_quote,
)


def test_default_policy_is_four_percent_host_nine_percent_guest_and_a_flat_booking_fee():
    assert HOST_COMMISSION_RATE == 4.0
    assert GUEST_SERVICE_FEE_RATE == 9.0
    assert BOOKING_FEE == 100.0


def test_subscriber_policy_is_two_point_five_percent_for_two_thousand_five_hundred():
    assert SUBSCRIBER_HOST_COMMISSION_RATE == 2.5
    assert SUBSCRIPTION_MONTHLY_FEE == 2500.0
    quote = split_fee_quote(10000, host_rate=SUBSCRIBER_HOST_COMMISSION_RATE)
    assert quote['host_commission'] == 250
    assert quote['host_payout'] == 9750


def test_quote_adds_fees_to_the_guest_total_and_deducts_commission_from_the_payout():
    quote = split_fee_quote(5000)

    assert quote == {
        'subtotal': 5000,
        'guest_service_fee': 450,
        'booking_fee': 100,
        'total': 5550,
        'host_commission': 200,
        'host_payout': 4800,
        'platform_fee': 750,
        'host_commission_rate': 4.0,
        'guest_service_fee_rate': 9.0,
    }
    # The guest total is what the host published plus the guest fees, and the
    # platform keeps the difference between the guest total and the host payout.
    assert quote['total'] - quote['host_payout'] == quote['platform_fee']


def test_quote_rounds_each_fee_to_whole_shillings_half_up():
    quote = split_fee_quote(1234)

    assert quote['subtotal'] == 1234
    assert quote['guest_service_fee'] == 111  # 111.06 shillings
    assert quote['booking_fee'] == 100
    assert quote['total'] == 1445
    assert quote['host_commission'] == 49  # 49.36 shillings
    assert quote['host_payout'] == 1185
    assert split_fee_quote(50)['guest_service_fee'] == 5  # 4.5 rounds up
    assert split_fee_quote(50)['host_commission'] == 2  # 2.0 shillings


def test_quote_honours_custom_rates_and_booking_fee_within_the_policy_bounds():
    quote = split_fee_quote(1000, host_rate=10, guest_rate=5, booking_fee=250)

    assert quote['subtotal'] == 1000
    assert quote['guest_service_fee'] == 50
    assert quote['booking_fee'] == 250
    assert quote['total'] == 1300
    assert quote['host_commission'] == 100
    assert quote['host_payout'] == 900
    assert quote['platform_fee'] == 400
    assert quote['host_commission_rate'] == 10.0
    assert quote['guest_service_fee_rate'] == 5.0


def test_quote_charges_no_booking_fee_without_a_subtotal():
    quote = split_fee_quote(0)

    assert quote['subtotal'] == 0
    assert quote['guest_service_fee'] == 0
    assert quote['booking_fee'] == 0
    assert quote['total'] == 0


@pytest.mark.parametrize('subtotal', [-1, 'not-a-number', None])
def test_quote_rejects_unpriced_subtotals(subtotal):
    with pytest.raises(ValueError):
        split_fee_quote(subtotal)


@pytest.mark.parametrize('host_rate, guest_rate', [(100, 9), (4, -1), (4, 120)])
def test_quote_rejects_rates_outside_the_policy_bounds(host_rate, guest_rate):
    with pytest.raises(ValueError):
        split_fee_quote(1000, host_rate=host_rate, guest_rate=guest_rate)


@pytest.mark.parametrize('booking_fee', [-100, 'not-a-number', None])
def test_quote_rejects_unpriced_booking_fees(booking_fee):
    with pytest.raises(ValueError):
        split_fee_quote(1000, booking_fee=booking_fee)


def test_catalogue_publishes_the_fee_policy():
    visitor = application.app.test_client()

    response = visitor.get('/api/catalogue')

    assert response.status_code == 200
    fees = response.get_json()['fees']
    with application.app.app_context():
        host_rate, guest_rate = application.platform_fee_rates()
        booking_fee = application.platform_booking_fee()
        subscriber_rate = application.platform_subscriber_rate()
        subscription_fee = application.platform_subscription_fee()
    assert fees == {
        'host_commission_rate': host_rate,
        'subscriber_host_commission_rate': subscriber_rate,
        'guest_service_fee_rate': guest_rate,
        'booking_fee': booking_fee,
        'subscription_monthly_fee': subscription_fee,
    }
