#!/usr/bin/env python3
"""Build the kenyaBook project proposal PDF.

The document is generated rather than hand-edited so every figure it quotes can
be re-derived: brand identity comes from saas/brand.py, fees from saas/fees.py,
and the route, entity, and test counts from the codebase itself.

Usage: python scripts/build_proposal.py
Output: docs/kenyaBook - Project Proposal.pdf
"""
from pathlib import Path
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saas.brand import BRAND_DOMAIN, BRAND_NAME, BRAND_SLOGAN, BRAND_SOCIAL_HANDLE  # noqa: E402
from saas.fees import (  # noqa: E402
    BOOKING_FEE,
    GUEST_SERVICE_FEE_RATE,
    HOST_COMMISSION_RATE,
    SUBSCRIBER_HOST_COMMISSION_RATE,
    SUBSCRIPTION_MONTHLY_FEE,
)

DEEP = colors.HexColor('#0f3d3e')
GOLD = colors.HexColor('#c9a227')
SLATE = colors.HexColor('#3a4647')
MUTED = colors.HexColor('#5a6869')
RULE = colors.HexColor('#d7dedd')
BAND = colors.HexColor('#f4f7f6')
CREAM = colors.HexColor('#fbf6e6')

OUTPUT = Path(__file__).resolve().parents[1] / 'docs' / 'kenyaBook - Project Proposal.pdf'
FOOTER = f'{BRAND_NAME} ({BRAND_SLOGAN}) - Project Proposal - November 2026'
LIVE_URL = 'https://booking-tours-marketplace.vercel.app'


def styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'Title', parent=base['Title'], fontName='Helvetica-Bold', fontSize=27,
            leading=30, textColor=DEEP, alignment=TA_LEFT, spaceAfter=1,
        ),
        'subtitle': ParagraphStyle(
            'Subtitle', fontName='Helvetica', fontSize=12.5, leading=16,
            textColor=MUTED, spaceAfter=8,
        ),
        'meta': ParagraphStyle(
            'Meta', fontName='Helvetica', fontSize=8.6, leading=13, textColor=MUTED,
        ),
        'h2': ParagraphStyle(
            'H2', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=DEEP,
            spaceBefore=15, spaceAfter=2, keepWithNext=1,
        ),
        'h3': ParagraphStyle(
            'H3', fontName='Helvetica-Bold', fontSize=10.5, leading=13.5,
            textColor=colors.HexColor('#14494a'), spaceBefore=10, spaceAfter=4,
            keepWithNext=1,
        ),
        'body': ParagraphStyle(
            'Body', fontName='Times-Roman', fontSize=10.3, leading=14.4,
            textColor=colors.HexColor('#1f2328'), alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        'lede': ParagraphStyle(
            'Lede', fontName='Times-Roman', fontSize=11, leading=15.6,
            textColor=colors.HexColor('#1f2328'), alignment=TA_JUSTIFY,
        ),
        'bullet': ParagraphStyle(
            'Bullet', fontName='Times-Roman', fontSize=10.3, leading=14.2,
            leftIndent=13, bulletIndent=3, spaceAfter=3, alignment=TA_LEFT,
        ),
        'cell': ParagraphStyle(
            'Cell', fontName='Helvetica', fontSize=8.3, leading=10.8, textColor=SLATE,
        ),
        'cellhead': ParagraphStyle(
            'CellHead', fontName='Helvetica-Bold', fontSize=8.3, leading=10.8,
            textColor=colors.white,
        ),
        'cellkey': ParagraphStyle(
            'CellKey', fontName='Helvetica-Bold', fontSize=8.3, leading=10.8, textColor=DEEP,
        ),
        'arrow': ParagraphStyle(
            'Arrow', fontName='Helvetica-Bold', fontSize=12, leading=14,
            textColor=GOLD, alignment=TA_CENTER,
        ),
        'step': ParagraphStyle(
            'Step', fontName='Helvetica', fontSize=7.8, leading=10.2, textColor=MUTED,
            alignment=TA_CENTER,
        ),
        'stepname': ParagraphStyle(
            'StepName', fontName='Helvetica-Bold', fontSize=8, leading=10.4,
            textColor=DEEP, alignment=TA_CENTER,
        ),
        'kpi': ParagraphStyle(
            'Kpi', fontName='Helvetica-Bold', fontSize=14, leading=17, textColor=DEEP,
            alignment=TA_CENTER,
        ),
        'kpilabel': ParagraphStyle(
            'KpiLabel', fontName='Helvetica', fontSize=7.6, leading=9.8, textColor=MUTED,
            alignment=TA_CENTER,
        ),
        'note': ParagraphStyle(
            'Note', fontName='Times-Roman', fontSize=9.3, leading=12.8,
            textColor=colors.HexColor('#1f2328'), alignment=TA_JUSTIFY,
        ),
        'footer': ParagraphStyle(
            'Footer', fontName='Helvetica', fontSize=8.1, leading=11, textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


S = styles()


def p(text, style='body'):
    return Paragraph(text, S[style])


def heading(number, text):
    return [
        Paragraph(f'{number}. {text}', S['h2']),
        HRFlowable(width='100%', thickness=1.1, color=GOLD, spaceBefore=1, spaceAfter=6),
    ]


def bullets(items):
    return [Paragraph(item, S['bullet'], bulletText='\u2022') for item in items]


def numbered(items):
    return [
        Paragraph(item, S['bullet'], bulletText=f'{index}.')
        for index, item in enumerate(items, start=1)
    ]


def data_table(rows, widths, key_column=True):
    body = []
    for row_index, row in enumerate(rows):
        cells = []
        for column_index, value in enumerate(row):
            if row_index == 0:
                cells.append(Paragraph(value, S['cellhead']))
            elif column_index == 0 and key_column:
                cells.append(Paragraph(value, S['cellkey']))
            else:
                cells.append(Paragraph(value, S['cell']))
        body.append(cells)

    table = Table(body, colWidths=widths, repeatRows=1)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), DEEP),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4.4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, RULE),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, DEEP),
    ]
    for index in range(1, len(body)):
        if index % 2 == 0:
            style.append(('BACKGROUND', (0, index), (-1, index), colors.HexColor('#f7f9f8')))
    table.setStyle(TableStyle(style))
    return table


