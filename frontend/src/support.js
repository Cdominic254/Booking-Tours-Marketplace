// Support and policy pages linked from the footer. Content is bundled with the
// frontend so these pages stay fast and readable without an API round trip.
export const SUPPORT_PAGES = [
  {
    slug: 'how-it-works',
    path: '/how-it-works.html',
    title: 'How it works',
    eyebrow: 'Booking with us',
    summary: 'From browsing to boarding the dhow: how a booking on the marketplace moves through each step, and who does what.',
    updated: '2026-11-01',
    sections: [
      {
        heading: 'Browse and compare',
        paragraphs: [
          'Tours and safaris are published with fixed departure dates, so the price you see is the price for that departure. Accommodation is published per night, with room types and rates shown for the exact dates you choose.',
          'Travel services such as airport transfers, private guides and vehicle hire are listed by enquiry. You see a starting price, then agree the details directly with the operator.',
        ],
      },
      {
        heading: 'Choose your date and send the request',
        paragraphs: [
          'Pick a departure for a tour, or your check-in and check-out dates for a stay. Enter the names and contact details of the lead guest, confirm the total, and submit the request.',
          'Submitting a request does not charge you and does not hold a date on its own. The next step depends on where you are booking from.',
        ],
      },
      {
        heading: 'Pay, or confirm with our team',
        paragraphs: [
          'Guests paying from Kenya receive an M-Pesa prompt on their phone for the amount in Kenyan shillings. Approve it on your handset and the booking is confirmed as soon as the payment is verified.',
          'Travellers paying from abroad are contacted on WhatsApp to confirm availability, answer questions and arrange payment. Nothing is charged until you have agreed the arrangements in writing.',
        ],
      },
      {
        heading: 'Before you travel',
        paragraphs: [
          'Once a booking is confirmed, the operator or host details are added to your booking so you know who is meeting you and where. For tours, we recommend confirming the pickup point the day before.',
        ],
        list: [
          'Keep your booking reference for check-in and for any changes.',
          'Carry the phone number you paid with if you booked by M-Pesa.',
          'Check the inclusions on the listing so you know what to bring and what to budget for.',
        ],
      },
      {
        heading: 'Manage, change or cancel',
        paragraphs: [
          'Your bookings are listed in your account. You can cancel a paid booking up to 48 hours before the start time and receive a full refund, or leave a review once the trip is done.',
          'Inside 48 hours, message our team and we will speak to the operator or host on your behalf. Their terms apply at that point.',
        ],
      },
    ],
  },
  {
    slug: 'booking-guide',
    path: '/booking-guide.html',
    title: 'Booking guide',
    eyebrow: 'Step by step',
    summary: 'What to have ready, how the forms work, and what happens after you press the booking button.',
    updated: '2026-11-01',
    sections: [
      {
        heading: 'Have these details ready',
        list: [
          'The names of everyone travelling, as they appear on their passports or IDs.',
          'Your travel dates, and a rough idea of arrival and departure times.',
          'A phone number that can receive M-Pesa, if you are paying from Kenya.',
          'An email address for the confirmation and for the operator to reach you.',
        ],
      },
      {
        heading: 'Booking a tour or safari',
        paragraphs: [
          'Open the tour, choose one of the published departure dates, then set the number of guests. The total updates as you change the guest count, so you can see the price before you commit.',
          'Add the lead guest details and submit. If a departure is full it is not shown, so every date you can select still has space at the time of booking.',
        ],
      },
      {
        heading: 'Booking accommodation',
        paragraphs: [
          'Choose your check-in and check-out dates and the number of guests. Available room types are shown with the rate for those exact nights, so the quote already reflects weekends and longer stays.',
          'If your dates are not yet fixed, browse first and send us a message instead. We can hold an enquiry open while you decide.',
        ],
      },
      {
        heading: 'Group trips and custom itineraries',
        paragraphs: [
          'For groups larger than a single departure allows, or for a trip that mixes a safari with a few days on the coast, use the trip planner or contact us. Our team builds the itinerary with the operators and hosts who run each leg.',
        ],
      },
      {
        heading: 'After you book',
        list: [
          'You receive a booking reference — keep it for your records.',
          'The operator or host is named on the booking, along with the meeting or pickup point.',
          'Changes and cancellations are handled from your account, or by messaging our team.',
          'Reviews can be left once you have travelled, if you have an account with us.',
        ],
        note: 'Nothing is charged online for travel services booked by enquiry. You agree the price with the operator and pay them directly.',
      },
    ],
  },
  {
    slug: 'cancellation-policy',
    path: '/cancellation-policy.html',
    title: 'Cancellation policy',
    eyebrow: 'Changes and refunds',
    summary: 'When you can cancel for free, what happens closer to the date, and how refunds are paid.',
    updated: '2026-11-01',
    sections: [
      {
        heading: 'Free cancellation up to 48 hours before',
        paragraphs: [
          'A paid tour or stay can be cancelled from your account up to 48 hours before the start time and refunded in full. The 48 hours are counted against the departure time for a tour, and against check-in time for accommodation.',
        ],
      },
      {
        heading: 'Inside 48 hours',
        paragraphs: [
          'Inside the 48-hour window, message our team rather than cancelling online. We will speak to the operator or host on your behalf. Late cancellations, no-shows and partial stays are subject to the terms of the operator or host, and may not be refundable.',
        ],
      },
      {
        heading: 'If we cancel',
        paragraphs: [
          'If an operator cancels a departure, or a host cannot honour a confirmed booking, you will be offered an alternative date or a full refund. We will contact you as soon as we know, using the phone number and email on the booking.',
        ],
      },
      {
        heading: 'Refunds',
        paragraphs: [
          'Refunds are paid back to the account the payment came from, which for Kenyan bookings is M-Pesa. Once a refund is approved it enters our payout queue and is sent to the paying number; it can take a few working days to appear on your statement.',
          'Refunds are issued in Kenyan shillings for the amount originally charged. Exchange rate movements between payment and refund are not covered.',
        ],
      },
      {
        heading: 'Services booked by enquiry',
        paragraphs: [
          'Transfers, private guides, vehicle hire and other travel services are arranged directly with the operator. Cancellation terms for those are agreed with the operator at the time you confirm, and refunds are handled by them.',
        ],
      },
      {
        heading: 'Weather and wildlife',
        paragraphs: [
          'Kenyan weather can change plans. If a sea trip or game drive cannot run safely, the operator will offer an alternative date or a refund for that activity. This does not apply where an activity runs as planned and you simply choose not to take part.',
        ],
      },
    ],
  },
  {
    slug: 'privacy-policy',
    path: '/privacy-policy.html',
    title: 'Privacy policy',
    eyebrow: 'Your data',
    summary: 'What we collect when you browse, enquire or book, why we need it, and the choices you have.',
    updated: '2026-11-01',
    sections: [
      {
        heading: 'What we collect',
        list: [
          'Details you give us: your name, email address, phone number, guest names and any message you send.',
          'Booking details: the tour, stay or service, dates, guest counts, room or departure choices and the amount paid.',
          'Payment references from M-Pesa, used to confirm a payment. We never ask for, or store, your M-Pesa PIN.',
          'Basic technical information needed to run the site, such as pages requested and error reports.',
        ],
      },
      {
        heading: 'How we use it',
        paragraphs: [
          'We use your details to confirm and deliver the booking, to pass the minimum information an operator or host needs for your trip, to answer your questions, and to handle changes, cancellations and refunds.',
          'We also use aggregated, non-identifying data to understand which destinations and experiences guests are interested in. We do not sell personal data, and we do not use it for third-party advertising.',
        ],
      },
      {
        heading: 'Who sees your details',
        paragraphs: [
          'The operator or host you book with receives the guest names, dates and contact details needed to deliver the trip. Our team sees the same details in order to support you.',
          'Payment processing is handled by our mobile money provider. Where an email notification is required, a mail delivery service may process the message contents on our behalf.',
        ],
      },
      {
        heading: 'Cookies and local storage',
        paragraphs: [
          'We use your browser’s local storage for two preferences: the language you choose and the currency you view prices in. These stay in your browser and are not shared with anyone else.',
          'Session cookies keep you signed in to your account or the partner dashboard. Clearing them signs you out.',
        ],
      },
      {
        heading: 'Keeping data and your rights',
        paragraphs: [
          'Booking and payment records are kept for as long as is needed for accounting, dispute handling and legal obligations. Marketing messages are only sent where you have asked for them.',
          'Under the Kenya Data Protection Act, 2019, you can ask to see the personal data we hold about you, ask for it to be corrected, or ask for it to be deleted where we are not required to keep it.',
        ],
      },
      {
        heading: 'Contact us about privacy',
        paragraphs: [
          'Questions about this policy, or a request about your data, can be sent through the contact form or by phone. We aim to respond within a few working days and will always confirm who we are before sharing account information.',
        ],
      },
    ],
  },
  {
    slug: 'terms-and-conditions',
    path: '/terms.html',
    title: 'Terms & conditions',
    eyebrow: 'The agreement',
    summary: 'The basis on which the marketplace lists experiences and accommodation, and the terms that apply when you book.',
    updated: '2026-11-01',
    sections: [
      {
        heading: 'About the marketplace',
        paragraphs: [
          'Kenya Tours & Marketplace is a booking platform. Tours, safaris, travel services and accommodation are delivered by independent licensed operators and hosts who list here; we handle discovery, booking and payment for the listings that are bookable online.',
          'When you book, you enter into a contract with the operator or host for the experience itself, alongside these terms for the use of the platform.',
        ],
      },
      {
        heading: 'Accounts',
        paragraphs: [
          'You are responsible for the accuracy of the details on your account and for keeping your password private. Partner accounts are for the business that created them and must not be shared.',
          'We may suspend an account that is used fraudulently, to abuse reviews, or to publish misleading listings.',
        ],
      },
      {
        heading: 'Prices and payment',
        paragraphs: [
          'Prices are published in Kenyan shillings. Other currencies are shown for guidance and are converted from the shilling price; the amount settled is always the shilling amount.',
          'Bookable tours and stays are paid by M-Pesa in Kenya, or arranged with our team for international travellers. Travel services listed by enquiry are paid directly to the operator under the terms you agree with them.',
        ],
      },
      {
        heading: 'Cancellations and refunds',
        paragraphs: [
          'Paid bookings can be cancelled for a full refund up to 48 hours before the start time. Inside 48 hours the terms of the operator or host apply. Full details are set out in the cancellation policy.',
        ],
      },
      {
        heading: 'Listings and availability',
        paragraphs: [
          'Operators and hosts are responsible for the accuracy of their listings, for holding the licences their activity requires, and for delivering what they publish. Listings are reviewed before they go live, and reported inaccuracies are investigated.',
          'Availability shown on the site reflects what has been published. Where a confirmation cannot be honoured, we will offer an alternative or a full refund.',
        ],
      },
      {
        heading: 'Reviews and content',
        paragraphs: [
          'Reviews may only be left by guests who travelled, and must describe their own experience. We remove reviews that are abusive, contain personal data, or are not genuine.',
          'Photographs and descriptions published on the site remain the property of their owners and may not be reused without permission.',
        ],
      },
      {
        heading: 'Liability and governing law',
        paragraphs: [
          'We take reasonable care in selecting the partners we list, but we are not the provider of the experience. Operators and hosts are responsible for the safety and delivery of their trips, and we recommend travel insurance that covers your activities.',
          'These terms are governed by the laws of Kenya, and disputes are subject to the jurisdiction of the Kenyan courts. We may update these terms; the date at the top of this page shows the current version.',
        ],
      },
    ],
  },
];

export function findSupportPage(pathname) {
  return SUPPORT_PAGES.find((page) => page.path === pathname) || null;
}
