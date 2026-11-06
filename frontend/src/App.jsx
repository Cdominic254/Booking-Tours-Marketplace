import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { getErrorMessage, whatsappUrl } from './utils.js';
import SmartTripPlanner from './SmartTripPlanner.jsx';
import {
  AdminDashboardPage,
  AdminActivityDashboardPage,
  AdminLoginPage,
  VendorDashboardPage,
  VendorLoginPage,
  VendorRegistrationPage,
} from './PortalPages.jsx';

const DhowModel = lazy(() => import('./DhowModel.jsx'));

const primaryLinks = [
  ['/index.html', 'Home'],
  ['/tours.html', 'Tours'],
  ['/booking.html', 'Plan your trip'],
  ['/contact.html', 'Contact'],
  ['/about-lamu.html', 'About Lamu'],
];
const legacyTourSlugs = ['dhow', 'old-town', 'sandbank', 'fishing', 'cultural', 'water-sports', 'day-trips'];
const fallbackImage = '/images/Spiritedpursuit_leelitumbe-106_lamu_kenya.webp';
const emptyCatalogue = { tours: [], properties: [], destinations: [] };

function imageUrl(url) {
  if (!url || !/^(https?:\/\/|\/?images\/|\/?pictures\/)/i.test(url) || url.split('/').includes('..')) {
    return fallbackImage;
  }
  return url.startsWith('http') ? url : `/${url.replace(/^\/+/, '')}`;
}

function formatPrice(amount, currency) {
  const code = currency.code in currency.rates ? currency.code : 'KES';
  return new Intl.NumberFormat(document.documentElement.lang === 'sw' ? 'sw-KE' : 'en-KE', {
    style: 'currency',
    currency: code,
    maximumFractionDigits: code === 'KES' ? 0 : 2,
  }).format(amount * currency.rates[code]);
}

function formatKenyanShillings(amount) {
  return new Intl.NumberFormat(document.documentElement.lang === 'sw' ? 'sw-KE' : 'en-KE', {
    style: 'currency',
    currency: 'KES',
    maximumFractionDigits: 0,
  }).format(amount);
}

function ButtonLink({ href, children, secondary = false, className = '' }) {
  return (
    <a
      className={`inline-flex min-h-12 items-center justify-center rounded-full px-6 text-sm font-semibold transition hover:-translate-y-0.5 ${
        secondary
          ? 'border border-white/60 bg-white/10 text-white hover:bg-white hover:text-[#203b35]'
          : 'bg-[#b96e45] text-white shadow-lg shadow-[#5d3425]/15 hover:bg-[#a45d38]'
      } ${className}`}
      href={href}
    >
      {children}
    </a>
  );
}

function isCurrentNavigationLink(href, pathname) {
  return pathname === href
    || (href === '/index.html' && pathname === '/')
    || (href === '/tours.html' && pathname === '/tour-details.html');
}