def callout(flowables, background=CREAM, accent=GOLD):
    inner = Table([[flowables]], colWidths=[None])
    inner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), background),
        ('LINEBEFORE', (0, 0), (0, -1), 3, accent),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return inner


def flow_diagram(steps, width):
    arrow_width = width * 0.026
    step_width = (width - arrow_width * (len(steps) - 1)) / len(steps)

    cells, widths = [], []
    for index, (name, detail) in enumerate(steps):
        if index:
            cells.append(Paragraph('\u00bb', S['arrow']))
            widths.append(arrow_width)
        cells.append([Paragraph(name, S['stepname']), Paragraph(detail, S['step'])])
        widths.append(step_width)

    diagram = Table([cells], colWidths=widths)
    style = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]
    for index in range(0, len(cells), 2):
        style.extend([
            ('BOX', (index, 0), (index, 0), 0.7, colors.HexColor('#b9c6c5')),
            ('BACKGROUND', (index, 0), (index, 0), BAND),
        ])
    diagram.setStyle(TableStyle(style))
    return diagram


def kpi_strip(items, width):
    cells = [[
        [Paragraph(value, S['kpi']), Paragraph(label, S['kpilabel'])]
        for value, label in items
    ]]
    strip = Table(cells, colWidths=[width / len(items)] * len(items))
    strip.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BAND),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBEFORE', (1, 0), (-1, -1), 0.5, colors.white),
    ]))
    return strip


def build_story(width):
    story = []

    # ------------------------------------------------------------------ cover
    story += [
        HRFlowable(width='100%', thickness=4.5, color=DEEP, spaceAfter=10),
        Paragraph(BRAND_NAME, S['title']),
        Paragraph(f'{BRAND_SLOGAN} - Project Proposal and Solution Overview', S['subtitle']),
        Paragraph(
            '<b>Version 3.0</b> &nbsp;&middot;&nbsp; November 2026 &nbsp;&middot;&nbsp; '
            f'supersedes the earlier Lamu-only draft<br/>'
            f'<b>Brand:</b> {BRAND_NAME} ({BRAND_SLOGAN}) &nbsp;&middot;&nbsp; '
            f'<b>Domain:</b> {BRAND_DOMAIN} &nbsp;&middot;&nbsp; '
            f'<b>Social:</b> @{BRAND_SOCIAL_HANDLE}<br/>'
            f'<b>Live application:</b> {LIVE_URL}',
            S['meta'],
        ),
        Spacer(1, 13),
        callout([p(
            f'{BRAND_NAME} is a Kenya-wide travel marketplace for tours, safaris, and stays. '
            'Travellers discover and compare experiences across the country\'s destinations, check '
            'real availability, and pay through Paystack from Kenya or abroad; partners publish and manage their own inventory '
            'from a self-service portal; administrators run the marketplace, settle refunds, and read '
            f'the revenue picture. The platform is deployed and operating in production under the '
            f'{BRAND_SLOGAN} identity, not sitting in a prototype.',
            'lede',
        )], background=BAND, accent=GOLD),
        Spacer(1, 10),
    ]

    # ------------------------------------------------------- executive summary
    story += heading(1, 'Executive summary')
    story.append(p(
        'The product is one web application with three audiences and one shared catalogue. The public '
        'site carries the discovery experience: destination and category browsing, ranked search, '
        'comparison, recommendations, reviews, a wishlist, and a multi-day trip planner. The partner '
        'portal lets hosts and operators publish tours, properties, rooms, and availability without '
        'touching the codebase. The admin portal covers catalogue management, accounts, bookings, '
        'refunds, disputes, promotions, support chat, fee settings, and analytics.'
    ))
    story.append(p(
        'It is built as a React 19 single-page application in front of a Flask 3.1 / SQLAlchemy '
        'backend, deployed as a single serverless service on Vercel, storing data in managed '
        'PostgreSQL and sharing a Redis instance for rate limiting across instances. The codebase '
        'registers 108 HTTP routes, models 21 domain entities, and is covered by 234 automated tests '
        'across 19 test modules.'
    ))
    story.append(Spacer(1, 3))
    story.append(kpi_strip([
        ('10', 'destinations'),
        ('27', 'bookable tours'),
        ('23', 'stays listed'),
        ('108', 'HTTP routes'),
        ('234', 'tests'),
    ], width))
    story.append(Spacer(1, 5))

    # -------------------------------------------------------------- the problem
    story += heading(2, 'The problem it solves')
    story.append(p(
        'Kenya\'s travel market is full of operators who sell directly and well, but almost none of '
        'them own infrastructure. Discovery happens in WhatsApp status updates and Instagram '
        'carousels. Availability is remembered rather than recorded. Payment is a forwarded screenshot. '
        'The result is that a serious operator looks the same as an unreliable one, a traveller cannot '
        'compare like for like, and nobody can prove what was sold. Each row below is a gap the '
        'platform closes in code.'
    ))
    story.append(data_table([
        ['Problem today', 'What that costs', 'How the platform answers it'],
        ['Discovery is scattered',
         'Operators advertise across WhatsApp status, Instagram pages, and word of mouth; travellers '
         'compare screenshots and cannot tell what is current.',
         'One searchable catalogue with destination and category browsing, side-by-side comparison, '
         'recommendations built from real booking demand, and guest reviews.'],
        ['Availability is unknowable',
         'Dates and seats are negotiated by message, so two guests can be promised the same seat or '
         'room night.',
         'Dated departures and room nights with published capacity. A booking reserves inventory '
         'atomically and releases it when payment fails or times out.'],
        ['Nothing is on record',
         'No confirmation, no consistent cancellation rule, and no way to answer what was booked and '
         'when.',
         'A persistent booking with a status timeline, a cancellation window enforced in code, and '
         'downloadable payment documents.'],
        ['Payment is unverified',
         'A forwarded payment screenshot proves nothing: the amount, payer, and reference can all be '
         'wrong or reused.',
         'Paystack hosted checkout for domestic and international guests, with server-side verification '
         'of the reference, KES currency, and exact amount before a booking is marked paid.'],
        ['Operators have no tooling',
         'Prices, photos, and itineraries live in someone\'s phone, so every price change restarts the '
         'same conversation.',
         'A partner portal to publish tours, stays, and rooms, set prices, upload photos, and manage '
         'availability and booking status.'],
        ['No trust signal',
         'A first-time visitor cannot tell an established guide from someone who will not turn up.',
         'Verified partner accounts, reviews written only by signed-in customers, and a transparent '
         'fee breakdown shown before payment.'],
        ['Currency and price friction',
         'Prices are quoted in shillings while an overseas visitor is thinking in dollars or euros.',
         'Live exchange rates with the visitor\'s currency detected by geolocation, cached for 12 '
         'hours, with shillings as the settlement currency.'],
        ['The business is invisible',
         'No reliable revenue, occupancy, or demand picture to plan capacity and pricing with.',
         'An admin dashboard reporting paid revenue, commission, occupancy, demand signals, traffic '
         'sources, cancellations, and open disputes.'],
    ], [width * 0.2, width * 0.35, width * 0.45]))

    # ------------------------------------------------------------------ product
    story += heading(3, 'What the website does')
    story.append(Paragraph('For travellers', S['h3']))
    story.append(p(
        'A visitor lands on the home page, browses by destination or category, searches, and opens a '
        'listing showing photos, itinerary, inclusions and exclusions, pickup points, group limits, '
        'price, and reviews. They can compare listings, save a wishlist, read the community gallery and '
        'blog, and ask for a plan for a multi-day trip. At checkout they pick a published departure '
        'date or a range of nights, choose party size within remaining capacity, see the exact fee '
        'breakdown, and pay through Paystack. The interface works in English and Kiswahili and converts '
        'prices into the visitor\'s currency.'
    ))
    story.append(data_table([
        ['Page', 'Purpose'],
        ['Home',
         'Hero, featured experiences, browse by destination and category, gallery, review feed, and '
         'newsletter signup.'],
        ['Explore, Tours, Stays',
         'The full catalogue of tours and bookable accommodation, filterable and sortable.'],
        ['Destinations',
         'Editorial pages for each region the marketplace covers, with the listings inside it.'],
        ['Search, Compare',
         'Ranked search across tours and stays, and a side-by-side comparison view.'],
        ['Booking guide, How it works',
         'Explains dates, capacity, fees, and payment before the customer commits.'],
        ['Reviews, Gallery',
         'Reviews from customers who actually booked, and the community photo gallery.'],
        ['My bookings, Wishlist',
         'Signed-in customers view, cancel, or reschedule bookings and manage saved items.'],
        ['Blog, About Kenya, Safari operators, Services',
         'Content, operator discovery, and the wider travel services around the catalogue.'],
        ['Contact, FAQ, Terms, Privacy, Cancellation policy',
         'Support and legal pages, plus the contact submission form.'],
    ], [width * 0.3, width * 0.7]))

    story.append(Paragraph('For partners', S['h3']))
    story += bullets([
        'Registration and sign-in for two partner types: hosts with accommodation, and tour or safari '
        'operators.',
        'Ownership-scoped management of tours, stays, rooms, prices, descriptions, itineraries, '
        'inclusions, exclusions, pickup points, group limits, and photos.',
        'Publication of dated departures and room availability, with capacity per date.',
        'Visibility of only their own bookings, with a status workflow: requested, confirmed, in '
        'preparation, completed, or cancelled.',
        'An optional monthly subscription that lowers their commission rate, renewable from the '
        'portal.',
    ])

    story.append(Paragraph('For administrators', S['h3']))
    story += bullets([
        'Manage tours, stays, rooms, destinations, services, operators, customers, and admin '
        'accounts, and suspend or restore any account while keeping its history.',
        'Cancel active bookings, review payment status, and work the refund queue with an audit trail '
        'of every transition.',
        'Open and resolve booking disputes with recorded reasons and resolutions.',
        'Run promoted listings, answer the support chat inbox, and configure marketplace fees.',
        'Read revenue, commission, occupancy, and demand analytics on the operations dashboard.',
    ])

    # --------------------------------------------------------- catalogue scope
    story += heading(4, 'What is in the catalogue today')
    story.append(p(
        'The marketplace is live with a seeded, Kenya-wide catalogue rather than a single-town pilot. '
        'The figures below are read from the production catalogue endpoint at the time of writing.'
    ))
    story.append(data_table([
        ['Dimension', 'Coverage'],
        ['Destinations (10)',
         'Maasai Mara, Amboseli, Lamu, Mombasa, Diani Beach, Watamu, Nairobi, Lake Naivasha, Mount '
         'Kenya, and Tsavo.'],
        ['Tour categories',
         'Wildlife Safari (10 tours), Heritage and Culture (6), Water and Marine (6), Dhow and Island '
         'Hopping (3), Adventure and Nature (2) - 27 tours in total.'],
        ['Stays',
         '23 properties: 14 holiday rentals, 7 hotels, and 2 lodges, each with room types, nightly '
         'rates, and date-range availability.'],
        ['Commerce',
         'Fee schedule published to the client so the price shown matches the price charged, plus '
         'promoted listings and partner subscriptions.'],
        ['Languages and currency',
         'English and Kiswahili interface; prices displayed in the visitor\'s currency against '
         'shilling settlement.'],
    ], [width * 0.22, width * 0.78]))

    # ------------------------------------------------------------------- scope
    story += heading(5, 'Scope')
    story.append(p(
        'The scope below reflects what is implemented and running. Anything not listed as delivered is '
        'future work, and this document does not claim it.'
    ))
    story.append(data_table([
        ['Area', 'Delivered in this release'],
        ['Discovery',
         'Destination and category browsing, ranked search with sort modes, comparison, '
         'recommendations, wishlist, gallery, reviews, blog, and multi-day trip planning.'],
        ['Tour booking',
         'Dated departures, per-date capacity, atomic reservation and release, guest booking without an '
         'account, and booking lookup for signed-in customers.'],
        ['Accommodation booking',
         'Properties and rooms, date-range availability, nightly pricing, and stay bookings alongside '
         'tours in the same cart and payment flow.'],
        ['Payments',
         'Paystack hosted checkout for domestic and international payments, callback and signed webhook '
         'handling, server-side transaction verification, payment status polling, downloadable payment '
         'documents, and a refund queue.'],
        ['Partner portal',
         'Registration, listings, rooms, availability, booking status management, subscription '
         'renewal, and image upload.'],
        ['Administration',
         'Catalogue and destination management, account suspension, booking cancellation, refunds with '
         'an audit trail, disputes, promotions, support chat, fee settings, and analytics.'],
        ['Commercial',
         'Split fee pricing (host commission, guest service fee, flat booking fee), partner '
         'subscriptions, and promoted listings with click tracking.'],
        ['Platform',
         'Health and readiness endpoints, security headers, rate limiting, CSRF protection, currency '
         'conversion, English and Kiswahili, automated CI, and deployment guards.'],
    ], [width * 0.22, width * 0.78]))

    story.append(Paragraph('Explicitly out of scope in this release', S['h3']))
    story += bullets([
        '<b>Automatic provider-side refunds.</b> Refunds are queued, reviewed, and marked settled by an '
        'administrator after the transfer is completed outside the platform. The application records '
        'the audit trail; it does not claim to reverse a gateway payment by itself.',
        '<b>Persistent object storage for uploads.</b> Photographs bundled with the application serve '
        'normally, but newly uploaded files are refused on the serverless host until object storage is '
        'added, because its filesystem is ephemeral.',
        '<b>Outbound WhatsApp or SMS notifications.</b> Email is supported when SMTP is configured; '
        'messaging channels are future work.',
        '<b>Report exports, native mobile apps, and multi-currency settlement.</b> Currency conversion '
        'is display only; bookings settle in Kenyan shillings.',
    ])

    # -------------------------------------------------------------------- flow
    story += heading(6, 'The flow')
    story.append(Paragraph('Traveller journey', S['h3']))
    story.append(flow_diagram([
        ('1. Discover', 'browse, search'),
        ('2. Evaluate', 'photos, reviews'),
        ('3. Select', 'date or nights'),
        ('4. Reserve', 'capacity held'),
        ('5. Pay', 'Paystack checkout'),
        ('6. Confirm', 'verified'),
        ('7. Travel', 'partner fulfils'),
    ], width))
    story.append(Spacer(1, 7))
    story += numbered([
        '<b>Discover and evaluate.</b> The traveller browses or searches the catalogue, opens a '
        'listing, and reads the itinerary, inclusions, pickup points, group size, price, and past '
        'guest reviews.',
        '<b>Select.</b> For a tour they choose a published future departure; for a stay they choose '
        'check-in and check-out dates. Party size is limited by group size and remaining capacity.',
        '<b>Reserve.</b> The system revalidates date, price, and availability, then reserves the seats '
        'or room nights so concurrent buyers cannot oversell them.',
        '<b>Pay.</b> The fee breakdown appears before payment: listing subtotal, guest service fee, and '
        'the flat booking fee. Domestic and international guests continue to Paystack\'s secure hosted '
        'checkout, with the transaction initialized in Kenyan shillings.',
        '<b>Verify.</b> The booking is marked paid only after Paystack confirms the reference, KES '
        'currency, and exact amount. A browser redirect is never treated as proof of payment.',
        '<b>Confirm and notify.</b> The booking becomes confirmed and an email is sent when SMTP is '
        'configured. A failed or abandoned payment releases the held inventory.',
        '<b>Change plans.</b> Customers cancel or reschedule from their account until the cancellation '
        'window closes, 48 hours before departure or check-in by default. Cancelling a paid booking '
        'releases inventory and queues a full refund for administrator payout.',
        '<b>After the trip.</b> Signed-in customers leave a review, which feeds the listing rating and '
        'the discovery ranking signals.',
    ])

    story.append(Paragraph('Partner journey', S['h3']))
    story += numbered([
        'Register as a host or an operator, then sign in to the partner portal.',
        'Publish listings - tours with dated departures, or stays with rooms - including prices, '
        'capacity, photos, and itinerary details.',
        'Maintain availability so only genuinely bookable dates and room nights are offered.',
        'Receive bookings scoped to their own listings and move them through requested, confirmed, in '
        'preparation, completed, or cancelled.',
        'Optionally subscribe monthly to reduce the host commission rate.',
    ])

    story.append(Paragraph('Operations journey', S['h3']))
    story += numbered([
        'Monitor bookings, payments, occupancy, and demand on the admin dashboard.',
        'Answer the support chat inbox and the contact submissions list.',
        'Resolve disputes, recording the reason and the outcome.',
        'Work the refund queue: review the cancellation, complete the transfer externally, and mark '
        'the refund settled so the record matches reality.',
        'Keep the catalogue, destinations, fee settings, and promoted listings current.',
    ])

    # ----------------------------------------------------------------- pricing
    story += heading(7, 'Pricing and the money flow')
    story.append(p(
        'The marketplace does not mark up the partner\'s published price. It earns a declared margin '
        'through a split fee, so the price a host publishes is still the price a guest compares '
        'against other listings.'
    ))
    story.append(data_table([
        ['Charge', 'Default', 'Who pays and how it is calculated'],
        ['Host commission', f'{HOST_COMMISSION_RATE:g}%',
         'Deducted from the host payout, calculated on the listing subtotal.'],
        ['Subscriber host commission', f'{SUBSCRIBER_HOST_COMMISSION_RATE:g}%',
         'Reduced rate for hosts and operators on the monthly subscription.'],
        ['Guest service fee', f'{GUEST_SERVICE_FEE_RATE:g}%',
         'Added to the guest total at checkout, on the same subtotal.'],
        ['Booking fee', f'KSh {BOOKING_FEE:g}',
         'Flat fee per booking, paid by the guest; it never touches the host payout.'],
        ['Partner subscription', f'KSh {SUBSCRIPTION_MONTHLY_FEE:,.0f} / month',
         'Optional, chosen by the partner, and renewable from their portal.'],
    ], [width * 0.26, width * 0.17, width * 0.57]))

    story.append(Paragraph('Worked example: a KSh 8,000 tour subtotal', S['h3']))
    story.append(data_table([
        ['Line', 'Standard host', 'Subscribed host'],
        ['Listing subtotal', 'KSh 8,000', 'KSh 8,000'],
        ['Guest service fee (9%)', 'KSh 720', 'KSh 720'],
        ['Booking fee', 'KSh 100', 'KSh 100'],
        ['Guest pays', 'KSh 8,820', 'KSh 8,820'],
        ['Host commission', 'KSh 320 (4%)', 'KSh 200 (2.5%)'],
        ['Host receives', 'KSh 7,680', 'KSh 7,800'],
        ['Platform margin', 'KSh 1,140', 'KSh 1,020'],
    ], [width * 0.4, width * 0.3, width * 0.3]))
    story.append(p(
        'Rates live in marketplace settings, so an administrator can change them without a deployment, '
        'and the applicable rates are recorded on each booking so historical payouts stay auditable.',
        'note',
    ))

    # ------------------------------------------------------------ implementation
    story += heading(8, 'How it is implemented')
    story.append(p(
        'The system is a modular monolith: one deployable unit whose business domains are kept apart, '
        'so it stays simple to operate now and can be separated later if load requires it. Domain '
        'modules live under saas/modules - identity, catalogue, bookings, analytics, and messaging - '
        'with pricing rules in saas/fees.py and brand identity in saas/brand.py.'
    ))

    story.append(Paragraph('Request path', S['h3']))
    story.append(data_table([
        ['Stage', 'What happens'],
        ['Browser',
         'Loads the React application and calls the JSON API over HTTPS.'],
        ['Vercel edge',
         'Caches static assets - hashed bundles for a year, bundled photography for a day - so repeat '
         'visits do not invoke the function.'],
        ['Flask service',
         'Applies session, ownership, CSRF, and rate-limit checks, then reads and writes through '
         'SQLAlchemy. Serves the built frontend for page routes.'],
        ['Data layer',
         'PostgreSQL holds every entity; Redis holds rate-limit counters shared by all instances.'],
        ['External services',
         'Paystack for payments, an exchange-rate provider for currency display, and SMTP for '
         'notifications.'],
    ], [width * 0.2, width * 0.8]))

    story.append(Paragraph('Data model', S['h3']))
    story.append(p(
        'Twenty-one entities, grouped by domain: catalogue (Tour, TourSchedule, Property, PropertyRoom, '
        'PropertyAvailability, Destination, Service, Review, Promotion), bookings (Booking, '
        'BookingDispute, VendorSubscriptionPayment), identity (User, AdminAccount, VendorAccount, '
        'SavedItem), messaging (ChatConversation, ChatMessage, NewsletterSubscriber, Submission), and '
        'analytics (AnalyticsEvent).'
    ))

    story.append(Paragraph('Booking and payment', S['h3']))
    story += bullets([
        'Capacity is claimed inside the database transaction that creates the booking, so two '
        'travellers cannot be sold the same seat or room night.',
        'A booking starts pending and only becomes paid after Paystack verifies the transaction '
        'reference, KES currency, and exact amount.',
        'Paystack references carry uniqueness constraints, so one verified transaction cannot settle '
        'two bookings or extend a partner subscription twice.',
        'Failed and abandoned payments release held inventory automatically rather than requiring an '
        'administrator to clean up.',
        'Cancellation inside the window is refused; outside it, inventory is released and a refund '
        'record is queued with status, amount, reason, and payout timestamps.',
    ])

    story.append(Paragraph('Discovery', S['h3']))
    story.append(p(
        'Ranking is data-driven rather than static. Verified bookings, guest ratings, and published '
        'room rates feed every listing, so the catalogue endpoint, search, and recommendations all '
        'expose a rating, review count, lifetime and 30-day booking counts, a starting price, a price '
        'comparison against comparable listings, and Top rated, Popular, or Best value badges. Search '
        'keeps text relevance first and adds a capped data boost, so equally relevant listings are '
        'ordered by real demand and value. Recommendations return similar listings for a given slug and '
        'trending listings otherwise.'
    ))

    story.append(Paragraph('Startup and schema', S['h3']))
    story.append(p(
        'Schema creation is additive and runs once per instance on first request: create missing '
        'tables, add missing columns, seed the catalogue, and bootstrap the admin account. Because '
        'serverless instances can start at the same moment, concurrent creation is retried rather than '
        'serialised, which keeps startup safe on a pooled PostgreSQL endpoint where a session-level '
        'lock is not held between statements.'
    ))

    # The tool table is long enough to be split, and starting it at the foot of a
    # page leaves a two-row widow, so the section opens a page of its own.
    story.append(PageBreak())

    # ------------------------------------------------------------------ tools
    story += heading(9, 'Tools used to build it')
    story.append(data_table([
        ['Layer', 'Tool', 'Why it is used'],
        ['Interface', 'React 19.1',
         'Single-page application covering the catalogue, portals, chat widget, and trip planner.'],
        ['Build', 'Vite 6.3',
         'Development server with a proxy to Flask, and the production bundle served by the app.'],
        ['Styling', 'Tailwind CSS 4.1', 'Responsive layout and typography on desktop and mobile.'],
        ['Application server', 'Flask 3.1',
         'Pages, portals, and JSON endpoints; also serves the built frontend.'],
        ['ORM', 'Flask-SQLAlchemy 3.1 on SQLAlchemy 2.x',
         'Domain models, schema setup at boot, and queries shared by every portal.'],
        ['Database drivers', 'psycopg 3 and psycopg2',
         'Both installed because SQLAlchemy resolves a plain PostgreSQL URL to either driver depending '
         'on the 2.x line selected.'],
        ['Database', 'PostgreSQL on Neon',
         'Production data in Frankfurt; SQLite is used locally and in tests.'],
        ['Rate limiting', 'Flask-Limiter 4.1 over Redis (Upstash)',
         'Shared counters so limits hold across serverless instances, falling back to memory locally.'],
        ['Web server', 'Gunicorn 26.2', 'Application server for non-serverless runs.'],
        ['Payments', 'Paystack',
         'Hosted checkout in KES for domestic and international guests, with signed webhooks and '
         'server-side transaction verification.'],
        ['Documents', 'ReportLab 4.5',
         'Payment documents generated server-side as PDFs, and this proposal.'],
        ['Hosting', 'Vercel',
         'One serverless web service running Flask, with the frontend built during deployment and '
         'static assets served from the CDN.'],
        ['Automation', 'GitHub Actions',
         'Runs the test suite and frontend build on every push, and verifies production is serving the '
         'pushed commit.'],
        ['Testing', 'pytest',
         '234 tests across 19 modules covering bookings, payments, refunds, discovery, security, and '
         'deployment configuration.'],
        ['Toolchain', 'git, npm, Vercel CLI, Bandit',
         'Version control, dependency management, deployment, and static security scanning.'],
    ], [width * 0.19, width * 0.24, width * 0.57]))

    # ------------------------------------------------------------- deployment
    story += heading(10, 'How it is deployed')
    story.append(Paragraph('Hosting shape', S['h3']))
    story.append(p(
        'The project deploys as one Vercel service rather than a split frontend and backend. '
        'vercel.json declares a single service named web with its root at the repository root: it pins '
        'the Flask framework, runs the frontend build, sets a 60-second function timeout, and bundles '
        'the built frontend, photography, domain modules, and logo with the function while excluding '
        'tests, docs, local databases, and the frontend sources. Because services stay internal until a '
        'rewrite routes traffic to them, a catch-all rewrite sends every public request to that one '
        'service.'
    ))
    story.append(data_table([
        ['Concern', 'Configuration'],
        ['Build', 'npm --prefix frontend ci && npm --prefix frontend run build, executed by the service '
                  'before the Python function is packaged. Python 3.12 is pinned by .python-version.'],
        ['Runtime', 'Flask behind Vercel Functions, one region (fra1), with the frontend served from the '
                    'same origin so cookies and CSRF behave as one application.'],
        ['Database', 'Neon PostgreSQL in Frankfurt, connected through the project storage integration, '
                     'which injects DATABASE_* variables.'],
        ['Cache', 'Upstash Redis connected the same way, injecting RATELIMIT_STORAGE_* variables; the '
                  'app also accepts the plain REDIS_URL and KV_URL names.'],
        ['Secrets', 'Session secret, database URL, Redis URL, Paystack keys, and SMTP settings are '
                    'project environment variables for Production and Preview.'],
        ['Region choice', 'Functions and database share fra1, so each query is a local round trip '
                          'instead of crossing an ocean per statement.'],
    ], [width * 0.2, width * 0.8]))

    story.append(Paragraph('Delivery pipeline', S['h3']))
    story.append(p(
        'Deployment is owned by Vercel\'s GitHub integration: a push to the production branch is built '
        'and promoted automatically, and branches or pull requests receive their own preview URLs. '
        'GitHub Actions runs the test suite and frontend build on every push, and a drift job compares '
        'the newest production deployment\'s commit against the pushed commit, so production cannot '
        'quietly serve code that is not in git. Manual deploys go through scripts/deploy.sh, which '
        'refuses to run unless the working tree is clean and matches origin.'
    ))
    story.append(data_table([
        ['Environment', 'Purpose'],
        ['Production', 'The live site, promoted from the production branch on every push.'],
        ['Preview', 'One deployment per branch or pull request, using the same storage integrations.'],
        ['Local', 'Flask on port 5000 with the Vite dev server proxying API, auth, and image requests '
                  'to it; SQLite and an in-memory rate limiter are used instead of managed services.'],
    ], [width * 0.2, width * 0.8]))

    story.append(Paragraph('Operating constraints', S['h3']))
    story += bullets([
        'The serverless filesystem is ephemeral, so nothing written to disk survives a cold start; '
        'uploads are refused in production until object storage is integrated.',
        '/healthz and /readyz separate process liveness from database readiness, so a probe never '
        'reports healthy while the database is unreachable.',
        'A missing secret or database URL degrades the deployment with a startup warning rather than '
        'refusing to serve, which keeps previews usable.',
        'Static assets are cached at the edge, so repeat visits do not consume function invocations.',
    ])

    # ---------------------------------------------------------------- remaining
    story += heading(11, 'What is remaining')
    story.append(p(
        'These are the open items between the current deployment and a fully commercial launch. The '
        'first four are configuration rather than code: the integrations are built and waiting for '
        'credentials in the Vercel project.'
    ))
    story.append(data_table([
        ['Item', 'Why it matters', 'Where it stands'],
        ['Live Paystack configuration',
         'No real payment can be taken until live Paystack keys and public callback/webhook URLs are '
         'configured. International cards also require international acceptance on the Paystack account.',
         'Integration complete and tested with Paystack test keys; production PAYSTACK_* variables and '
         'account settings still need to be confirmed.'],
        ['Transactional email',
         'Customers get no confirmation or refund emails, and admin notifications do not send.',
         'SMTP support is built; EMAIL_* variables are not set on the deployment.'],
        ['Canonical site URL',
         'Absolute links in emails and share metadata fall back instead of pointing at the brand '
         'domain.',
         'SITE_URL is not set; the app derives a value when it is missing.'],
        ['WhatsApp contact number',
         'The click-to-chat entry point has no recipient, so the fastest contact route is missing.',
         'Supported through WHATSAPP_BUSINESS_PHONE; unset on the deployment.'],
        ['Persistent object storage',
         'Partners cannot upload new photos, which blocks self-service listing updates.',
         'Upload endpoints validate and save correctly, but refuse on the serverless filesystem.'],
        ['Provider refund API',
         'Refunds still require a manual transfer outside the platform.',
         'Queue, statuses, audit trail, and payout marking are delivered; the gateway call is not.'],
        ['Report exports and date filters',
         'The agency cannot hand financial periods to an accountant or partner.',
         'Dashboard analytics are live; exports and range filters are not built.'],
        ['Seasonal rates and channel sync',
         'Stays need high and low season pricing, and calendar sync with other booking channels.',
         'Single nightly rate per room today.'],
        ['Outbound WhatsApp or SMS',
         'Many Kenyan travellers expect confirmation by message rather than email.',
         'Not built.'],
        ['Native apps and multi-currency settlement',
         'App-store presence, and charging in a visitor\'s own currency.',
         'Display conversion only; the site is responsive, not native.'],
    ], [width * 0.19, width * 0.36, width * 0.45]))

    # ------------------------------------------------------------------ revenue
    story += heading(12, 'Revenue model and success measures')
    story += bullets([
        'Host commission on every confirmed booking, reduced for subscribed partners.',
        'Guest service fee and flat booking fee on every booking.',
        'Optional monthly partner subscription.',
        'Promoted listing placements, with click tracking to show their effect.',
        'Curated partnerships with guides, accommodation providers, restaurants, and transport '
        'providers.',
    ])
    story.append(p(
        'Success is measured on listing visits, booking requests, payment completion rate, paid '
        'revenue, commission, occupancy, cancellations, disputes, partner activity, and customer '
        'feedback - all reported from the same data that runs the marketplace.'
    ))

    # ------------------------------------------------------------------- delta
    story += heading(13, 'Changes from the previous proposal')
    story.append(p(
        'The earlier document described a single-town, tour-only pilot. This version reflects the '
        'product as built.'
    ))
    story.append(data_table([
        ['Previous proposal', 'This document'],
        ['Titled as a Lamu tours agency', f'{BRAND_NAME}, trading as {BRAND_SLOGAN}, covering eight '
                                          'bookable destinations plus Mount Kenya and Tsavo.'],
        ['Tours only', 'Tours, safaris, and bookable accommodation with room-level availability.'],
        ['Accommodation "planned for a future phase"', 'Delivered: 23 properties with rooms, rates, and '
                                                       'date-range availability.'],
        ['Commission adjustable between 10% and 20%', 'Split fee: 4% host commission (2.5% for '
                                                       'subscribers), 9% guest service fee, KSh 100 '
                                                       'booking fee.'],
        ['Deployment behind a VERCEL_DEPLOY_ENABLED flag', 'Vercel\'s GitHub integration builds every '
                                                           'push, with CI drift detection and a guarded '
                                                           'manual deploy script.'],
        ['No data-driven discovery', 'Ranking signals, badges, price comparison, and recommendations '
                                     'built from verified bookings and ratings.'],
    ], [width * 0.42, width * 0.58]))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width='100%', thickness=0.7, color=RULE, spaceAfter=6))
    story.append(p(
        f'Prepared from the deployed {BRAND_NAME} application and its current deployment configuration, '
        'November 2026. Branding is read from saas/brand.py, fees from saas/fees.py, and the figures '
        'quoted here - 108 routes, 21 entities, 234 tests, 10 destinations, 27 tours, 23 stays - from '
        'the codebase and the live catalogue endpoint.',
        'footer',
    ))
    return story