function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [language, setLanguage] = useState(document.documentElement.lang === 'sw' ? 'sw' : 'en');
  const [signedIn, setSignedIn] = useState(false);
  const pathname = window.location.pathname;

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/customer/profile', { headers: { Accept: 'application/json' }, signal: controller.signal })
      .then((response) => setSignedIn(response.ok))
      .catch((error) => {
        if (error.name !== 'AbortError') setSignedIn(false);
      });
    return () => controller.abort();
  }, []);

  function toggleLanguage() {
    const nextLanguage = language === 'en' ? 'sw' : 'en';
    window.setLamuLanguage?.(nextLanguage);
    setLanguage(nextLanguage);
  }

  return (
    <header className="relative z-20 border-b border-[#e9e5db] bg-[#fbfaf6] shadow-sm shadow-sky-950/5">
      <div className="mx-auto grid max-w-7xl grid-cols-[1fr_auto] items-center gap-x-4 gap-y-3 px-5 py-4 sm:px-8">
        <a className="brand-lockup flex shrink-0 items-center gap-3 sm:gap-4" href="/index.html" aria-label="Lamu Tours — island experiences in Kenya">
          <img className="brand-mark h-16 w-16 sm:h-20 sm:w-20" src="/logo.svg" alt="" />
          <span className="flex flex-col">
            <span className="brand-name text-3xl font-bold tracking-tight text-[#203b35] sm:text-4xl">Lamu Tours</span>
            <span className="brand-tagline text-[0.68rem] font-bold uppercase tracking-[0.16em] text-[#52718a] sm:text-sm">Island experiences · Kenya</span>
          </span>
        </a>
        <div className="flex items-center justify-self-end gap-2 sm:gap-3 max-[480px]:col-span-2 max-[480px]:w-full max-[480px]:justify-end">
          <a
            className="rounded-full bg-[#203b35] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#31554b]"
            href={signedIn ? '/my-bookings' : '/login.html'}
          >
            {signedIn ? 'My account' : 'Sign in'}
          </a>
          <button
            className="order-last inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-[#dedbd2] px-3 py-2 text-sm font-semibold text-[#52615b] hover:bg-[#eeeee6]"
            data-language-toggle
            type="button"
            aria-label={language === 'en' ? 'Switch to Kiswahili' : 'Switch to English'}
            aria-pressed={language === 'sw'}
            title={language === 'en' ? 'Switch to Kiswahili' : 'Switch to English'}
            onClick={toggleLanguage}
          >
            <svg aria-hidden="true" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 5h9M8.5 3v2m3 0c-.8 4-3.2 7-7.5 9" />
              <path d="M6 9c1.2 1.8 2.8 3.2 5 4.2M14 19l3.2-8 3.3 8m-5.4-2h4.3" />
            </svg>
            <span>{language === 'en' ? 'SW' : 'EN'}</span>
          </button>
          <button
            className="order-first rounded-lg border border-[#dedbd2] px-3 py-2 text-sm font-semibold text-[#203b35] lg:hidden"
            type="button"
            aria-expanded={menuOpen}
            aria-controls="primary-navigation"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? 'Close' : 'Menu'}
          </button>
        </div>
        <nav
          id="primary-navigation"
          className={`${menuOpen ? 'absolute inset-x-0 top-full flex flex-col border-b border-[#e9e5db] bg-[#fbfaf6] p-4 shadow-lg' : 'hidden'} col-span-2 items-center gap-2 lg:static lg:flex lg:flex-row lg:justify-center lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none`}
          aria-label="Main navigation"
        >
          {primaryLinks.map(([href, label]) => (
            <a
              className={`rounded-full px-3 py-2 text-sm transition ${isCurrentNavigationLink(href, pathname)
                ? 'bg-[#eeeee6] font-bold text-[#203b35]'
                : 'font-medium text-[#52615b] hover:bg-[#eeeee6] hover:text-[#203b35]'}`}
              href={href}
              key={href}
              aria-current={isCurrentNavigationLink(href, pathname) ? 'page' : undefined}
              onClick={() => setMenuOpen(false)}
            >
              {label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="mt-20 bg-[#203b35] text-[#e8eee9]">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-12 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <a className="brand-lockup flex items-center gap-3 text-white" href="/index.html" aria-label="Lamu Tours home">
            <img className="brand-mark h-12 w-12" src="/logo.svg" alt="" />
            <span className="flex flex-col">
              <span className="brand-name text-xl font-bold text-white">Lamu Tours</span>
              <span className="brand-tagline text-[0.6rem] font-bold uppercase tracking-[0.17em] text-[#8de6e4]">Island experiences · Kenya</span>
            </span>
          </a>
          <p className="mt-4 max-w-sm text-sm leading-6 text-[#c4d0c9]">
            Find the coast through local eyes: unhurried dhow sails, storied streets, and stays with a sense of place.
          </p>
        </div>
        <div>
          <h2 className="font-semibold text-white">Explore</h2>
          <div className="mt-4 flex flex-col gap-3 text-sm text-[#c4d0c9]">
            <a className="hover:text-white" href="/tours.html">Island tours</a>
            <a className="hover:text-white" href="/booking.html">Plan your trip</a>
            <a className="hover:text-white" href="/about-lamu.html">About Lamu</a>
            <a className="hover:text-white" href="/vendor/login">Vendor portal</a>
          </div>
        </div>
        <div>
          <h2 className="font-semibold text-white">Get in touch</h2>
          <div className="mt-4 flex flex-col gap-3 text-sm text-[#c4d0c9]">
            <a className="hover:text-white" href="/contact.html">Contact our team</a>
            <a className="hover:text-white" href="mailto:info@lamutours.com">info@lamutours.com</a>
            <a className="hover:text-white" href="mailto:cdominic.cm@gmail.com">cdominic.cm@gmail.com</a>
            <a className="hover:text-white" href="mailto:justerkarendi.carlos@gmail.com">justerkarendi.carlos@gmail.com</a>
            <a className="hover:text-white" href="tel:0704143718">0704143718</a>
            <span>Lamu Island, Kenya</span>
          </div>
        </div>
      </div>
      <div className="border-t border-white/10 px-5 py-5 text-center text-xs text-[#c4d0c9]">
        © 2026 Lamu Tours &amp; Booking Agency. All rights reserved.
      </div>
    </footer>
  );
}

function PageShell({ children }) {
  return (
    <>
      <a className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-full focus:bg-white focus:px-5 focus:py-3 focus:font-semibold focus:text-[#203b35] focus:shadow-xl" href="#main-content">
        Skip to main content
      </a>
      <Header />
      <main id="main-content" tabIndex={-1}>{children}</main>
      <Footer />
      <FloatingWhatsApp />
    </>
  );
}

function FloatingWhatsApp() {
  const [phone, setPhone] = useState(document.documentElement.dataset.whatsappPhone || '');
  const message = "Hello, I'm planning a trip to Lamu and would like some information.";

  useEffect(() => {
    const updatePhone = () => setPhone(document.documentElement.dataset.whatsappPhone || '');
    document.addEventListener('lamu-catalogue-ready', updatePhone);
    updatePhone();
    return () => document.removeEventListener('lamu-catalogue-ready', updatePhone);
  }, []);

  return (
    <a
      className="fixed bottom-5 right-5 z-50 inline-flex min-h-14 items-center gap-3 rounded-full bg-[#16833b] px-4 text-sm font-bold text-white shadow-xl shadow-slate-950/25 transition hover:-translate-y-1 hover:bg-[#116b30] focus-visible:outline-white sm:bottom-7 sm:right-7"
      href={whatsappUrl(message, phone)}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Chat with Lamu Tours on WhatsApp (opens in a new tab)"
      title="Chat with us on WhatsApp"
    >
      <svg aria-hidden="true" className="h-7 w-7 shrink-0" viewBox="0 0 32 32" fill="currentColor">
        <path d="M16.04 3.2A12.75 12.75 0 0 0 5.11 22.52L3.42 28.7l6.33-1.66A12.78 12.78 0 1 0 16.04 3.2Zm0 23.24c-2 0-3.96-.54-5.67-1.56l-.4-.24-3.76.99 1-3.66-.27-.42a10.4 10.4 0 1 1 9.1 4.89Zm5.71-7.8c-.31-.16-1.84-.91-2.13-1.01-.28-.1-.49-.16-.7.16-.2.31-.8 1.01-.98 1.22-.18.2-.36.23-.67.08-.31-.16-1.3-.48-2.48-1.53-.92-.82-1.54-1.83-1.72-2.14-.18-.31-.02-.48.14-.64.14-.14.31-.36.46-.54.16-.18.2-.31.31-.52.1-.21.05-.39-.03-.54-.08-.16-.7-1.69-.96-2.31-.25-.61-.51-.52-.7-.53h-.6c-.21 0-.54.08-.82.39-.28.31-1.07 1.04-1.07 2.53s1.1 2.94 1.25 3.14c.15.21 2.15 3.29 5.2 4.61.72.31 1.28.5 1.72.64.72.23 1.37.2 1.89.12.58-.09 1.84-.75 2.1-1.48.26-.72.26-1.35.18-1.48-.08-.13-.28-.21-.59-.36Z" />
      </svg>
      <span className="hidden sm:inline">Chat with us</span>
    </a>
  );
}

function SectionHeading({ eyebrow, title, description, centered = false }) {
  return (
    <div className={`mb-8 ${centered ? 'mx-auto max-w-2xl text-center' : 'max-w-2xl'}`}>
      {eyebrow && <p className="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">{eyebrow}</p>}
      <h2 className="display-font text-3xl leading-tight text-[#203b35] sm:text-4xl">{title}</h2>
      {description && <p className="mt-4 leading-7 text-[#52615b]">{description}</p>}
    </div>
  );
}

function LoadingState({ error, onRetry }) {
  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800" role="alert">
        <p>{error}</p>
        <button className="action-button mt-3" type="button" onClick={onRetry}>Try again</button>
      </div>
    );
  }
  return <p className="py-8 text-center text-[#52615b]" role="status">Loading island experiences…</p>;
}

function TourCard({ tour, currency }) {
  return (
    <article className="tour-card overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-xl">
      <a href={`/tour-details.html?id=${encodeURIComponent(tour.slug)}`} aria-label={`View ${tour.name}`}>
        <img className="h-56 w-full object-cover" src={imageUrl(tour.image_url)} alt={tour.name} loading="lazy" />
      </a>
      <div className="p-5">
        <p className="mb-2 text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{tour.category || 'Island experiences'}</p>
        <div className="flex items-start justify-between gap-3">
          <h3 className="display-font text-2xl text-[#203b35]">{tour.name}</h3>
          <span className="shrink-0 rounded-full bg-[#f3eee6] px-3 py-1 text-xs font-semibold text-[#735744]">{tour.duration}</span>
        </div>
        <p className="mt-3 line-clamp-3 min-h-[4.5rem] text-sm leading-6 text-[#52615b]">{tour.description}</p>
        <div className="mt-5 flex items-center justify-between gap-3 border-t border-[#efede7] pt-4">
          <p className="text-sm text-[#52615b]">
            From <strong className="text-base text-[#203b35]">{formatPrice(tour.price, currency)}</strong>
            <span className="block text-xs">per guest</span>
          </p>
          <a className="rounded-full bg-[#203b35] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#31554b]" href={`/tour-details.html?id=${encodeURIComponent(tour.slug)}`}>
            Discover this tour
          </a>
        </div>
      </div>
    </article>
  );
}

function PropertyCard({ property, currency }) {
  return (
    <article className="stay-card overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm">
      <img className="h-52 w-full object-cover" src={imageUrl(property.image_url)} alt={property.name} loading="lazy" />
      <div className="p-5">
        <p className="text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{property.property_type} · {property.location}</p>
        <h3 className="display-font mt-2 text-2xl text-[#203b35]">{property.name}</h3>
        <p className="mt-2 text-sm text-[#52615b]">{property.guests} guests · {formatPrice(property.price_per_night, currency)} per night</p>
        {property.description && <p className="mt-3 line-clamp-2 text-sm leading-6 text-[#52615b]">{property.description}</p>}
        <a className="mt-4 inline-flex rounded-full border border-[#203b35] px-4 py-2.5 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" href={`/booking.html?stay=${encodeURIComponent(property.slug)}&guests=${property.guests}`}>
          Ask us about this stay
        </a>
        <details className="mt-5 border-t border-[#efede7] pt-4">
          <summary className="cursor-pointer text-sm font-semibold text-[#203b35]">Guest reviews</summary>
          <ReviewPanel targetId={property.slug} targetType="property" readOnly />
        </details>
      </div>
    </article>
  );
}

function ReviewPanel({ targetType, targetId, readOnly = false }) {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ target_type: targetType, target_id: targetId });
    fetch(`/reviews?${query}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Reviews could not be loaded (HTTP ${response.status}).`);
        return response.json();
      })
      .then(({ reviews: loadedReviews }) => {
        setReviews(loadedReviews);
        setError('');
      })
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') setError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [targetId, targetType]);

  async function submitReview(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    data.target_type = targetType;
    data.target_id = targetId;
    setStatus('');
    try {
      const response = await fetch('/review-submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Your review could not be published.');
      form.reset();
      setReviews((current) => [result.review, ...current]);
      setStatus('Your review was published.');
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  return (
    <div className="mt-4">
      {loading && <p className="text-sm text-[#52615b]" role="status">Loading reviews…</p>}
      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p>}
      {!loading && !error && reviews.length === 0 && <p className="text-sm text-[#52615b]">{readOnly ? 'No guest reviews yet.' : 'No reviews yet. Be the first to share your experience.'}</p>}
      <div className="mt-3 space-y-3">
        {reviews.map((review) => (
          <article className="rounded-xl bg-[#f5f3ed] p-3" key={review.id}>
            <p className="text-sm text-[#b96e45]" aria-label={`${review.rating} out of 5 stars`}>
              <span aria-hidden="true">{'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)}</span>
              <span className="ml-2 text-xs font-semibold text-[#52615b]">{review.rating}/5</span>
            </p>
            <p className="mt-1 text-sm leading-5 text-[#52615b]">{review.comment}</p>
            <p className="mt-2 text-xs font-semibold text-[#203b35]">{review.reviewer_name}</p>
          </article>
        ))}
      </div>
      {!readOnly && <form className="mt-4 space-y-3" onSubmit={submitReview}>
        <label className="block"><span className="field-label">Your name</span><input className="field" name="reviewer_name" required /></label>
        <label className="block"><span className="field-label">Email address</span><input className="field" name="reviewer_email" type="email" required /></label>
        <label className="block"><span className="field-label">Rating</span><select className="field" name="rating" required><option value="">Choose a rating</option>{[5, 4, 3, 2, 1].map((rating) => <option key={rating} value={rating}>{rating} {rating === 1 ? 'star' : 'stars'}</option>)}</select></label>
        <label className="block"><span className="field-label">Your review</span><textarea className="field min-h-20 resize-y" name="comment" required /></label>
        {status && <p className="text-sm text-[#52615b]" role="status">{status}</p>}
        <button className="rounded-full bg-[#203b35] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#31554b]" type="submit">Publish review</button>
      </form>}
    </div>
  );
}

function HomePage({ catalogue, loading, error, retry, currency }) {
  const [location, setLocation] = useState('');
  const [guests, setGuests] = useState('');
  const [propertyType, setPropertyType] = useState('');
  const visibleProperties = catalogue.properties.filter((property) => {
    const matchesLocation = !location || `${property.location} ${property.name}`.toLowerCase().includes(location.toLowerCase());
    const matchesGuests = !guests || property.guests >= Number(guests);
    const matchesType = !propertyType || property.property_type.toLowerCase() === propertyType;
    return matchesLocation && matchesGuests && matchesType;
  });

  return (
    <PageShell>
      <section className="coast-hero relative isolate min-h-[590px] overflow-hidden bg-[#203b35] sm:min-h-[650px]">
        <img className="absolute inset-0 -z-20 h-full w-full object-cover" src="/pictures/187168867.jpg" alt="" />
        <div className="image-overlay absolute inset-0 -z-10" />
        <Suspense fallback={null}><DhowModel /></Suspense>
        <div className="mx-auto flex min-h-[590px] max-w-7xl items-center px-5 py-20 sm:min-h-[650px] sm:px-8">
          <div className="hero-copy max-w-2xl text-white">
            <p className="mb-5 text-sm font-bold uppercase tracking-[0.24em] text-[#f1b28b]">An island off the beaten tide · Kenya</p>
            <h1 className="display-font text-5xl leading-[1.05] sm:text-7xl">Let the tides lead you to Lamu.</h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-white/85">
              Follow the dhow routes, wander centuries-old Swahili lanes, and let the Indian Ocean set the pace.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <ButtonLink href="/tours.html">Find your island experience</ButtonLink>
              <ButtonLink href="/about-lamu.html" secondary>Get to know Lamu</ButtonLink>
            </div>
          </div>
        </div>
        <div className="absolute bottom-5 right-5 hidden max-w-xs rounded-2xl border border-white/25 bg-[#203b35]/65 p-4 text-sm text-white backdrop-blur sm:block">
          <span className="block font-semibold">Come for the coastline. Stay for the feeling.</span>
          <span className="mt-1 block text-white/75">Ocean air, Swahili heritage, and a welcome that feels like yours.</span>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-20">
        <SectionHeading
          eyebrow="Make it your own"
          title="Make room for a different kind of getaway."
          description="Trade the rush for dhow sails, old-town stories, and slow mornings beside the sea. Start with the experience that feels most like you."
        />
        <div className="grid gap-5 md:grid-cols-3">
          {[
            ['01', 'Walk through living history', 'Follow winding lanes, carved doorways, and the stories that make Lamu Old Town unforgettable.', '/about-lamu.html'],
            ['02', 'Let the sea set the pace', 'Step aboard a traditional dhow and discover island channels, open water, and sandy shores.', '/tours.html'],
            ['03', 'Wake up by the water', 'Find a welcoming guest house, a quiet villa, or a home base for longer island days.', '#places-to-stay'],
          ].map(([number, title, description, href]) => (
            <a className={`feature-card feature-card-${number} rounded-2xl border border-[#e9e5db] bg-white p-6 transition hover:border-[#c98d6b] hover:shadow-lg`} href={href} key={number}>
              <span className="text-sm font-bold text-[#b96e45]">{number}</span>
              <h3 className="display-font mt-5 text-2xl text-[#203b35]">{title}</h3>
              <p className="mt-3 leading-6 text-[#52615b]">{description}</p>
            </a>
          ))}
        </div>
      </section>

      <section className="coast-gallery-wrap px-5 pb-16 sm:px-8 sm:pb-20">
        <div className="coast-gallery mx-auto grid max-w-7xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ['/pictures/187168867.jpg', 'Turquoise coastal waters', 'Blue-water days'],
            ['/images/IMG_2026-03-23-17-36-36-712.jpg', 'Traditional dhow boats on the water', 'Made for the sea'],
            ['/pictures/426299433.jpg', 'Island coastline in Lamu', 'Find your horizon'],
            ['/pictures/552015001.jpg', 'Lamu waterfront scene', 'A life by the coast'],
          ].map(([src, alt, caption]) => (
            <figure className="coast-gallery-card group relative overflow-hidden rounded-2xl" key={src}>
              <img className="h-56 w-full object-cover transition duration-500 group-hover:scale-105" src={src} alt={alt} loading="lazy" />
              <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#06385f]/90 to-transparent px-4 pb-4 pt-12 text-sm font-semibold text-white">{caption}</figcaption>
            </figure>
          ))}
        </div>
      </section>

      <section className="bg-[#efeee7] px-5 py-16 sm:px-8 sm:py-20">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <SectionHeading eyebrow="Go at your own pace" title="The best island days are never hurried." />
            <ButtonLink className="mb-8 self-start" href="/tours.html">Explore every experience →</ButtonLink>
          </div>
          {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
            <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {catalogue.tours.slice(0, 3).map((tour) => <TourCard currency={currency} key={tour.slug} tour={tour} />)}
              {catalogue.tours.length === 0 && <p className="text-[#52615b]">New island experiences are on the way. Check back soon.</p>}
            </div>
          )}
        </div>
      </section>

      {catalogue.destinations.length > 0 && (
        <section className="bg-[#efeee7] px-5 py-16 sm:px-8 sm:py-20">
          <div className="mx-auto max-w-7xl">
            <SectionHeading
              eyebrow="A coast of many moods"
              title="Find the place that feels like yours."
              description="From lively old-town lanes to quiet island shores, explore Lamu’s neighborhoods and discover what makes each one special."
            />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {catalogue.destinations.map((destination) => (
                <article className="destination-card overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm" key={destination.slug}>
                  <img className="h-48 w-full object-cover" src={imageUrl(destination.image_url)} alt={destination.name} loading="lazy" />
                  <div className="p-5">
                    <h3 className="display-font text-2xl text-[#203b35]">{destination.name}</h3>
                    <p className="mt-2 min-h-12 text-sm leading-6 text-[#52615b]">{destination.description}</p>
                    <a
                      className="action-link mt-4"
                      href="#places-to-stay"
                      onClick={() => setLocation(destination.search_location)}
                    >
                      Find stays nearby →
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      <section id="places-to-stay" className="mx-auto max-w-7xl scroll-mt-8 px-5 py-16 sm:px-8 sm:py-20">
        <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <SectionHeading
            eyebrow="Settle into island life"
            title="A welcoming place to call your own."
            description="Search Lamu stays by neighborhood, guest count, and style. Find a calm home base for your days by the coast."
          />
          <form className="mb-8 grid gap-3 rounded-2xl border border-[#e9e5db] bg-white p-4 sm:grid-cols-2 lg:grid-cols-[1fr_9rem_9rem_auto]" onSubmit={(event) => event.preventDefault()}>
            <label>
              <span className="field-label">Area or stay</span>
              <input className="field" value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Try Shela, Manda, or Old Town" />
            </label>
            <label>
              <span className="field-label">Guests</span>
              <select className="field" value={guests} onChange={(event) => setGuests(event.target.value)}>
                <option value="">Any number</option>
                {[1, 2, 3, 4, 5, 6].map((count) => <option key={count} value={count}>{count} {count === 1 ? 'guest' : 'guests'}</option>)}
              </select>
            </label>
            <label>
              <span className="field-label">Stay type</span>
              <select className="field" value={propertyType} onChange={(event) => setPropertyType(event.target.value)}>
                <option value="">Any type</option>
                {['hotel', 'home', 'guest house', 'villa'].map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
            </label>
            <button className="self-end rounded-full bg-[#203b35] px-5 py-3 font-semibold text-white hover:bg-[#31554b]" type="submit">Find a stay</button>
          </form>
        </div>
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {visibleProperties.slice(0, 3).map((property) => <PropertyCard currency={currency} key={property.slug} property={property} />)}
            {visibleProperties.length === 0 &&             <p className="text-[#52615b]">We couldn’t find a stay with that combination. Try another neighborhood or a smaller guest count.</p>}
            {visibleProperties.length > 3 &&             <a className="flex min-h-56 items-center justify-center rounded-2xl border border-dashed border-[#c8c9be] font-semibold text-[#203b35] hover:bg-white" href="/booking.html">Looking for something else? Ask our local team →</a>}
          </div>
        )}
      </section>

      <section className="mx-auto max-w-7xl px-5 pb-20 sm:px-8">
        <div className="overflow-hidden rounded-3xl bg-[#203b35] px-6 py-12 text-white sm:px-12 sm:py-16">
          <div className="max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#f1b28b]">Your island story starts here</p>
            <h2 className="display-font mt-4 text-4xl sm:text-5xl">Let Lamu be more than a place on the map.</h2>
            <p className="mt-4 leading-7 text-white/75">Tell us what you’re drawn to—sailing, Swahili heritage, or a slower few days by the sea—and take the first step toward your island escape.</p>
            <ButtonLink className="mt-7" href="/booking.html">Start planning your escape</ButtonLink>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function ToursPage({ catalogue, loading, error, retry, currency }) {
  const [category, setCategory] = useState('');
  const categories = [...new Set(catalogue.tours.map((tour) => tour.category || 'Island experiences'))].sort();
  const visibleTours = catalogue.tours.filter((tour) => !category || (tour.category || 'Island experiences') === category);

  return (
    <PageShell>
      <PageBanner eyebrow="Find your island rhythm" title="Come for the sea. Leave with a story." description="Sail in a traditional dhow, follow the old town’s hidden details, or spend a day with the coast as your guide. Find experiences led by people who know Lamu by heart." />
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <SectionHeading eyebrow="Made memorable by local knowledge" title="Your next Lamu story starts here." description="Find the experience that fits your pace, explore the details, and choose from published departure times." />
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
          <>
          <div className="mb-7 flex flex-wrap gap-2" aria-label="Filter tours by category">
            <button className={`rounded-full px-4 py-2 text-sm font-semibold ${category === '' ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" onClick={() => setCategory('')}>All experiences</button>
            {categories.map((item) => <button className={`rounded-full px-4 py-2 text-sm font-semibold ${category === item ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" key={item} onClick={() => setCategory(item)}>{item}</button>)}
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {visibleTours.map((tour) => <TourCard currency={currency} key={tour.slug} tour={tour} />)}
            {catalogue.tours.length === 0 && <p className="text-[#52615b]">Tours are being added. Please check back soon.</p>}
            {catalogue.tours.length > 0 && visibleTours.length === 0 && <p className="text-[#52615b]">No experiences are currently listed in this category.</p>}
          </div>
          </>
        )}
      </section>
    </PageShell>
  );
}

function PageBanner({ eyebrow, title, description }) {
  return (
    <section className="bg-[#203b35] px-5 py-16 text-white sm:px-8 sm:py-24">
      <div className="mx-auto max-w-7xl">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#f1b28b]">{eyebrow}</p>
        <h1 className="display-font mt-4 max-w-4xl text-4xl leading-tight sm:text-6xl">{title}</h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-white/75">{description}</p>
      </div>
    </section>
  );
}

function BookingPage({ catalogue, loading, error, retry, currency }) {
  const params = new URLSearchParams(window.location.search);
  const requestedTour = params.get('tour') || params.get('stay') || '';
  const requestedSchedule = params.get('schedule_id') || '';
  const initialGuests = params.get('guests') || '1';
  const initialCheckIn = params.get('check_in') || params.get('date') || new Date().toISOString().slice(0, 10);
  const initialCheckOut = params.get('check_out') || new Date(Date.parse(`${initialCheckIn}T00:00:00Z`) + 86400000).toISOString().slice(0, 10);
  const [selected, setSelected] = useState(requestedTour);
  const [guests, setGuests] = useState(initialGuests);
  const [schedules, setSchedules] = useState([]);
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [availabilityError, setAvailabilityError] = useState('');
  const [selectedDate, setSelectedDate] = useState(params.get('date') || '');
  const [scheduleId, setScheduleId] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [checkInDate, setCheckInDate] = useState(initialCheckIn);
  const [checkOutDate, setCheckOutDate] = useState(initialCheckOut);
  const [stayQuoteUrl, setStayQuoteUrl] = useState('');
  const [language, setLanguage] = useState(document.documentElement.lang === 'sw' ? 'sw' : 'en');
  const [travelerType, setTravelerType] = useState(currency.code === 'KES' ? 'domestic' : 'international');
  const [travelerChoiceTouched, setTravelerChoiceTouched] = useState(false);
  const allOptions = [
    ...catalogue.tours.map((tour) => ({ ...tour, kind: 'tour', price: tour.price })),
    ...catalogue.properties.map((property) => ({ ...property, kind: 'stay', price: property.price_per_night })),
  ];
  const selectedListing = allOptions.find((item) => item.slug === selected);
  const stayNights = Math.max(0, Math.round((Date.parse(`${checkOutDate}T00:00:00Z`) - Date.parse(`${checkInDate}T00:00:00Z`)) / 86400000));
  const total = selectedListing
    ? selectedListing.kind === 'stay'
      ? selectedListing.price * stayNights
      : selectedListing.price * Number(guests || 1)
    : 0;
  const errorMessage = params.get('error');
  const departureDates = [...new Set(schedules.map((item) => item.starts_at.slice(0, 10)))];
  const daySchedules = schedules.filter((item) => item.starts_at.startsWith(selectedDate));
  const selectedSchedule = daySchedules.find((item) => String(item.id) === scheduleId);

  useEffect(() => {
    function syncLanguage(event) {
      setLanguage(event.detail.language);
    }
    document.addEventListener('lamu-language-changed', syncLanguage);
    return () => document.removeEventListener('lamu-language-changed', syncLanguage);
  }, []);

  useEffect(() => {
    if (!travelerChoiceTouched) setTravelerType(currency.code === 'KES' ? 'domestic' : 'international');
  }, [currency.code, travelerChoiceTouched]);

  useEffect(() => {
    if (!selectedListing || selectedListing.kind !== 'tour') {
      setSchedules([]);
      setSelectedDate('');
      setScheduleId('');
      return undefined;
    }
    const controller = new AbortController();
    setAvailabilityLoading(true);
    setAvailabilityError('');
    fetch(`/api/tours/${encodeURIComponent(selectedListing.slug)}/availability`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Tour availability could not be loaded.');
        return result.schedules;
      })
      .then((result) => {
        setSchedules(result);
        const preferredSchedule = result.find((item) => String(item.id) === requestedSchedule)
          || result.find((item) => item.starts_at.startsWith(selectedDate))
          || result[0];
        setSelectedDate(preferredSchedule?.starts_at.slice(0, 10) || '');
        setScheduleId(preferredSchedule ? String(preferredSchedule.id) : '');
      })
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') setAvailabilityError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setAvailabilityLoading(false);
      });
    return () => controller.abort();
  }, [selected, selectedListing?.kind]);

  async function submitBooking(event) {
    event.preventDefault();
    setSubmitError('');
    const data = Object.fromEntries(new FormData(event.currentTarget));
    if (selectedListing?.kind === 'stay') {
      if (stayNights < 1) {
        setSubmitError('Choose a check-out date after check-in.');
        return;
      }
      const dateLabel = (date) => new Date(`${date}T12:00:00`).toLocaleDateString(language === 'sw' ? 'sw-KE' : 'en-KE');
      const details = String(data.message || '').trim();
      const domesticPhone = String(data.phone || '').replace(/\D/g, '').replace(/^0/, '').replace(/^254/, '');
      const contactLines = [
        `Traveler: ${data.name} (${travelerType === 'domestic' ? 'Traveling from Kenya' : `International traveler from ${data.country_of_residence}`})`,
        `Email: ${data.email}`,
        `Phone: ${travelerType === 'domestic' ? `+254${domesticPhone}` : data.international_phone}`,
      ];
      const message = language === 'sw'
        ? [
          'Habari Lamu Tours, tafadhali thibitisheni malazi haya kabla sijalipa:',
          ...contactLines,
          `Malazi: ${selectedListing.name} (${selectedListing.location})`,
          `Kuingia: ${dateLabel(checkInDate)}`,
          `Kutoka: ${dateLabel(checkOutDate)} (${stayNights} usiku)`,
          `Wageni: ${guests}`,
          `Jumla ya makadirio: ${formatKenyanShillings(total)}`,
          ...(details ? [`Maelezo: ${details}`] : []),
          'Tafadhali thibitisheni nafasi na mtumie hatua salama za malipo ya M-Pesa.',
        ].join('\n')
        : [
          'Hello Lamu Tours, please confirm this stay before I pay:',
          ...contactLines,
          `Stay: ${selectedListing.name} (${selectedListing.location})`,
          `Check-in: ${dateLabel(checkInDate)}`,
          `Check-out: ${dateLabel(checkOutDate)} (${stayNights} ${stayNights === 1 ? 'night' : 'nights'})`,
          `Guests: ${guests}`,
          `Estimated stay total: ${formatKenyanShillings(total)}`,
          ...(details ? [`Notes: ${details}`] : []),
          travelerType === 'domestic'
            ? 'Please confirm availability and share the secure M-Pesa payment steps.'
            : 'Please confirm availability and share international payment options. I understand this request does not hold the stay until confirmed.',
        ].join('\n');
      setStayQuoteUrl(whatsappUrl(message, catalogue.whatsapp_business_phone));
      return;
    }
    if (travelerType === 'international') {
      const dateLabel = selectedSchedule
        ? `${selectedSchedule.starts_at.slice(0, 10)} at ${selectedSchedule.starts_at.slice(11, 16)} Lamu time`
        : `${data.date} at ${data.time} Lamu time`;
      const details = String(data.message || '').trim();
      const message = [
        'Hello Lamu Tours, I am an international traveler and would like to arrange this booking:',
        `Name: ${data.name}`,
        `Email: ${data.email}`,
        `Country: ${data.country_of_residence}`,
        `Phone/WhatsApp: ${data.international_phone}`,
        `Experience: ${selectedListing?.name || data.tour}`,
        `Preferred departure: ${dateLabel}`,
        `Guests: ${guests}`,
        `Estimated total: ${formatKenyanShillings(total)}${currency.code !== 'KES' ? ` (approximately ${formatPrice(total, currency)})` : ''}`,
        ...(details ? [`Notes: ${details}`] : []),
        'Please confirm availability and share international payment options. I understand this request does not reserve a place until confirmed.',
      ].join('\n');
      window.open(whatsappUrl(message, catalogue.whatsapp_business_phone), '_blank', 'noopener,noreferrer');
      return;
    }
    setStayQuoteUrl('');
    setSubmitting(true);
    if (selectedListing?.kind === 'tour') data.schedule_id = scheduleId;
    try {
      const response = await fetch('/booking-confirmation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Your booking could not be submitted.');
      const emailStatus = result.email_sent ? 'sent' : 'unavailable';
      const pending = result.payment_pending ? '&pending=true' : '';
      window.location.assign(
        `/booking-confirmation.html?booking_id=${result.booking.id}&reference=${encodeURIComponent(result.payment_reference)}&email=${emailStatus}&managed=${result.managed}${pending}`
      );
    } catch (requestError) {
      setSubmitError(getErrorMessage(requestError));
      setSubmitting(false);
    }
  }

  return (
    <PageShell>
      <PageBanner
        eyebrow={selectedListing?.kind === 'stay' ? (language === 'sw' ? 'Ombi la malazi' : 'Stay enquiry') : 'A few details, then the island is closer'}
        title={selectedListing?.kind === 'stay' ? (language === 'sw' ? 'Panga kukaa kwako Lamu.' : 'Plan your stay in Lamu.') : 'Let’s bring your Lamu plans to life.'}
        description={selectedListing?.kind === 'stay' ? (language === 'sw' ? 'Chagua tarehe zako na uombe mwenyeji athibitishe nafasi kupitia WhatsApp kabla ya malipo.' : 'Choose your dates and ask the host to confirm availability on WhatsApp before payment.') : travelerType === 'domestic' ? 'Choose an experience and available departure, then confirm your booking securely with M-Pesa.' : 'Choose an experience and departure, then contact our local team to confirm availability and arrange payment.'}
      />
      <div className="mx-auto max-w-7xl px-5 pt-10 sm:px-8 sm:pt-14">
        <SmartTripPlanner tours={catalogue.tours} properties={catalogue.properties} destinations={catalogue.destinations} whatsappPhone={catalogue.whatsapp_business_phone} guests={Number(guests) || 1} />
      </div>
      <section className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div id="booking-checkout" className="rounded-3xl border border-[#e9e5db] bg-white p-6 shadow-sm sm:p-9">
          <h2 className="display-font text-3xl text-[#203b35]">{selectedListing?.kind === 'stay' ? 'Ask about your stay' : 'Make it a date with the coast.'}</h2>
          <p className="mt-2 text-sm leading-6 text-[#52615b]">{selectedListing?.kind === 'stay' ? 'Send these dates to our local team. No payment is taken until the host confirms availability.' : travelerType === 'domestic' ? 'Choose a published departure, tell us who’s coming, and approve the M-Pesa prompt sent to your Kenyan mobile number. Your booking is confirmed after payment is verified.' : 'Share your details with our local team on WhatsApp. We’ll confirm the departure and provide an international payment option.'}</p>
          {errorMessage && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{errorMessage}</p>}
          {submitError && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{submitError}</p>}
          {stayQuoteUrl && <div className="mt-5 rounded-xl bg-[#e9eee8] p-4" role="status"><p className="text-sm text-[#203b35]">Your stay request is ready. The host will confirm dates before payment.</p><a className="mt-3 inline-flex min-h-11 items-center justify-center rounded-full bg-[#177b5b] px-5 text-sm font-semibold text-white hover:bg-[#126448]" href={stayQuoteUrl} target="_blank" rel="noreferrer">{catalogue.whatsapp_business_phone ? 'Message Lamu Tours on WhatsApp' : 'Share enquiry in WhatsApp'}</a></div>}
          {loading || error ? <div className="mt-6"><LoadingState error={error} onRetry={retry} /></div> : (
            <form className="mt-7 grid gap-x-5 gap-y-5 sm:grid-cols-2" onSubmit={submitBooking}>
              <label className="sm:col-span-2">
                <span className="field-label">Tour or stay</span>
                <select className="field" name="tour" value={selected} onChange={(event) => { setSelected(event.target.value); setStayQuoteUrl(''); }} required>
                  <option value="">Choose an experience or stay</option>
                  {catalogue.tours.length > 0 && <optgroup label="Tours">{catalogue.tours.map((tour) => <option key={tour.slug} value={tour.slug}>{tour.name} — {formatKenyanShillings(tour.price)} / person</option>)}</optgroup>}
                  {catalogue.properties.length > 0 && <optgroup label="Places to stay">{catalogue.properties.map((property) => <option key={property.slug} value={property.slug}>{property.name} — {formatKenyanShillings(property.price_per_night)} / night</option>)}</optgroup>}
                </select>
              </label>
              {selectedListing && <>
                <label><span className="field-label">Full name</span><input className="field" name="name" autoComplete="name" required /></label>
                <label><span className="field-label">Email address</span><input className="field" name="email" type="email" autoComplete="email" required /></label>
                <fieldset className="rounded-2xl border border-[#d1e0e2] p-4 sm:col-span-2">
                  <legend className="px-1 text-sm font-semibold text-[#203b35]">Where are you traveling from?</legend>
                  <div className="mt-1 grid gap-3 sm:grid-cols-2">
                    <label className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm font-semibold ${travelerType === 'domestic' ? 'border-[#17617a] bg-[#e6f0f1] text-[#123b52]' : 'border-[#d1e0e2] text-[#52615b]'}`}>
                      <input className="accent-[#17617a]" type="radio" name="traveler_type" value="domestic" checked={travelerType === 'domestic'} onChange={() => { setTravelerChoiceTouched(true); setTravelerType('domestic'); }} />
                      Traveling from Kenya
                    </label>
                    <label className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm font-semibold ${travelerType === 'international' ? 'border-[#17617a] bg-[#e6f0f1] text-[#123b52]' : 'border-[#d1e0e2] text-[#52615b]'}`}>
                      <input className="accent-[#17617a]" type="radio" name="traveler_type" value="international" checked={travelerType === 'international'} onChange={() => { setTravelerChoiceTouched(true); setTravelerType('international'); }} />
                      Traveling from abroad
                    </label>
                  </div>
                </fieldset>
                {travelerType === 'domestic' ? <>
                  <label><span className="field-label">M-Pesa country code</span><input className="field" name="country_code" value="+254" readOnly aria-readonly="true" /></label>
                  <label><span className="field-label">M-Pesa phone number</span><input className="field" name="phone" type="tel" inputMode="numeric" autoComplete="tel-national" pattern="(?:0?[17][0-9]{8}|254[17][0-9]{8})" title="Enter a Kenyan mobile number, with or without the leading 0 or 254" required /></label>
                </> : <>
                  <label><span className="field-label">Country of residence</span><input className="field" name="country_of_residence" autoComplete="country-name" placeholder="For example, United Kingdom" required /></label>
                  <label><span className="field-label">Phone / WhatsApp (include country code)</span><input className="field" name="international_phone" type="tel" autoComplete="tel" placeholder="For example, +44 7700 900123" required /></label>
                </>}
                <p className="rounded-xl bg-[#e6f0f1] p-4 text-sm leading-6 text-[#365565] sm:col-span-2" role="note">
                  {travelerType === 'domestic'
                    ? 'Pay securely with an M-Pesa prompt sent to your Kenyan mobile number.'
                    : 'We’ll send your details to our team on WhatsApp to confirm availability and arrange an international payment option. Your place is not reserved until we confirm it.'}
                </p>
              </>}
              {selectedListing?.kind === 'tour' ? (
                <>
                  <label>
                    <span className="field-label">Available date</span>
                    <select className="field" value={selectedDate} onChange={(event) => {
                      const date = event.target.value;
                      setSelectedDate(date);
                      setScheduleId(String(schedules.find((item) => item.starts_at.startsWith(date))?.id || ''));
                    }} required disabled={availabilityLoading || departureDates.length === 0}>
                      <option value="">{availabilityLoading ? 'Loading dates…' : 'Choose an available date'}</option>
                      {departureDates.map((date) => <option value={date} key={date}>{new Date(`${date}T12:00:00`).toLocaleDateString(document.documentElement.lang === 'sw' ? 'sw-KE' : 'en-KE', { weekday: 'short', year: 'numeric', month: 'long', day: 'numeric' })}</option>)}
                    </select>
                  </label>
                  <label>
                    <span className="field-label">Departure time (Lamu time)</span>
                    <select className="field" value={scheduleId} onChange={(event) => setScheduleId(event.target.value)} required disabled={!daySchedules.length}>
                      <option value="">Choose a departure</option>
                      {daySchedules.map((item) => <option key={item.id} value={item.id}>{item.starts_at.slice(11, 16)} · {item.remaining} spaces left</option>)}
                    </select>
                  </label>
                  <input type="hidden" name="date" value={selectedSchedule?.starts_at.slice(0, 10) || ''} />
                  <input type="hidden" name="time" value={selectedSchedule?.starts_at.slice(11, 16) || ''} />
                  <input type="hidden" name="schedule_id" value={scheduleId} />
                  {availabilityError && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-800 sm:col-span-2" role="alert">{availabilityError}</p>}
                  {!availabilityLoading && !availabilityError && schedules.length === 0 && <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b] sm:col-span-2">No departures are available yet. Contact our team and we’ll help arrange a date.</p>}
                </>
              ) : selectedListing?.kind === 'stay' ? (
                <>
                  <label><span className="field-label">Check-in</span><input className="field" name="check_in" type="date" min={new Date().toISOString().slice(0, 10)} value={checkInDate} onChange={(event) => { setCheckInDate(event.target.value); setStayQuoteUrl(''); }} required /></label>
                  <label><span className="field-label">Check-out</span><input className="field" name="check_out" type="date" min={checkInDate} value={checkOutDate} onChange={(event) => { setCheckOutDate(event.target.value); setStayQuoteUrl(''); }} required /></label>
                </>
              ) : (
                <>
                  <label><span className="field-label">Preferred date</span><input className="field" name="date" type="date" min={new Date().toISOString().slice(0, 10)} required /></label>
                  <label><span className="field-label">Preferred time</span><input className="field" name="time" type="time" required /></label>
                </>
              )}
              <label>
                <span className="field-label">Number of guests</span>
                <input className="field" name="guests" type="number" min={selectedListing?.kind === 'tour' ? selectedListing.min_group_size : 1} max={selectedListing?.kind === 'tour' ? Math.min(selectedListing.max_group_size, selectedSchedule?.remaining || selectedListing.max_group_size) : selectedListing?.guests} value={guests} onChange={(event) => { setGuests(event.target.value); setStayQuoteUrl(''); }} required />
              </label>
              <label className="sm:col-span-2">
                <span className="field-label">Anything we should know? <span className="font-normal text-[#52615b]">(optional)</span></span>
                <textarea className="field min-h-28 resize-y" name="message" rows="4" />
              </label>
              <div className="rounded-xl bg-[#f5f3ed] p-4 sm:col-span-2">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm text-[#52615b]">Estimated total</span>
                  <strong className="text-lg text-[#203b35]">{formatKenyanShillings(total)}</strong>
                </div>
                <p className="mt-1 text-xs text-[#52615b]">{selectedListing?.kind === 'stay'
                  ? language === 'sw'
                    ? `${stayNights} usiku kwa ${formatKenyanShillings(selectedListing.price)} kwa usiku. Hakuna malipo hadi uthibitisho.`
                    : `${stayNights} ${stayNights === 1 ? 'night' : 'nights'} at ${formatKenyanShillings(selectedListing.price)} per night. No charge until confirmed.`
                  : `Charged in Kenyan shillings (KES). Tour prices are per person.${currency.code !== 'KES' ? ` Approximate total in ${currency.code}: ${formatPrice(total, currency)}.` : ''}`}</p>
              </div>
              <button className="min-h-12 rounded-full bg-[#b96e45] px-6 font-semibold text-white hover:bg-[#a45d38] disabled:opacity-50 sm:col-span-2" type="submit" disabled={submitting || (selectedListing?.kind === 'tour' && (!selectedSchedule || Number(guests) > selectedSchedule.remaining || availabilityLoading)) || (selectedListing?.kind === 'stay' && stayNights < 1)}>
                {selectedListing?.kind === 'stay'
                  ? 'Request availability on WhatsApp'
                  : travelerType === 'international'
                    ? 'Continue on WhatsApp to arrange booking'
                    : submitting ? 'Opening secure checkout…' : 'Continue to secure payment'}
              </button>
            </form>
          )}
        </div>
        <aside className="h-fit rounded-3xl bg-[#e9eee8] p-6 sm:p-7">
          <h2 className="display-font text-2xl text-[#203b35]">Need a hand?</h2>
          <p className="mt-3 text-sm leading-6 text-[#52615b]">Not sure which experience fits? Tell us what you’re looking for and our local team can help.</p>
          <ButtonLink className="mt-5" href="/contact.html">Talk to our team →</ButtonLink>
          <div className="mt-7 border-t border-[#d7dfd5] pt-6 text-sm text-[#52615b]">
            <p className="font-semibold text-[#203b35]">A note about booking</p>
            <p className="mt-2 leading-6">{selectedListing?.kind === 'stay' ? 'We’ll confirm availability with the host on WhatsApp. No payment is taken before confirmation.' : travelerType === 'domestic' ? 'Payments are requested securely through M-Pesa STK Push in Kenyan shillings. Your booking is confirmed only after Daraja verifies successful payment.' : 'International requests are sent to our team on WhatsApp. Your booking is not held until the team confirms availability and payment arrangements.'}</p>
          </div>
        </aside>
      </section>
    </PageShell>
  );
}

function AboutPage() {
  return (
    <PageShell>
      <PageBanner eyebrow="A place with a story" title="An island that asks you to slow down." description="Here, the day follows the tide. Wander, listen, and let Lamu reveal itself one sunlit street and sea breeze at a time." />
      <section className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-2 lg:items-center">
        <img className="h-[26rem] w-full rounded-3xl object-cover" src="/images/Lamu,_Kenya_(45275410485).jpeg" alt="Historic Lamu town beside the water" />
        <div>
          <SectionHeading eyebrow="Meet Lamu" title="Where living culture meets the Indian Ocean." />
          <p className="leading-7 text-[#52615b]">Off Kenya’s northern coast, Lamu is one of East Africa’s oldest and best-preserved Swahili settlements. Coral-stone buildings, intricately carved doors, and winding lanes hold traces of generations shaped by Indian Ocean trade and travel.</p>
          <p className="mt-4 leading-7 text-[#52615b]">Life here moves at a gentler pace—on foot, by dhow, and along familiar neighborhood paths. Lamu Old Town was recognized as a UNESCO World Heritage Site in 2001, and its sense of place is still part of daily life.</p>
          <ButtonLink className="mt-7" href="/tours.html">Experience Lamu with a local guide</ButtonLink>
        </div>
      </section>
      <section className="bg-[#efeee7] px-5 py-14 sm:px-8 sm:py-20">
        <div className="mx-auto max-w-7xl">
          <SectionHeading centered eyebrow="Follow your curiosity" title="Many paths. One unforgettable island." />
          <div className="grid gap-5 md:grid-cols-3">
            {[
              ['images/Lamu_Fort_Museum\'s.jpg', 'Old Town, full of stories', 'Follow the narrow lanes, pause at the museum, and look closer at the carved details of Swahili architecture.'],
              ['images/shela-lamu-kenya-01.jpg', 'Shela, where the shore opens up', 'Take the long way along the sand, feel the sea breeze, and leave a little room in the day for doing nothing.'],
              ['images/Lamu_Donkey_Sanctuary.jpg', 'A slower island rhythm', 'Discover the local traditions, familiar faces, and everyday moments that make Lamu feel like nowhere else.'],
            ].map(([image, title, description]) => (
              <article className="overflow-hidden rounded-2xl bg-white" key={title}>
                <img className="h-56 w-full object-cover" src={`/${image}`} alt={title} loading="lazy" />
                <div className="p-5">
                  <h3 className="display-font text-2xl text-[#203b35]">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#52615b]">{description}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function ContactPage() {
  const [status, setStatus] = useState({ message: '', error: false, sending: false });

  async function submitContact(event) {
    event.preventDefault();
    setStatus({ message: '', error: false, sending: true });
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    try {
      const response = await fetch('/contact-submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Your message could not be sent.');
      form.reset();
      setStatus({
        message: result.email_sent
          ? 'Thanks for getting in touch. Your message has been received.'
          : 'Your message was received, but our email notification could not be sent. Please contact us directly if your request is urgent.',
        error: false,
        sending: false,
      });
    } catch (error) {
      setStatus({ message: getErrorMessage(error), error: true, sending: false });
    }
  }

  return (
    <PageShell>
      <PageBanner eyebrow="A local team, one message away" title="Let’s make your Lamu plans easier." description="Wondering which experience suits your trip, or need help with a booking? Tell us what you’re looking for and our team will be glad to help." />
      <section className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-[0.8fr_1.2fr]">
        <div>
          <SectionHeading eyebrow="Get in touch" title="Tell us what you have in mind." description="A tour, a place to stay, a question about your plans—we’re listening. Send a note and our team will follow up." />
          <div className="rounded-2xl bg-[#e9eee8] p-6">
            <p className="font-semibold text-[#203b35]">Lamu Tours &amp; Booking Agency</p>
            <p className="mt-3 text-sm leading-6 text-[#52615b]">
              Lamu Island, Kenya<br />
              <a className="font-medium text-[#9a5534] hover:underline" href="mailto:info@lamutours.com">info@lamutours.com</a><br />
              <a className="font-medium text-[#9a5534] hover:underline" href="mailto:cdominic.cm@gmail.com">cdominic.cm@gmail.com</a><br />
              <a className="font-medium text-[#9a5534] hover:underline" href="mailto:justerkarendi.carlos@gmail.com">justerkarendi.carlos@gmail.com</a><br />
              <a className="font-medium text-[#9a5534] hover:underline" href="tel:0704143718">0704143718</a>
            </p>
          </div>
        </div>
        <form className="rounded-3xl border border-[#e9e5db] bg-white p-6 shadow-sm sm:p-9" onSubmit={submitContact}>
          <div className="grid gap-5 sm:grid-cols-2">
            <label>
              <span className="field-label">Your name</span>
              <input className="field" name="name" autoComplete="name" required />
            </label>
            <label>
              <span className="field-label">Email address</span>
              <input className="field" name="email" type="email" autoComplete="email" required />
            </label>
            <label className="sm:col-span-2">
              <span className="field-label">Subject</span>
              <input className="field" name="subject" required />
            </label>
            <label className="sm:col-span-2">
              <span className="field-label">Message</span>
              <textarea className="field min-h-36 resize-y" name="message" rows="6" required />
            </label>
          </div>
          {status.message && <p className={`mt-5 rounded-xl p-4 text-sm ${status.error ? 'bg-red-50 text-red-800' : 'bg-green-50 text-green-800'}`} role={status.error ? 'alert' : 'status'}>{status.message}</p>}
          <button className="mt-6 min-h-12 rounded-full bg-[#b96e45] px-6 font-semibold text-white hover:bg-[#a45d38] disabled:opacity-60" type="submit" disabled={status.sending}>
            {status.sending ? 'Sending…' : 'Send your message'}
          </button>
        </form>
      </section>
    </PageShell>
  );
}

function TourDetailPage({ catalogue, loading, error, retry, currency }) {
  const params = new URLSearchParams(window.location.search);
  const requestedId = params.get('id') || '';
  const slug = /^\d+$/.test(requestedId) ? legacyTourSlugs[Number(requestedId) - 1] : requestedId;
  const tour = catalogue.tours.find((item) => item.slug === slug);

  if (loading || error) {
    return <PageShell><section className="mx-auto max-w-7xl px-5 py-16 sm:px-8"><LoadingState error={error} onRetry={retry} /></section></PageShell>;
  }
  if (!tour) {
    return <PageShell><section className="mx-auto max-w-3xl px-5 py-20 text-center"><h1 className="display-font text-4xl text-[#203b35]">Tour not found</h1><p className="mt-4 text-[#52615b]">We couldn’t find that tour. Browse the current experiences to choose another.</p><ButtonLink className="mt-7" href="/tours.html">Browse tours</ButtonLink></section></PageShell>;
  }

  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
        <a className="text-sm font-semibold text-[#9a5534] hover:underline" href="/tours.html">← All tours</a>
        <div className="mt-6 grid gap-10 lg:grid-cols-[1.15fr_0.85fr]">
          <img className="max-h-[34rem] w-full rounded-3xl object-cover" src={imageUrl(tour.image_url)} alt={tour.name} />
          <div className="py-2">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">{tour.category || 'A Lamu experience'}</p>
            <h1 className="display-font mt-4 text-4xl leading-tight text-[#203b35] sm:text-5xl">{tour.name}</h1>
            <p className="mt-5 leading-7 text-[#52615b]">{tour.description}</p>
            <div className="mt-7 grid grid-cols-2 gap-4 rounded-2xl bg-[#efeee7] p-5">
              <div><span className="block text-xs text-[#52615b]">Duration</span><strong className="mt-1 block text-[#203b35]">{tour.duration}</strong></div>
              <div><span className="block text-xs text-[#52615b]">From</span><strong className="mt-1 block text-[#203b35]">{formatPrice(tour.price, currency)} / person</strong></div>
              <div><span className="block text-xs text-[#52615b]">Pickup point</span><strong className="mt-1 block text-[#203b35]">{tour.pickup_point || 'Confirmed after booking'}</strong></div>
              <div><span className="block text-xs text-[#52615b]">Group size</span><strong className="mt-1 block text-[#203b35]">{tour.min_group_size || 1}–{tour.max_group_size || 12} guests</strong></div>
            </div>
            <ButtonLink className="mt-7" href={`/booking.html?tour=${encodeURIComponent(tour.slug)}`}>Book this tour</ButtonLink>
          </div>
        </div>
        {(tour.itinerary?.length || tour.inclusions?.length || tour.exclusions?.length) > 0 && <div className="mt-12 grid gap-6 md:grid-cols-3">
          {tour.itinerary?.length > 0 && <TourDetailList title="Itinerary" items={tour.itinerary} />}
          {tour.inclusions?.length > 0 && <TourDetailList title="What's included" items={tour.inclusions} />}
          {tour.exclusions?.length > 0 && <TourDetailList title="What's not included" items={tour.exclusions} />}
        </div>}
        <section className="mt-14 border-t border-[#e9e5db] pt-10">
          <SectionHeading eyebrow="Share your experience" title="A note from a fellow traveler." description="Been on this tour? Leave a review to help other travelers choose." />
          <ReviewPanel targetId={tour.slug} targetType="tour" />
        </section>
      </section>
    </PageShell>
  );
}

function TourDetailList({ title, items }) {
  const isItinerary = title === 'Itinerary';
  const hasTimeSlots = isItinerary && items.some((item) => item.includes('|'));

  return (
    <section className="rounded-2xl border border-[#d1e0e2] bg-[#f5f3ed] p-5">
      <h2 className="display-font text-2xl text-[#203b35]">{title}</h2>
      {hasTimeSlots ? (
        <ol className="mt-5 space-y-4">
          {items.map((item, index) => {
            const [time, detail = item] = item.split('|', 2);
            const [activity, highlightText] = detail.split('; Highlights:', 2);
            return (
              <li className="relative border-l-2 border-[#b6d8dc] pb-1 pl-4 last:border-l-transparent" key={`${item}-${index}`}>
                <p className="text-xs font-extrabold uppercase tracking-wide text-[#17617a]">{time.trim()}</p>
                <p className="mt-1 text-sm font-semibold leading-6 text-[#203b35]">{activity.trim()}</p>
                {highlightText && <p className="mt-1 text-sm leading-6 text-[#52615b]"><span className="font-semibold">Highlights:</span> {highlightText.trim()}</p>}
              </li>
            );
          })}
        </ol>
      ) : (
        <ul className="mt-4 list-inside list-disc space-y-2 text-sm leading-6 text-[#52615b]">
          {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
        </ul>
      )}
    </section>
  );
}

function AuthPage({ register = false }) {
  const error = new URLSearchParams(window.location.search).get('error');
  return (
    <PageShell>
      <section className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-20">
        <div className="rounded-3xl border border-[#e9e5db] bg-white p-6 shadow-sm sm:p-10">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">Lamu Tours</p>
          <h1 className="display-font mt-3 text-4xl text-[#203b35]">{register ? 'Join the island experience.' : 'Welcome back to Lamu.'}</h1>
          <p className="mt-3 text-[#52615b]">{register ? 'Create an account to plan and manage your bookings.' : 'Sign in to continue planning your Lamu experience.'}</p>
          {error && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</p>}
          <form className="mt-7 space-y-5" action={register ? '/register' : '/login'} method="post">
            {register && <label className="block"><span className="field-label">Full name</span><input className="field" name="name" autoComplete="name" required /></label>}
            <label className="block"><span className="field-label">Email address</span><input className="field" name="email" type="email" autoComplete="email" required /></label>
            <label className="block"><span className="field-label">Password</span><input className="field" name="password" type="password" minLength={register ? 8 : undefined} autoComplete={register ? 'new-password' : 'current-password'} required /></label>
            {register && <label className="block"><span className="field-label">Confirm password</span><input className="field" name="confirm_password" type="password" minLength="8" autoComplete="new-password" required /></label>}
            <button className="min-h-12 w-full rounded-full bg-[#b96e45] px-6 font-semibold text-white hover:bg-[#a45d38]" type="submit">{register ? 'Create account' : 'Sign in'}</button>
          </form>
          <p className="mt-6 text-sm text-[#52615b]">
            {register ? 'Already have an account?' : 'New to Lamu Tours?'}{' '}
            <a className="font-semibold text-[#9a5534] hover:underline" href={register ? '/login.html' : '/register.html'}>{register ? 'Sign in' : 'Create an account'}</a>
          </p>
          {!register && <p className="mt-4 text-sm"><a className="font-semibold text-[#9a5534] underline" href="/my-bookings">View or manage your bookings</a></p>}
          <p className="mt-4 text-sm text-[#52615b]">For vendors: <a className="font-semibold text-[#9a5534] hover:underline" href="/vendor/login">Sign in</a> or <a className="font-semibold text-[#9a5534] hover:underline" href="/vendor/register">create an account</a>.</p>
        </div>
      </section>
    </PageShell>
  );
}

function ConfirmationPage() {
  const params = new URLSearchParams(window.location.search);
  const bookingId = params.get('booking_id');
  const paymentReference = params.get('reference');
  const emailStatus = params.get('email');
  const isManaged = params.get('managed') === 'true';
  const initiationUnknown = params.get('pending') === 'unknown';
  const [payment, setPayment] = useState(null);
  const [paymentError, setPaymentError] = useState('');

  useEffect(() => {
    if (!paymentReference) return undefined;
    let active = true;
    let timeout;

    async function refreshPaymentStatus() {
      try {
        const response = await fetch(`/api/payment-status/${encodeURIComponent(paymentReference)}`, {
          headers: { Accept: 'application/json' },
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Payment status could not be loaded.');
        if (!active) return;
        setPayment(result);
        setPaymentError('');
        if (!['paid', 'failed', 'cancelled'].includes(result.payment_status)) {
          timeout = window.setTimeout(refreshPaymentStatus, 5000);
        }
      } catch (requestError) {
        if (!active) return;
        setPaymentError(getErrorMessage(requestError));
        timeout = window.setTimeout(refreshPaymentStatus, 10000);
      }
    }

    refreshPaymentStatus();
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [paymentReference]);

  const paymentIsConfirmed = payment?.payment_status === 'paid';
  const paymentFailed = ['failed', 'cancelled'].includes(payment?.payment_status);

  return (
    <PageShell>
      <section className="mx-auto max-w-3xl px-5 py-16 sm:px-8 sm:py-24">
        <div className="rounded-3xl border border-[#e9e5db] bg-white p-8 text-center shadow-sm sm:p-12">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[#e9eee8] text-2xl text-[#31554b]" aria-hidden="true">✓</span>
          <h1 className="display-font mt-6 text-4xl text-[#203b35]">{paymentIsConfirmed ? 'Your booking is confirmed.' : 'Your request is in.'}</h1>
          <p className="mt-4 leading-7 text-[#52615b]">
            {paymentIsConfirmed
              ? 'Your M-Pesa payment has been verified. Thanks for booking with Lamu Tours.'
              : paymentFailed
                ? 'The M-Pesa payment was not completed and this booking was not confirmed. You can try booking again.'
                : 'We’ve received your request. Check your phone for the M-Pesa prompt and enter your PIN to pay. We’ll confirm your booking after Daraja verifies the payment.'}
          </p>
          {bookingId && <p className="mt-5 rounded-xl bg-[#f5f3ed] p-4 text-sm font-semibold text-[#203b35]">Booking reference: #{bookingId}</p>}
          {paymentReference && <p className="mt-3 text-sm text-[#52615b]" role="status">{paymentIsConfirmed ? 'Payment status: paid' : paymentFailed ? 'Payment status: not completed' : initiationUnknown ? 'We could not confirm whether the M-Pesa prompt was sent. Check your phone and payment status before trying again.' : 'Waiting for M-Pesa payment confirmation…'}</p>}
          {payment?.mpesa_receipt_number && <p className="mt-2 text-sm font-semibold text-[#31554b]">M-Pesa receipt: {payment.mpesa_receipt_number}</p>}
          {payment?.document_urls?.invoice && <a className="mt-4 inline-block rounded-full border border-[#31554b] px-4 py-2 text-sm font-semibold text-[#31554b] hover:bg-[#e9eee8]" href={payment.document_urls.invoice}>Download invoice</a>}
          {payment?.document_urls?.receipt && <a className="mt-4 ml-2 inline-block rounded-full border border-[#31554b] px-4 py-2 text-sm font-semibold text-[#31554b] hover:bg-[#e9eee8]" href={payment.document_urls.receipt}>Download receipt</a>}
          {paymentError && <p className="mt-3 text-sm text-[#8a4c2e]" role="status">{paymentError}</p>}
          {emailStatus === 'sent' && <p className="mt-4 text-sm text-[#31554b]" role="status">A confirmation email has been sent to the address you provided.</p>}
          {emailStatus === 'unavailable' && <p className="mt-4 text-sm text-[#8a4c2e]" role="status">Your booking is saved. Email delivery is not configured right now; keep your booking reference for enquiries.</p>}
          {isManaged && <p className="mt-4 text-sm text-[#52615b]"><a className="font-semibold text-[#9a5534] underline" href="/my-bookings">View or manage this booking</a></p>}
          <div className="mt-8 rounded-2xl bg-[#f5f3ed] p-5 text-left">
          <h2 className="font-semibold text-[#203b35]">And now?</h2>
            <ul className="mt-3 list-inside list-disc space-y-2 text-sm leading-6 text-[#52615b]">
              <li>Approve the M-Pesa prompt on your phone, if you have not already.</li>
              <li>Daraja will securely notify us when payment completes.</li>
              <li>Your booking status will update here automatically.</li>
            </ul>
          </div>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <ButtonLink href="/index.html">Return home</ButtonLink>
            <ButtonLink href="/tours.html" secondary className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white">Browse tours</ButtonLink>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function CustomerBookingCard({ booking, csrfToken, onChanged }) {
  const [schedules, setSchedules] = useState([]);
  const [scheduleId, setScheduleId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const canChange = ['requested', 'confirmed'].includes(booking.status);

  useEffect(() => {
    if (!booking.schedule_id || !canChange) return undefined;
    const controller = new AbortController();
    fetch(`/api/tours/${encodeURIComponent(booking.tour)}/availability`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Available departures could not be loaded.');
        return result.schedules;
      })
      .then((result) => setSchedules(result.filter((item) => item.id !== booking.schedule_id)))
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') setError(getErrorMessage(loadError));
      });
    return () => controller.abort();
  }, [booking.tour, booking.schedule_id, canChange]);

  async function mutate(action, payload) {
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`/api/customer/bookings/${booking.id}/${action}`, {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Booking could not be updated.');
      await onChanged();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="rounded-2xl border border-[#e9e5db] bg-white p-5 shadow-sm sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="display-font text-2xl text-[#203b35]">{booking.tour.replaceAll('-', ' ')}</h2><p className="mt-1 text-sm text-[#52615b]">{booking.date} at {booking.time} · {booking.guests} guest{booking.guests === 1 ? '' : 's'}</p></div>
        <span className="rounded-full bg-[#efeee7] px-3 py-1 text-sm font-semibold capitalize text-[#52615b]">{booking.status}</span>
      </div>
      <p className="mt-3 text-sm text-[#52615b]">Booking #{booking.id} · KSh {Number(booking.amount).toLocaleString(document.documentElement.lang === 'sw' ? 'sw-KE' : 'en-KE')} · Payment: {booking.payment_status}</p>
      {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p>}
      {canChange && booking.schedule_id && <div className="mt-5 flex flex-wrap items-end gap-3">
        <label className="min-w-64 flex-1"><span className="field-label">Reschedule departure</span><select className="field" value={scheduleId} onChange={(event) => setScheduleId(event.target.value)}><option value="">Choose another available time</option>{schedules.map((slot) => <option key={slot.id} value={slot.id}>{slot.starts_at.replace('T', ' ')} · {slot.remaining} spaces</option>)}</select></label>
        <button className="rounded-full border border-[#203b35] px-5 py-3 text-sm font-semibold text-[#203b35] disabled:opacity-50" type="button" disabled={busy || !scheduleId} onClick={() => mutate('reschedule', { schedule_id: Number(scheduleId) })}>Reschedule</button>
        <button className="rounded-full border border-red-200 px-5 py-3 text-sm font-semibold text-red-700 disabled:opacity-50" type="button" disabled={busy} onClick={() => { if (window.confirm('Cancel this booking? Changes are allowed only more than 48 hours before departure.')) mutate('cancel'); }}>Cancel booking</button>
      </div>}
      {canChange && <p className="mt-3 text-xs text-[#52615b]">Cancellation and rescheduling are available at least 48 hours before departure.</p>}
    </article>
  );
}

function MyBookingsPage() {
  const [profile, setProfile] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const profileResponse = await fetch('/api/customer/profile', { headers: { Accept: 'application/json' } });
      const profileResult = await profileResponse.json();
      if (!profileResponse.ok) throw new Error(profileResult.error || 'Sign in to view your bookings.');
      const bookingsResponse = await fetch('/api/customer/bookings', { headers: { Accept: 'application/json' } });
      const bookingsResult = await bookingsResponse.json();
      if (!bookingsResponse.ok) throw new Error(bookingsResult.error || 'Your bookings could not be loaded.');
      setProfile(profileResult);
      setBookings(bookingsResult.bookings);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    if (!profile?.csrf_token) return;
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/logout', {
        method: 'POST',
        headers: { Accept: 'application/json', 'X-CSRF-Token': profile.csrf_token },
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error || 'You could not be signed out. Please try again.');
      }
      window.location.assign('/index.html');
    } catch (logoutError) {
      setError(getErrorMessage(logoutError));
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <PageShell>
      <PageBanner eyebrow="Your account" title="My account and bookings." description="View your account details and manage your Lamu experiences." />
      <section className="mx-auto max-w-5xl space-y-5 px-5 py-12 sm:px-8 sm:py-16">
        {loading && <p className="text-[#52615b]" role="status">Loading your bookings…</p>}
        {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800"><p role="alert">{error}</p><a className="mt-3 inline-block font-semibold underline" href="/login.html">Sign in as a customer</a></div>}
        {profile && <section className="rounded-2xl border border-[#e9e5db] bg-white p-6 shadow-sm" aria-labelledby="account-details-heading">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 id="account-details-heading" className="display-font text-2xl text-[#203b35]">Account details</h2>
            <button className="rounded-full border border-[#dedbd2] px-4 py-2 text-sm font-semibold text-[#52615b] hover:bg-[#eeeee6] disabled:opacity-50" type="button" onClick={logout} disabled={loading}>Log out</button>
          </div>
          <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
            <div><dt className="font-semibold text-[#52615b]">Name</dt><dd className="mt-1 text-[#203b35]">{profile.customer.name}</dd></div>
            <div><dt className="font-semibold text-[#52615b]">Email</dt><dd className="mt-1 text-[#203b35]">{profile.customer.email}</dd></div>
          </dl>
        </section>}
        {!loading && !error && bookings.length === 0 && <div className="rounded-2xl bg-white p-7"><h2 className="display-font text-2xl text-[#203b35]">No bookings yet</h2><p className="mt-2 text-[#52615b]">When you book while signed in, your trips will appear here.</p><ButtonLink className="mt-5" href="/tours.html">Explore tours</ButtonLink></div>}
        {profile && bookings.map((booking) => <CustomerBookingCard key={booking.id} booking={booking} csrfToken={profile.csrf_token} onChanged={load} />)}
      </section>
    </PageShell>
  );
}

function NotFoundPage() {
  return (
    <PageShell>
      <section className="mx-auto max-w-3xl px-5 py-20 text-center sm:px-8 sm:py-28">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">404 · Page not found</p>
        <h1 className="display-font mt-4 text-4xl text-[#203b35]">This isn’t the island path you’re looking for.</h1>
        <p className="mt-4 text-[#52615b]">The page may have moved. Head home or browse the island tours instead.</p>
        <div className="mt-7 flex justify-center gap-3">
          <ButtonLink href="/index.html">Go home</ButtonLink>
          <ButtonLink href="/tours.html" secondary className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white">Browse tours</ButtonLink>
        </div>
      </section>
    </PageShell>
  );
}

export default function App() {
  const [catalogue, setCatalogue] = useState(emptyCatalogue);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [currency, setCurrency] = useState({ code: 'KES', rates: { KES: 1 } });
  const [retryCount, setRetryCount] = useState(0);
  const [, setLanguageVersion] = useState(0);
  const pathname = window.location.pathname.toLowerCase();

  useEffect(() => {
    if (pathname.startsWith('/admin') || pathname.startsWith('/vendor') || pathname === '/dashboard') return;

    const campaignSource = new URLSearchParams(window.location.search).get('utm_source');
    let referrerSource = '';
    try {
      referrerSource = document.referrer ? new URL(document.referrer).hostname : '';
    } catch {
      referrerSource = '';
    }

    let source = campaignSource || referrerSource;
    try {
      const sourceKey = 'lamu-first-touch-source';
      const firstTouchSource = window.localStorage.getItem(sourceKey);
      if (firstTouchSource) source = firstTouchSource;
      else if (source) window.localStorage.setItem(sourceKey, source);
    } catch {
      source = campaignSource || referrerSource;
    }

    fetch('/api/analytics/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ page: pathname, source }),
      keepalive: true,
    }).catch(() => {});
  }, [pathname]);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;

    const root = document.getElementById('root');
    if (!root) return undefined;

    const selector = 'main > section, main > div, .feature-card, .coast-gallery-card, .tour-card, .stay-card';
    const observer = 'IntersectionObserver' in window
      ? new IntersectionObserver((entries, currentObserver) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          currentObserver.unobserve(entry.target);
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -36px' })
      : null;

    function observeTargets(node) {
      if (!(node instanceof Element)) return;
      const targets = [];
      if (node.matches(selector)) targets.push(node);
      targets.push(...node.querySelectorAll(selector));
      targets.forEach((element, index) => {
        if (element.classList.contains('scroll-reveal')) return;
        element.classList.add('scroll-reveal');
        element.style.setProperty('--reveal-delay', `${Math.min(index, 4) * 100}ms`);
        observer?.observe(element);
      });
    }

    function revealVisibleTargets() {
      document.querySelectorAll('.motion-ready .scroll-reveal:not(.is-visible)').forEach((element) => {
        const bounds = element.getBoundingClientRect();
        if (bounds.top < window.innerHeight - 36 && bounds.bottom > 36) {
          element.classList.add('is-visible');
          observer?.unobserve(element);
        }
      });
    }

    function updateMotionVisibility() {
      const isVisible = document.visibilityState === 'visible';
      document.documentElement.classList.toggle('motion-ready', isVisible);
      if (isVisible) {
        window.requestAnimationFrame(revealVisibleTargets);
        window.setTimeout(revealVisibleTargets, 150);
      }
    }

    observeTargets(root);
    updateMotionVisibility();
    document.addEventListener('visibilitychange', updateMotionVisibility);
    if (!observer) {
      window.addEventListener('scroll', revealVisibleTargets, { passive: true });
      window.addEventListener('resize', revealVisibleTargets);
    }

    const mutations = new MutationObserver((records) => {
      records.forEach((record) => record.addedNodes.forEach((node) => {
        observeTargets(node);
        window.requestAnimationFrame(revealVisibleTargets);
        window.setTimeout(revealVisibleTargets, 150);
      }));
    });
    mutations.observe(root, { childList: true, subtree: true });

    return () => {
      mutations.disconnect();
      observer?.disconnect();
      document.removeEventListener('visibilitychange', updateMotionVisibility);
      if (!observer) {
        window.removeEventListener('scroll', revealVisibleTargets);
        window.removeEventListener('resize', revealVisibleTargets);
      }
      document.documentElement.classList.remove('motion-ready');
    };
  }, []);

  useEffect(() => {
    function refreshLocalizedValues() {
      setLanguageVersion((version) => version + 1);
    }

    document.addEventListener('lamu-language-changed', refreshLocalizedValues);
    return () => document.removeEventListener('lamu-language-changed', refreshLocalizedValues);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/catalogue', { signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(async (response) => {
        if (!response.ok) throw new Error(`The catalogue could not be loaded (HTTP ${response.status}).`);
        return response.json();
      })
      .then((data) => {
        if (!data || !Array.isArray(data.tours) || !Array.isArray(data.properties) || !Array.isArray(data.destinations)) {
          throw new Error('The catalogue returned incomplete data.');
        }
        setCatalogue(data);
        document.documentElement.dataset.whatsappPhone = data.whatsapp_business_phone || '';
        document.dispatchEvent(new Event('lamu-catalogue-ready'));
      })
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') setError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [retryCount]);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/currency', { signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Currency data could not be loaded (HTTP ${response.status}).`);
        return response.json();
      })
      .then((data) => {
        if (data.base !== 'KES' || !data.rates || data.rates.KES !== 1 || !Number.isFinite(data.rates[data.currency])) {
          throw new Error('Currency data was incomplete.');
        }
        setCurrency({ code: data.currency, rates: data.rates });
      })
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') console.warn(`${getErrorMessage(loadError)} Prices will be shown in KSh.`);
      });
    return () => controller.abort();
  }, []);

  const retry = useMemo(() => () => setRetryCount((count) => count + 1), []);

  useEffect(() => {
    const titles = {
      '/': 'Lamu Tours | Find your way to Lamu',
      '/index.html': 'Lamu Tours | Find your way to Lamu',
      '/tours.html': 'Island tours | Lamu Tours',
      '/booking.html': 'Plan your Lamu escape | Lamu Tours',
      '/about-lamu.html': 'Discover Lamu | Lamu Tours',
      '/contact.html': 'Contact us | Lamu Tours',
      '/login.html': 'Sign in | Lamu Tours',
      '/register.html': 'Create an account | Lamu Tours',
      '/tour-details.html': 'Tour details | Lamu Tours',
      '/booking-confirmation.html': 'Booking request received | Lamu Tours',
      '/my-bookings': 'My account | Lamu Tours',
      '/admin/login': 'Admin sign in | Lamu Tours',
      '/admin': 'Admin dashboard | Lamu Tours',
      '/admin/dashboard': 'Admin dashboard | Lamu Tours',
      '/dashboard': 'Bookings and messages | Lamu Tours',
      '/vendor/login': 'Vendor sign in | Lamu Tours',
      '/vendor/register': 'Vendor registration | Lamu Tours',
      '/vendor/dashboard': 'Vendor dashboard | Lamu Tours',
    };
    document.title = titles[pathname] || 'Lamu Tours & Booking Agency';
  }, [pathname]);

  if (pathname === '/admin/login') return <AdminLoginPage />;
  if (pathname === '/admin' || pathname === '/admin/dashboard') return <AdminDashboardPage />;
  if (pathname === '/dashboard') return <AdminActivityDashboardPage />;
  if (pathname === '/vendor/login') return <VendorLoginPage />;
  if (pathname === '/vendor/register') return <VendorRegistrationPage />;
  if (pathname === '/vendor/dashboard') return <VendorDashboardPage />;
  if (pathname === '/tours.html') return <ToursPage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname === '/booking.html') return <BookingPage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname === '/my-bookings') return <MyBookingsPage />;
  if (pathname === '/about-lamu.html') return <AboutPage />;
  if (pathname === '/contact.html') return <ContactPage />;
  if (pathname === '/login.html' || pathname === '/login') return <AuthPage />;
  if (pathname === '/register.html' || pathname === '/register') return <AuthPage register />;
  if (pathname === '/tour-details.html') return <TourDetailPage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname === '/booking-confirmation.html') return <ConfirmationPage />;
  if (pathname === '/' || pathname === '/index.html') return <HomePage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  return <NotFoundPage />;
}