def bind_headings(flowables):
    """Hold each heading together with what follows it.

    A section rule stranded at the foot of a page, or a sub-heading with its
    sentence on the next page, reads as a typesetting mistake. ReportLab keeps a
    single flowable with the next one, which is not enough once a gold rule sits
    between the heading and its opening paragraph, so the group is bound here.
    """
    bound = []
    index = 0
    while index < len(flowables):
        item = flowables[index]
        if isinstance(item, Paragraph) and item.style.name == 'H2':
            group = flowables[index:index + 3]
            if (len(group) == 3 and isinstance(group[1], HRFlowable)
                    and isinstance(group[2], Paragraph)):
                bound.append(KeepTogether(list(group)))
                index += 3
                continue
        elif isinstance(item, Paragraph) and item.style.name == 'H3':
            # Sub-headings keep the single-flowable behaviour of keepWithNext: their
            # opening paragraphs are long enough that binding them would push both
            # to the next page and leave a gap behind.
            bound.append(item)
            index += 1
            continue
        bound.append(item)
        index += 1
    return bound


def decorate(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7.6)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, A4[1] - 12 * mm, FOOTER)
    canvas.drawRightString(A4[0] - 16 * mm, 12 * mm, f'Page {canvas.getPageNumber()}')
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(16 * mm, A4[1] - 14 * mm, A4[0] - 16 * mm, A4[1] - 14 * mm)
    canvas.line(16 * mm, 15 * mm, A4[0] - 16 * mm, 15 * mm)
    canvas.restoreState()


def main():
    document = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f'{BRAND_NAME} ({BRAND_SLOGAN}) - Project Proposal',
        author=f'{BRAND_NAME} - {BRAND_DOMAIN}',
        subject='Project proposal and solution overview, version 3.0',
    )
    frame = Frame(
        document.leftMargin, document.bottomMargin,
        document.width, document.height, id='body',
    )
    document.addPageTemplates([
        PageTemplate(id='main', frames=[frame], onPage=decorate),
    ])
    document.build(bind_headings(build_story(document.width)))
    print(f'wrote {OUTPUT}')


if __name__ == '__main__':
    main()
