import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { addDaysToIsoDate, documentLanguage, formatMoney as formatPrice, formatShillings as formatKenyanShillings, getErrorMessage, numberLocale, todayInKenya, whatsappUrl } from './utils.js';
import SmartTripPlanner from './SmartTripPlanner.jsx';
import { BLOG_POSTS, blogCategories, findBlogPost } from './blog.js';
import { SUPPORT_PAGES, findSupportPage } from './support.js';
import { CATEGORIES, categoriesFor, categoryItems, findCategory } from './categories.js';
import { REGIONS, findRegion, inRegion, regionDestinations, regionHref, regionListingCounts } from './regions.js';
import { GALLERY_PHOTOS, cataloguePhotos, galleryRegions } from './gallery.js';
import { COMPARE_EVENT, COMPARE_LIMIT, clearCompare, compareHref, compareKey, isCompared, parseCompareParam, readCompare, removeCompare, replaceCompare, toggleCompare } from './compare.js';
import { clearSaved, getWishlistSnapshot, loadWishlist, removeSaved, subscribeWishlist, toggleSaved } from './wishlist.js';
import {
  AdminDashboardPage,
  AdminActivityDashboardPage,
  AdminLoginPage,
  VendorDashboardPage,
  VendorLoginPage,
  VendorRegistrationPage,
} from './PortalPages.jsx';

const primaryLinks = [
  ['/index.html', 'Home'],
  ['/properties.html', 'Properties'],
  ['/tours.html', 'Tours'],
  ['/safari-operators.html', 'Safari operators'],
  ['/destinations.html', 'Destinations'],
  ['/about-kenya.html', 'About Kenya'],
];

const secondaryLinks = [
  ['/blog.html', 'Blogs & travel guides'],
  ['/gallery.html', 'Photo gallery'],
  ['/reviews.html', 'Community reviews'],
  ['/contact.html', 'Contact us'],
  ['/faq.html', 'FAQ'],
];

// Paths that should keep a related top-level link highlighted.
const navigationAliases = {
  '/tours.html': ['/tour-details.html'],
  '/safari-operators.html': ['/operators/'],
  '/blog.html': ['/blog/'],
};
const legacyTourSlugs = ['dhow', 'old-town', 'sandbank', 'fishing', 'cultural', 'water-sports', 'day-trips'];
const fallbackImage = '/images/Spiritedpursuit_leelitumbe-106_lamu_kenya.webp';
const emptyCatalogue = { tours: [], properties: [], services: [], operators: [], destinations: [] };
const WHATSAPP_GREETING = "Hello, I'm planning a trip to Kenya and would like some information.";
const CONTACT_PHONE_DISPLAY = '0704143718';
const CONTACT_PHONE_HREF = 'tel:+254704143718';

function useWhatsAppPhone() {
  const [phone, setPhone] = useState(document.documentElement.dataset.whatsappPhone || '');

  useEffect(() => {
    const updatePhone = () => setPhone(document.documentElement.dataset.whatsappPhone || '');
    document.addEventListener('kenya-catalogue-ready', updatePhone);
    updatePhone();
    return () => document.removeEventListener('kenya-catalogue-ready', updatePhone);
  }, []);

  return phone;
}

function useSocialLinks() {
  const readLinks = () => {
    try {
      const stored = JSON.parse(document.documentElement.dataset.socialLinks || '[]');
      return Array.isArray(stored) ? stored : [];
    } catch {
      return [];
    }
  };
  const [links, setLinks] = useState(readLinks);

  useEffect(() => {
    const updateLinks = () => setLinks(readLinks());
    document.addEventListener('kenya-catalogue-ready', updateLinks);
    updateLinks();
    return () => document.removeEventListener('kenya-catalogue-ready', updateLinks);
  }, []);

  return links;
}

function useCompareSelection() {
  const [items, setItems] = useState(readCompare);

  useEffect(() => {
    const sync = () => setItems(readCompare());
    window.addEventListener(COMPARE_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(COMPARE_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  return items;
}

function useCompareMeta() {
  // Names and thumbnails for the floating tray, published with the catalogue.
  const readMeta = () => {
    try {
      const stored = JSON.parse(document.documentElement.dataset.compareMeta || '{}');
      return stored && typeof stored === 'object' ? stored : {};
    } catch {
      return {};
    }
  };
  const [meta, setMeta] = useState(readMeta);

  useEffect(() => {
    const updateMeta = () => setMeta(readMeta());
    document.addEventListener('kenya-catalogue-ready', updateMeta);
    updateMeta();
    return () => document.removeEventListener('kenya-catalogue-ready', updateMeta);
  }, []);

  return meta;
}

function CompareToggle({ type, slug, name, className = '' }) {
  const selectedItems = useCompareSelection();
  const selected = isCompared(selectedItems, type, slug);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(''), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  return (
    <div className={className}>
      <button
        aria-label={selected ? `Remove ${name} from the comparison` : `Add ${name} to the comparison`}
        aria-pressed={selected}
        className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold transition ${selected ? 'border-[#203b35] bg-[#203b35] text-white' : 'border-[#d9d3c4] bg-white text-[#203b35] hover:border-[#203b35]'}`}
        onClick={() => {
          const result = toggleCompare(type, slug);
          if (result.full) setNotice(`You can compare ${COMPARE_LIMIT} listings at once. Remove one to add another.`);
        }}
        type="button"
      >
        <span aria-hidden="true" className={`grid h-4 w-4 place-items-center rounded-[0.3rem] border text-[0.6rem] leading-none ${selected ? 'border-white bg-white text-[#203b35]' : 'border-[#bdb6a6]'}`}>
          {selected ? '✓' : ''}
        </span>
        {selected ? 'Added to compare' : 'Compare'}
      </button>
      {notice && <span className="mt-2 block text-xs font-semibold text-[#9a5534]" role="status">{notice}</span>}
    </div>
  );
}

function CompareTray() {
  const items = useCompareSelection();
  const meta = useCompareMeta();
  if (!items.length || window.location.pathname === '/compare.html') return null;

  return (
    <div className="fixed bottom-3 left-3 right-24 z-40 sm:bottom-5 sm:left-5 sm:right-auto sm:w-[24rem]">
      <div className="rounded-2xl border border-[#d9d3c4] bg-white/95 p-3 shadow-2xl shadow-slate-950/20 backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[0.65rem] font-bold uppercase tracking-[0.14em] text-[#a75f3a]">Comparing {items.length} of {COMPARE_LIMIT}</p>
          <button className="text-xs font-semibold text-[#52615b] hover:text-[#203b35]" onClick={clearCompare} type="button">Clear all</button>
        </div>
        <ul className="mt-2 flex items-start gap-2">
          {items.map((item) => {
            const listing = meta[compareKey(item)];
            return (
              <li className="min-w-0 flex-1" key={compareKey(item)}>
                <div className="relative overflow-hidden rounded-lg bg-[#efeee7]">
                  {listing?.image
                    ? <img alt="" className="h-12 w-full object-cover" loading="lazy" src={imageUrl(listing.image)} />
                    : <span className="grid h-12 w-full place-items-center text-[0.6rem] font-bold uppercase tracking-wide text-[#735744]">{item.type === 'tour' ? 'Tour' : 'Stay'}</span>}
                  <button
                    aria-label={`Remove ${listing?.name || item.slug.replace(/-/g, ' ')} from the comparison`}
                    className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-white/90 text-xs font-bold leading-none text-[#203b35] shadow-sm hover:bg-white"
                    onClick={() => removeCompare(item.type, item.slug)}
                    type="button"
                  >
                    ×
                  </button>
                </div>
                <p className="mt-1 truncate text-[0.65rem] font-semibold text-[#203b35]">{listing?.name || item.slug.replace(/-/g, ' ')}</p>
              </li>
            );
          })}
        </ul>
        <a className="mt-3 flex items-center justify-center rounded-full bg-[#203b35] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#31554b]" href={compareHref(items)}>
          Compare side by side →
        </a>
      </div>
    </div>
  );
}

function useWishlist() {
  return useSyncExternalStore(subscribeWishlist, getWishlistSnapshot);
}

function HeartIcon({ filled = false, className = 'h-5 w-5' }) {
  return (
    <svg aria-hidden="true" className={className} fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" viewBox="0 0 24 24">
      <path d="M12 20.3s-7.6-4.5-7.6-9.6a4.2 4.2 0 0 1 7.6-2.4 4.2 4.2 0 0 1 7.6 2.4c0 5.1-7.6 9.6-7.6 9.6Z" />
    </svg>
  );
}

function WishlistButton({ listingType, slug, name, className = '', variant = 'overlay' }) {
  const wishlist = useWishlist();
  const saved = wishlist.items.some((item) => item.listing_type === listingType && item.listing_slug === slug);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!error) return undefined;
    const timer = window.setTimeout(() => setError(''), 5000);
    return () => window.clearTimeout(timer);
  }, [error]);

  async function toggle() {
    setBusy(true);
    setError('');
    try {
      const result = await toggleSaved(listingType, slug);
      if (result.needsSignIn) window.location.assign('/login.html');
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setBusy(false);
    }
  }

  const label = saved ? `Remove ${name} from your wishlist` : `Save ${name} to your wishlist`;

  if (variant === 'inline') {
    return (
      <span className={`inline-flex flex-col ${className}`}>
        <button
          aria-label={label}
          aria-pressed={saved}
          className={`inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold transition disabled:opacity-60 ${saved ? 'border-[#b96e45] bg-[#b96e45] text-white hover:bg-[#a75f3a]' : 'border-[#b96e45] text-[#9a5534] hover:bg-[#fdf0e6]'}`}
          disabled={busy}
          onClick={toggle}
          type="button"
        >
          <HeartIcon className="h-4 w-4" filled={saved} />
          {saved ? 'Saved to wishlist' : 'Save to wishlist'}
        </button>
        {error && <span className="mt-2 text-xs font-semibold text-[#9a5534]" role="alert">{error}</span>}
      </span>
    );
  }

  return (
    <span className={`inline-flex items-end ${className || 'relative'}`}>
      <button
        aria-label={label}
        aria-pressed={saved}
        className={`grid h-10 w-10 place-items-center rounded-full border shadow-sm backdrop-blur transition disabled:opacity-60 ${saved ? 'border-[#b96e45] bg-[#b96e45] text-white' : 'border-white/70 bg-white/85 text-[#203b35] hover:bg-white'}`}
        disabled={busy}
        onClick={toggle}
        title={saved ? 'Saved to your wishlist' : 'Save to your wishlist'}
        type="button"
      >
        <HeartIcon filled={saved} />
      </button>
      {error && (
        <span className="absolute right-0 top-12 z-10 w-44 rounded-lg bg-white px-2 py-1.5 text-right text-[0.65rem] font-semibold text-[#9a5534] shadow-md" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}

function HeaderWishlistLink() {
  const wishlist = useWishlist();
  const count = wishlist.signedIn ? wishlist.items.length : 0;

  useEffect(() => { loadWishlist(); }, []);

  return (
    <a
      aria-label={count ? `Your wishlist, ${count} saved ${count === 1 ? 'listing' : 'listings'}` : 'Your wishlist'}
      className="site-icon-button site-wishlist-link"
      href="/wishlist.html"
      title={count ? `Wishlist · ${count} saved` : 'Wishlist'}
    >
      <HeartIcon filled={count > 0} />
      <span className="site-icon-button__label">Saved</span>
      {count > 0 && <span aria-hidden="true" className="site-wishlist-count">{count}</span>}
    </a>
  );
}

function PhoneIcon({ className = 'h-4 w-4 shrink-0' }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6.4 3.5h2.3l1.4 3.9-1.9 1.3a11.2 11.2 0 0 0 5.1 5.1l1.3-1.9 3.9 1.4v2.3a2 2 0 0 1-2.2 2A16.6 16.6 0 0 1 4.4 5.7a2 2 0 0 1 2-2.2Z" />
    </svg>
  );
}

function WhatsAppIcon({ className = 'h-4 w-4 shrink-0' }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 32 32" fill="currentColor">
      <path d="M16.04 3.2A12.75 12.75 0 0 0 5.11 22.52L3.42 28.7l6.33-1.66A12.78 12.78 0 1 0 16.04 3.2Zm0 23.24c-2 0-3.96-.54-5.67-1.56l-.4-.24-3.76.99 1-3.66-.27-.42a10.4 10.4 0 1 1 9.1 4.89Zm5.71-7.8c-.31-.16-1.84-.91-2.13-1.01-.28-.1-.49-.16-.7.16-.2.31-.8 1.01-.98 1.22-.18.2-.36.23-.67.08-.31-.16-1.3-.48-2.48-1.53-.92-.82-1.54-1.83-1.72-2.14-.18-.31-.02-.48.14-.64.14-.14.31-.36.46-.54.16-.18.2-.31.31-.52.1-.21.05-.39-.03-.54-.08-.16-.7-1.69-.96-2.31-.25-.61-.51-.52-.7-.53h-.6c-.21 0-.54.08-.82.39-.28.31-1.07 1.04-1.07 2.53s1.1 2.94 1.25 3.14c.15.21 2.15 3.29 5.2 4.61.72.31 1.28.5 1.72.64.72.23 1.37.2 1.89.12.58-.09 1.84-.75 2.1-1.48.26-.72.26-1.35.18-1.48-.08-.13-.28-.21-.59-.36Z" />
    </svg>
  );
}

const SOCIAL_ICON_PATHS = {
  instagram: (
    <>
      <rect x="3.4" y="3.4" width="17.2" height="17.2" rx="5" fill="none" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="12" cy="12" r="4.1" fill="none" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="17.1" cy="6.9" r="1.1" />
    </>
  ),
  facebook: <path d="M13.6 21v-7.4h2.6l.4-3h-3V8.7c0-.86.25-1.45 1.5-1.45h1.5V4.5c-.26-.03-1.15-.1-2.18-.1-2.16 0-3.64 1.3-3.64 3.7v2.5H8v3h2.78V21z" />,
  x: <path d="M17.6 3h3.2l-7 8 8.2 10h-6.4l-5-5.7L4.7 21H1.5l7.5-8.6L1.1 3h6.6l4.5 5.2zm-1.1 16h1.8L7.6 4.9H5.7z" />,
  tiktok: <path d="M14.6 3h2.4a5.1 5.1 0 0 0 4 4v2.5a7.5 7.5 0 0 1-4-1.3v6.2a6.3 6.3 0 1 1-5.4-6.2v2.6a3.8 3.8 0 1 0 2.9 3.7z" />,
  youtube: (
    <>
      <rect x="2.6" y="5.6" width="18.8" height="12.8" rx="3.4" />
      <path d="M10.4 9.4 15.6 12l-5.2 2.6z" fill="#203b35" />
    </>
  ),
};

function SocialIcon({ icon, className = 'h-4 w-4' }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="currentColor">
      {SOCIAL_ICON_PATHS[icon] || SOCIAL_ICON_PATHS.instagram}
    </svg>
  );
}

function ShareIcon({ icon, className = 'h-4 w-4' }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="currentColor">
      {icon === 'whatsapp' ? (
        <path d="M12 3a9 9 0 0 0-7.7 13.7L3 21l4.4-1.2A9 9 0 1 0 12 3Zm0 16.3a7.3 7.3 0 0 1-3.9-1.1l-.3-.2-2.5.7.7-2.4-.2-.3A7.3 7.3 0 1 1 12 19.3Zm4.1-5.4c-.2-.1-1.3-.6-1.5-.7-.2-.1-.3-.1-.5.1-.1.2-.5.7-.7.8-.1.2-.2.2-.5.1a6 6 0 0 1-1.7-1.1 6.5 6.5 0 0 1-1.2-1.5c-.1-.2 0-.3.1-.4l.4-.4c.1-.2.1-.3.2-.4 0-.2 0-.3-.1-.4l-.6-1.6c-.2-.5-.4-.4-.5-.4h-.4c-.2 0-.4.1-.6.3-.2.2-.8.7-.8 1.8s.8 2.1.9 2.3c.1.2 1.6 2.4 3.8 3.4.5.2.9.4 1.2.5.5.2 1 .1 1.4.1.4-.1 1.3-.5 1.5-1.1.2-.5.2-1 .1-1.1 0-.1-.2-.2-.4-.3Z" />
      ) : (
        SOCIAL_ICON_PATHS[icon]
      )}
    </svg>
  );
}

function pageShareLinks(title) {
  const url = typeof window === 'undefined' ? '' : window.location.href;
  return {
    url,
    items: [
      { icon: 'whatsapp', label: 'WhatsApp', href: `https://wa.me/?text=${encodeURIComponent(`${title} — ${url}`)}` },
      { icon: 'facebook', label: 'Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}` },
      { icon: 'x', label: 'X', href: `https://x.com/intent/post?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}` },
      { icon: 'mail', label: 'Email', href: `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(url)}` },
    ],
  };
}

function ShareRow({ title, className = '', tone = 'light' }) {
  const [copied, setCopied] = useState(false);
  const { url, items } = pageShareLinks(title);
  const chip = tone === 'dark'
    ? 'border-white/25 text-white/80 hover:border-white/60 hover:text-white'
    : 'border-[#d9d3c4] text-[#52615b] hover:border-[#203b35] hover:text-[#203b35]';

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <span className={`text-xs font-bold uppercase tracking-[0.14em] ${tone === 'dark' ? 'text-white/55' : 'text-[#8a8172]'}`}>Share</span>
      {items.map((item) => (
        <a
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${chip}`}
          href={item.href}
          key={item.label}
          rel="noopener noreferrer"
          target="_blank"
        >
          {item.icon === 'mail' ? (
            <svg aria-hidden="true" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <rect x="3" y="5.5" width="18" height="13" rx="2.5" />
              <path d="m4 7 8 6 8-6" />
            </svg>
          ) : <ShareIcon className="h-3.5 w-3.5" icon={item.icon} />}
          {item.label}
        </a>
      ))}
      <button
        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${chip}`}
        onClick={copyLink}
        type="button"
      >
        <svg aria-hidden="true" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <path d="M10.2 13.8a3.6 3.6 0 0 0 5.1 0l3-3a3.6 3.6 0 0 0-5.1-5.1l-1 1" />
          <path d="M13.8 10.2a3.6 3.6 0 0 0-5.1 0l-3 3a3.6 3.6 0 0 0 5.1 5.1l1-1" />
        </svg>
        {copied ? 'Copied' : 'Copy link'}
      </button>
    </div>
  );
}

function FooterSocialRow() {
  const profiles = useSocialLinks();
  if (!profiles.length) {
    return <ShareRow className="mt-6" title="Kenya Tours & Marketplace" tone="dark" />;
  }
  return (
    <div className="mt-6">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#8de6e4]">Follow us</p>
      <ul className="mt-3 flex flex-wrap items-center gap-2" aria-label="Kenya Tours & Marketplace on social media">
        {profiles.map((profile) => (
          <li key={profile.href}>
            <a
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/20 text-[#e8eee9] transition hover:border-white/60 hover:text-white"
              href={profile.href}
              rel="noopener noreferrer"
              target="_blank"
              aria-label={`${profile.label} (opens in a new tab)`}
              title={profile.label}
            >
              <SocialIcon className="h-[1.05rem] w-[1.05rem]" icon={profile.icon} />
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function imageUrl(url) {
  if (!url || !/^(https?:\/\/|\/?images\/|\/?pictures\/|\/?uploads\/)/i.test(url) || url.split('/').includes('..')) {
    return fallbackImage;
  }
  return url.startsWith('http') ? url : `/${url.replace(/^\/+/, '')}`;
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
    || (navigationAliases[href] || []).some((path) => pathname.startsWith(path));
}

function HeaderSearchLink() {
  // The search page brings its own, larger search field, so the header only points to it.
  if (window.location.pathname.toLowerCase() === '/search.html') return null;

  return (
    <a
      className="site-search-link"
      href="/search.html"
      aria-label="Search tours, accommodations and places"
      title="Search tours, accommodations and places"
    >
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="11" cy="11" r="6.5" />
        <path d="m16.2 16.2 4.3 4.3" />
      </svg>
      <span className="site-search-link__label">Search</span>
    </a>
  );
}

function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [language, setLanguage] = useState(documentLanguage());
  const [signedIn, setSignedIn] = useState(false);
  const [atTop, setAtTop] = useState(true);
  const pathname = window.location.pathname;
  const isHome = pathname === '/' || pathname === '/index.html';
  const accountHref = signedIn ? '/my-bookings' : '/login.html';
  const accountLabel = signedIn ? 'My account' : 'Sign in';

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/customer/profile', { headers: { Accept: 'application/json' }, signal: controller.signal })
      .then((response) => setSignedIn(response.ok))
      .catch((error) => {
        if (error.name !== 'AbortError') setSignedIn(false);
      });
    return () => controller.abort();
  }, []);

  // On the home page the bar floats over the hero until the visitor scrolls away from it.
  useEffect(() => {
    if (!isHome) return undefined;
    const onScroll = () => setAtTop(window.scrollY < 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [isHome]);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);

  function toggleLanguage() {
    const nextLanguage = language === 'en' ? 'sw' : 'en';
    window.setKenyaLanguage?.(nextLanguage);
    setLanguage(nextLanguage);
  }

  const overlay = isHome && atTop && !menuOpen;

  return (
    <header className={`site-header${isHome ? ' site-header--home' : ''} ${overlay ? 'is-over-hero' : 'is-docked'}`}>
      <div className="site-utility">
        <div className="site-utility__inner">
          <a className="site-utility__phone" href={CONTACT_PHONE_HREF}>
            <PhoneIcon />
            <span>Talk to a local expert · {CONTACT_PHONE_DISPLAY}</span>
          </a>
          <nav className="site-utility__links" aria-label="Secondary navigation">
            {secondaryLinks.map(([href, label]) => (
              <a href={href} key={href} aria-current={isCurrentNavigationLink(href, pathname) ? 'page' : undefined}>
                {label}
              </a>
            ))}
            <a className="site-utility__account" href={accountHref}>{signedIn ? 'My account' : 'Sign in / Register'}</a>
          </nav>
        </div>
      </div>

      <div className="site-header__bar">
        <a className="brand-lockup site-brand" href="/index.html" aria-label="Kenya Tours & Marketplace — tours and accommodations across Kenya">
          <img className="brand-mark site-brand__mark" src="/logo.svg" alt="" />
          <span className="site-brand__text">
            <span className="brand-name site-brand__name">Kenya Tours &amp; Marketplace</span>
            <span className="brand-tagline site-brand__tagline">Tours &amp; accommodations · Kenya</span>
          </span>
        </a>

        <nav className="site-nav" aria-label="Main navigation">
          {primaryLinks.map(([href, label]) => (
            <a
              href={href}
              key={href}
              aria-current={isCurrentNavigationLink(href, pathname) ? 'page' : undefined}
              onClick={() => setMenuOpen(false)}
            >
              {label}
            </a>
          ))}
        </nav>

        <div className="site-actions">
          <HeaderSearchLink />
          <HeaderWishlistLink />
          <button
            className="site-icon-button"
            data-language-toggle
            type="button"
            aria-label={language === 'en' ? 'Switch to Kiswahili' : 'Switch to English'}
            aria-pressed={language === 'sw'}
            title={language === 'en' ? 'Switch to Kiswahili' : 'Switch to English'}
            onClick={toggleLanguage}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 5h9M8.5 3v2m3 0c-.8 4-3.2 7-7.5 9" />
              <path d="M6 9c1.2 1.8 2.8 3.2 5 4.2M14 19l3.2-8 3.3 8m-5.4-2h4.3" />
            </svg>
            <span className="site-icon-button__label">{language === 'en' ? 'SW' : 'EN'}</span>
          </button>
          <a className="site-account" href={accountHref}>{accountLabel}</a>
          <button
            className="site-menu-button"
            type="button"
            aria-expanded={menuOpen}
            aria-controls="primary-navigation"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <span className="site-menu-button__bars" aria-hidden="true"><i /><i /><i /></span>
            <span className="sr-only">{menuOpen ? 'Close' : 'Menu'}</span>
          </button>
        </div>
      </div>

      {menuOpen && (
        <div className="site-menu" id="primary-navigation">
          <nav aria-label="Mobile navigation">
            {primaryLinks.map(([href, label]) => (
              <a
                href={href}
                key={href}
                aria-current={isCurrentNavigationLink(href, pathname) ? 'page' : undefined}
                onClick={() => setMenuOpen(false)}
              >
                {label}
              </a>
            ))}
          </nav>
          {pathname.toLowerCase() !== '/search.html' && (
            <a className="site-menu__search" href="/search.html" onClick={() => setMenuOpen(false)}>
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <circle cx="11" cy="11" r="6.5" />
                <path d="m16.2 16.2 4.3 4.3" />
              </svg>
              <span>Search</span>
            </a>
          )}
          <div className="site-menu__divider" role="presentation" />
          <nav className="site-menu__secondary" aria-label="More navigation">
            {secondaryLinks.map(([href, label]) => (
              <a
                href={href}
                key={href}
                aria-current={isCurrentNavigationLink(href, pathname) ? 'page' : undefined}
                onClick={() => setMenuOpen(false)}
              >
                {label}
              </a>
            ))}
          </nav>
          <a className="site-menu__account" href={accountHref} onClick={() => setMenuOpen(false)}>{signedIn ? 'My account' : 'Sign in / Register'}</a>
        </div>
      )}
    </header>
  );
}

function Footer() {
  const phone = useWhatsAppPhone();

  return (
    <footer className="mt-20 bg-[#203b35] text-[#e8eee9]">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-12 sm:px-8 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-[1.4fr_1fr_1fr_1fr_1fr]">
        <div>
          <a className="brand-lockup flex items-center gap-3 text-white" href="/index.html" aria-label="Kenya Tours & Marketplace home">
            <img className="brand-mark h-12 w-12" src="/logo.svg" alt="" />
            <span className="flex flex-col">
              <span className="brand-name text-lg font-bold text-white sm:text-xl">Kenya Tours & Marketplace</span>
              <span className="brand-tagline text-[0.6rem] font-bold uppercase tracking-[0.17em] text-[#8de6e4]">Tours &amp; accommodations · Kenya</span>
            </span>
          </a>
          <p className="mt-4 max-w-sm text-sm leading-6 text-[#c4d0c9]">
            Book the coast, the city, and the savannah with people who live there: dhow sails, heritage walks, safaris, and accommodations with a sense of place.
          </p>
          <NewsletterForm className="mt-6 max-w-sm" source="footer" />
          <FooterSocialRow />
        </div>
        <div>
          <h2 className="font-semibold text-white">Explore</h2>
          <div className="mt-4 flex flex-col gap-3 text-sm text-[#c4d0c9]">
            <a className="hover:text-white" href="/properties.html">Properties &amp; places to stay</a>
            <a className="hover:text-white" href="/tours.html">Tours &amp; guided experiences</a>
            <a className="hover:text-white" href="/safari-operators.html">Safari operators</a>
            <a className="hover:text-white" href="/destinations.html">Destinations by region</a>
            <a className="hover:text-white" href="/explore.html">Explore by category</a>
            <a className="hover:text-white" href="/gallery.html">Photo gallery</a>
            <a className="hover:text-white" href="/compare.html">Compare listings</a>
            <a className="hover:text-white" href="/wishlist.html">My wishlist</a>
            <a className="hover:text-white" href="/services.html">Travel services &amp; transfers</a>
            <a className="hover:text-white" href="/about-kenya.html">About Kenya</a>
          </div>
        </div>
        <div>
          <h2 className="font-semibold text-white">Guides &amp; help</h2>
          <div className="mt-4 flex flex-col gap-3 text-sm text-[#c4d0c9]">
            <a className="hover:text-white" href="/blog.html">Blogs &amp; travel guides</a>
            <a className="hover:text-white" href="/reviews.html">Community reviews</a>
            <a className="hover:text-white" href="/faq.html">FAQ</a>
            <a className="hover:text-white" href="/contact.html">Contact us</a>
            <a className="hover:text-white" href="/search.html">Search tours &amp; stays</a>
            <a className="hover:text-white" href="/booking.html">Plan your trip</a>
            <a className="hover:text-white" href="/partner/login">Partner portal</a>
          </div>
        </div>
        <div>
          <h2 className="font-semibold text-white">User support</h2>
          <div className="mt-4 flex flex-col gap-3 text-sm text-[#c4d0c9]">
            <a className="hover:text-white" href="/how-it-works.html">How it works</a>
            <a className="hover:text-white" href="/booking-guide.html">Booking guide</a>
            <a className="hover:text-white" href="/cancellation-policy.html">Cancellation policy</a>
            <a className="hover:text-white" href="/privacy-policy.html">Privacy policy</a>
            <a className="hover:text-white" href="/terms.html">Terms &amp; conditions</a>
          </div>
        </div>
        <div>
          <h2 className="font-semibold text-white">Get in touch</h2>
          <div className="mt-4 flex flex-col gap-3 text-sm text-[#c4d0c9]">
            <a className="hover:text-white" href="/contact.html">Contact our team</a>
            <a className="inline-flex items-center gap-2 hover:text-white" href={CONTACT_PHONE_HREF}>
              <PhoneIcon />
              <span>Call {CONTACT_PHONE_DISPLAY}</span>
            </a>
            <a className="inline-flex items-center gap-2 hover:text-white" href={whatsappUrl(WHATSAPP_GREETING, phone)} target="_blank" rel="noopener noreferrer">
              <WhatsAppIcon />
              <span>WhatsApp us</span>
            </a>
            <span>Kenya</span>
          </div>
        </div>
      </div>
      <div className="border-t border-white/10 px-5 py-5 text-center text-xs text-[#c4d0c9]">
        © 2026 Kenya Tours &amp; Marketplace. All rights reserved.
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
      <CompareTray />
      <FloatingWhatsApp />
    </>
  );
}

function FloatingWhatsApp() {
  const phone = useWhatsAppPhone();

  return (
    <a
      className="fixed bottom-5 right-5 z-50 inline-flex min-h-14 items-center gap-3 rounded-full bg-[#16833b] px-4 text-sm font-bold text-white shadow-xl shadow-slate-950/25 transition hover:-translate-y-1 hover:bg-[#116b30] focus-visible:outline-white sm:bottom-7 sm:right-7"
      href={whatsappUrl(WHATSAPP_GREETING, phone)}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Chat with Kenya Tours & Marketplace on WhatsApp (opens in a new tab)"
      title="Chat with us on WhatsApp"
    >
      <WhatsAppIcon className="h-7 w-7 shrink-0" />
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
  return <p className="py-8 text-center text-[#52615b]" role="status">Loading Kenya experiences…</p>;
}

function TourCard({ tour, currency }) {
  return (
    <article className="tour-card overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-xl">
      <div className="relative">
        <a className="block" href={`/tour-details.html?id=${encodeURIComponent(tour.slug)}`} aria-label={`View ${tour.name}`} onClick={() => trackPromotionClick('tour', tour.slug, tour.promotion)}>
          <img className="h-56 w-full object-cover" src={imageUrl(tour.image_url)} alt={tour.name} loading="lazy" />
        </a>
        <SponsoredTag className="absolute left-3 top-3 shadow-sm" promotion={tour.promotion} />
        <WishlistButton className="absolute right-3 top-3 z-10" listingType="tour" name={tour.name} slug={tour.slug} />
      </div>
      <div className="p-5">
        <p className="mb-2 text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{tour.category || 'Experiences'}</p>
        <div className="flex items-start justify-between gap-3">
          <h3 className="display-font text-2xl text-[#203b35]">{tour.name}</h3>
          <span className="shrink-0 rounded-full bg-[#f3eee6] px-3 py-1 text-xs font-semibold text-[#735744]">{tour.duration}</span>
        </div>
        {tour.operator && tour.operator.slug && <OperatorCredit operator={tour.operator} />}
        <BadgeList badges={tour.badges} />
        {tour.review_count > 0 && <p className="mt-2 flex items-center gap-2 text-sm text-[#52615b]">
          <StarRow rating={tour.rating} />
          <span>{Number(tour.rating).toFixed(1)}</span>
          <span>· {tour.review_count} review{tour.review_count === 1 ? '' : 's'}</span>
        </p>}
        <p className="mt-3 line-clamp-3 min-h-[4.5rem] text-sm leading-6 text-[#52615b]">{tour.description}</p>
        <CompareToggle className="mt-4" name={tour.name} slug={tour.slug} type="tour" />
        <div className="mt-5 flex items-center justify-between gap-3 border-t border-[#efede7] pt-4">
          <div>
            <p className="text-sm text-[#52615b]">
              From <strong className="text-base text-[#203b35]">{formatPrice(tour.price, currency)}</strong>
              <span className="block text-xs">per guest</span>
            </p>
            <p className="mt-1 text-xs font-semibold text-[#177b5b]">{priceComparisonText(tour.price_comparison)}</p>
          </div>
          <a className="rounded-full bg-[#203b35] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#31554b]" href={`/tour-details.html?id=${encodeURIComponent(tour.slug)}`} onClick={() => trackPromotionClick('tour', tour.slug, tour.promotion)}>
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
      <div className="relative">
        <img className="h-52 w-full object-cover" src={imageUrl(property.image_url)} alt={property.name} loading="lazy" />
        <SponsoredTag className="absolute left-3 top-3 shadow-sm" promotion={property.promotion} />
        <WishlistButton className="absolute right-3 top-3 z-10" listingType="property" name={property.name} slug={property.slug} />
      </div>
      <div className="p-5">
        <p className="text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{propertyTypeLabel(property.property_type)} · {property.location}</p>
        <h3 className="display-font mt-2 text-2xl text-[#203b35]">{property.name}</h3>
        <OperatorCredit operator={property.operator} role="host" />
        {property.review_count > 0 && <p className="mt-1 flex items-center gap-2 text-sm font-semibold text-[#203b35]">
          <StarRow rating={property.rating} />
          <span>{Number(property.rating).toFixed(1)}</span>
          <span className="font-normal text-[#52615b]">({property.review_count} review{property.review_count === 1 ? '' : 's'})</span>
        </p>}
        <BadgeList badges={property.badges} />
        <p className="mt-2 text-sm text-[#52615b]">
          {property.guests} guests · {stayPriceText(property, currency)}
          {property.room_types > 0 && ` · ${property.room_types} room ${property.room_types === 1 ? 'type' : 'types'}`}
        </p>
        <p className="mt-1 text-xs font-semibold text-[#177b5b]">{priceComparisonText(property.price_comparison)}</p>
        {property.description && <p className="mt-3 line-clamp-2 text-sm leading-6 text-[#52615b]">{property.description}</p>}
        <a className="mt-4 inline-flex rounded-full border border-[#203b35] px-4 py-2.5 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" href={`/booking.html?stay=${encodeURIComponent(property.slug)}&guests=${property.guests}`} onClick={() => trackPromotionClick('property', property.slug, property.promotion)}>
          Ask us about this accommodation
        </a>
        <CompareToggle className="mt-3" name={property.name} slug={property.slug} type="property" />
        <details className="mt-5 border-t border-[#efede7] pt-4">
          <summary className="cursor-pointer text-sm font-semibold text-[#203b35]">Guest reviews</summary>
          <ReviewPanel targetId={property.slug} targetType="property" />
        </details>
      </div>
    </article>
  );
}

function OperatorCredit({ operator, role = 'partner' }) {
  if (!operator || !operator.slug) return null;
  return (
    <p className="mt-1 text-xs font-semibold text-[#52718a]">
      {role === 'host' ? 'Hosted by' : 'By'} <a className="hover:underline" href={`/operators/${operator.slug}`}>{operator.name}</a>
      {operator.location ? ` · ${operator.location}` : ''}
    </p>
  );
}

function ServiceCard({ service, currency }) {
  const sitePhone = useWhatsAppPhone();
  const operator = service.operator;
  const enquiry = whatsappUrl(
    `Hello, I would like a quote for ${service.name} (${formatPrice(service.price_from, currency)} ${service.price_unit}).`,
    operator?.phone || sitePhone,
  );

  return (
    <article className="tour-card flex flex-col overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-xl" id={`service-${service.slug}`}>
      <img className="h-48 w-full object-cover" src={imageUrl(service.image_url)} alt={service.name} loading="lazy" />
      <div className="flex flex-1 flex-col p-5">
        <p className="mb-2 text-xs font-bold uppercase tracking-wider text-[#a75f3a]">
          {service.service_type_label}{service.location ? ` · ${service.location}` : ''}
        </p>
        <h3 className="display-font text-2xl text-[#203b35]">{service.name}</h3>
        <OperatorCredit operator={operator} />
        {service.coverage?.length > 0 && <p className="mt-2 text-xs font-semibold text-[#735744]">Covers {service.coverage.join(', ')}</p>}
        <p className="mt-3 line-clamp-3 text-sm leading-6 text-[#52615b]">{service.description}</p>
        {service.inclusions?.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2">
            {service.inclusions.slice(0, 3).map((item) => (
              <li className="rounded-full bg-[#f3eee6] px-2.5 py-1 text-xs font-semibold text-[#735744]" key={item}>{item}</li>
            ))}
          </ul>
        )}
        <div className="mt-auto pt-5">
          <p className="text-sm text-[#52615b]">
            From <strong className="text-base text-[#203b35]">{formatPrice(service.price_from, currency)}</strong>
            <span className="block text-xs">{service.price_unit}</span>
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <a className="rounded-full bg-[#16833b] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#116b30]" href={enquiry} target="_blank" rel="noopener noreferrer">
              Request a quote
            </a>
            {operator?.slug && <a className="rounded-full border border-[#203b35] px-4 py-2.5 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" href={`/operators/${operator.slug}`}>View operator</a>}
          </div>
        </div>
      </div>
    </article>
  );
}

function StarRow({ rating }) {
  const rounded = Math.max(0, Math.min(5, Math.round(Number(rating) || 0)));
  return <span className="text-[#b96e45]" role="img" aria-label={`${Number(rating) || 0} out of 5 stars`}><span aria-hidden="true">{'★'.repeat(rounded)}{'☆'.repeat(5 - rounded)}</span></span>;
}

const BADGE_STYLES = {
  'Top rated': 'bg-[#e6f2ea] text-[#177b5b]',
  Popular: 'bg-[#fdf0e6] text-[#a75f3a]',
  'Best value': 'bg-[#eaf1f7] text-[#2c5a7c]',
};

function BadgeList({ badges = [] }) {
  if (!badges || badges.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {badges.map((badge) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${BADGE_STYLES[badge] || 'bg-[#efeee7] text-[#52615b]'}`} key={badge}>{badge}</span>
      ))}
    </div>
  );
}

function SponsoredTag({ promotion, className = '' }) {
  // Paid placements are always labelled, so a sponsored slot can never pass as organic.
  if (!promotion || !promotion.sponsored) return null;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full bg-[#f6ecdc] px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-[0.12em] text-[#8a5a25] ring-1 ring-[#e5d3b6] ${className}`}>
      Sponsored
      {promotion.label && <span className="font-semibold normal-case tracking-normal text-[#a2723f]">· {promotion.label}</span>}
    </span>
  );
}

function promotionRank(item) {
  return Number(item?.promotion?.rank) || 0;
}

function sortPromotedFirst(items) {
  // Array#sort is stable, so the organic order survives inside each sponsored rank.
  return [...items].sort((left, right) => promotionRank(right) - promotionRank(left));
}

function trackPromotionClick(listingType, slug, promotion) {
  if (!promotion || !promotion.sponsored || !slug) return;
  const url = `/api/promotions/${listingType}/${encodeURIComponent(slug)}/click`;
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url);
      return;
    }
    fetch(url, { method: 'POST', keepalive: true }).catch(() => {});
  } catch {
    // Click counting is best effort and never blocks the visitor.
  }
}

function PromotedCard({ listing, currency }) {
  const isStay = listing.listingType === 'property';
  const href = isStay
    ? `/booking.html?stay=${encodeURIComponent(listing.slug)}&guests=${listing.guests}`
    : `/tour-details.html?id=${encodeURIComponent(listing.slug)}`;
  const price = isStay
    ? `${formatPrice(listing.price_per_night, currency)} per night`
    : `From ${formatPrice(listing.price, currency)} per guest`;
  const openListing = () => trackPromotionClick(listing.listingType, listing.slug, listing.promotion);

  return (
    <article className="overflow-hidden rounded-2xl border border-[#e6ddc9] bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg">
      <a className="relative block" aria-label={`View ${listing.name}`} href={href} onClick={openListing}>
        <img className="h-40 w-full object-cover" src={imageUrl(listing.image_url)} alt={listing.name} loading="lazy" />
        <SponsoredTag className="absolute left-3 top-3 shadow-sm" promotion={listing.promotion} />
      </a>
      <div className="p-4">
        <p className="text-xs font-bold uppercase tracking-wider text-[#a75f3a]">
          {isStay ? propertyTypeLabel(listing.property_type) : listing.category || 'Experience'}
        </p>
        <h3 className="display-font mt-1 text-xl leading-tight text-[#203b35]">{listing.name}</h3>
        {listing.promotion?.label && <p className="mt-1 text-xs font-semibold text-[#8a5a25]">{listing.promotion.label}</p>}
        <p className="mt-2 text-sm font-semibold text-[#203b35]">{price}</p>
        <a className="mt-3 inline-flex text-sm font-semibold text-[#9a5534] hover:underline" href={href} onClick={openListing}>View details →</a>
      </div>
    </article>
  );
}

function priceComparisonText(comparison) {
  if (!comparison || !['below', 'above'].includes(comparison.position)) return '';
  const percent = Math.abs(Number(comparison.difference_percent) || 0);
  if (!percent) return '';
  return comparison.position === 'below'
    ? `${percent}% below the area average`
    : `${percent}% above the area average`;
}

function stayPriceText(property, currency) {
  const from = Number(property.price_from) || Number(property.price_per_night) || 0;
  const to = Number(property.price_to) || 0;
  if (!from) return 'Ask our team';
  if (to > from) return `From ${formatPrice(from, currency)} to ${formatPrice(to, currency)} per night`;
  return `${formatPrice(from, currency)} per night`;
}

function RecommendationCard({ item, currency }) {
  const price = Number(item.price_from) > 0
    ? `${formatPrice(item.price_from, currency)} ${item.price_unit}`
    : 'Ask our team';
  return (
    <article className="overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg">
      <a href={item.url} aria-label={`View ${item.name}`}>
        <img className="h-40 w-full object-cover" src={imageUrl(item.image_url)} alt={item.name} loading="lazy" />
      </a>
      <div className="p-4">
        <p className="text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{item.location} · {item.category}</p>
        <h3 className="display-font mt-2 text-xl text-[#203b35]">{item.name}</h3>
        <BadgeList badges={item.badges} />
        {item.review_count > 0 && <p className="mt-2 flex items-center gap-2 text-sm text-[#52615b]">
          <StarRow rating={item.rating} />
          <span>{Number(item.rating).toFixed(1)}</span>
          <span>· {item.review_count} review{item.review_count === 1 ? '' : 's'}</span>
        </p>}
        <p className="mt-2 text-sm font-semibold text-[#203b35]">{price}</p>
        <p className="mt-2 text-xs font-semibold text-[#177b5b]">{item.reason}</p>
        <a className="mt-3 inline-flex text-sm font-semibold text-[#9a5534] hover:underline" href={item.url}>View details →</a>
      </div>
    </article>
  );
}

function RecommendationStrip({ currency, type = '', slug = '', destination = '', exclude = '', title, description, embedded = false }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: '3' });
    if (type) params.set('type', type);
    if (slug) params.set('slug', slug);
    if (destination) params.set('destination', destination);
    if (exclude) params.set('exclude', exclude);
    fetch(`/api/recommendations?${params}`, { signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(async (response) => {
        if (!response.ok) return { recommendations: [] };
        return response.json();
      })
      .then((data) => {
        if (!controller.signal.aborted) setItems(Array.isArray(data.recommendations) ? data.recommendations : []);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [destination, exclude, slug, type]);

  if (items.length === 0) return null;

  return (
    <section className={embedded ? 'mt-14' : 'mx-auto max-w-7xl px-5 py-16 sm:px-8'}>
      <SectionHeading eyebrow="Recommended for you" title={title} description={description} />
      <div className="grid gap-5 md:grid-cols-3">
        {items.map((item) => <RecommendationCard currency={currency} item={item} key={`${item.type}-${item.slug}`} />)}
      </div>
    </section>
  );
}

function ReviewPanel({ targetType, targetId }) {
  const [reviews, setReviews] = useState([]);
  const [summary, setSummary] = useState({ rating: 0, review_count: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ target_type: targetType, target_id: targetId });
    fetch(`/reviews?${query}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Reviews could not be loaded (HTTP ${response.status}).`);
        return response.json();
      })
      .then(({ reviews: loadedReviews, summary: loadedSummary }) => {
        setReviews(loadedReviews);
        setSummary(loadedSummary || { rating: 0, review_count: 0 });
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

  return (
    <div className="mt-4">
      {loading && <p className="text-sm text-[#52615b]" role="status">Loading reviews…</p>}
      {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p>}
      {!loading && !error && reviews.length === 0 && <p className="text-sm text-[#52615b]">No guest reviews yet.</p>}
      {!loading && !error && reviews.length > 0 && <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-[#203b35]">
        <StarRow rating={summary.rating} />
        <span>{Number(summary.rating).toFixed(1)} / 5</span>
        <span className="font-normal text-[#52615b]">· {summary.review_count} review{summary.review_count === 1 ? '' : 's'}</span>
      </p>}
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
    </div>
  );
}

const HOME_STORIES = [
  {
    number: '01',
    title: 'Walk through living history',
    description: 'Follow winding lanes, carved doorways, and the stories that make Kenya’s Swahili old towns unforgettable.',
    href: '/about-kenya.html',
    image: '/images/img-08.webp',
    alt: 'The arched gateway into Lamu old town',
  },
  {
    number: '02',
    title: 'Let the sea set the pace',
    description: 'Step aboard a traditional dhow and discover reef channels, open water, and sandy shores.',
    href: '/tours.html',
    image: '/images/shela-lamu-kenya-01.jpg',
    alt: 'A wooden dhow resting on the sand beneath a clear sky',
  },
  {
    number: '03',
    title: 'Wake up somewhere new',
    description: 'Find a hotel, an apartment, a rental, or a hostel close to the wildlife you came to see.',
    href: '#places-to-stay',
    image: '/images/shela-village.webp',
    alt: 'A whitewashed Swahili house framed by bougainvillea and palms',
  },
];

const HOME_GALLERY = [
  { src: '/pictures/187168867.jpg', alt: 'Turquoise lagoon and dhow near Lamu', caption: 'Blue-water days', layout: 'feature' },
  { src: '/images/Lamu_coast.jpg', alt: 'Aerial view of the Lamu waterfront', caption: 'Old town mornings' },
  { src: '/images/IMG_2026-03-23-17-36-36-712.jpg', alt: 'Boats moored in Lamu harbour at dusk', caption: 'Harbour evenings' },
  { src: '/pictures/426299433.jpg', alt: 'A plunge pool beside a whitewashed villa', caption: 'Slow afternoons' },
  { src: '/pictures/552015001.jpg', alt: 'Dinner tables set on the sand beneath trees', caption: 'Dinner on the sand' },
  { src: '/images/site_1055_0011-1000-748-20151105113637.jpg', alt: 'A dhow sailing along the Lamu shoreline', caption: 'Sail the channel', layout: 'banner' },
];

const HOME_POINTS = [
  { title: 'Guides who call these places home', body: 'Small local teams who know the reefs, lanes and land personally.' },
  { title: 'Published prices, no surprises', body: 'See the full price before you pay, including room rates and per-guest tour costs.' },
  { title: 'Cancel up to 48 hours ahead', body: 'Plans change. Cancel a paid booking from your account and we refund it in full.' },
];

function HomePage({ catalogue, loading, error, retry, currency }) {
  const reviewed = [...catalogue.tours, ...catalogue.properties].filter((item) => item.review_count > 0);
  const reviewTotal = reviewed.reduce((sum, item) => sum + item.review_count, 0);
  const averageRating = reviewTotal
    ? reviewed.reduce((sum, item) => sum + Number(item.rating) * item.review_count, 0) / reviewTotal
    : 0;
  const heroStats = [
    { value: catalogue.destinations.length, label: 'Destinations' },
    { value: catalogue.tours.length + catalogue.properties.length, label: 'Experiences' },
    ...(averageRating ? [{ value: `${averageRating.toFixed(1)}/5`, label: 'Guest rating' }] : []),
  ];
  const promoted = sortPromotedFirst([
    ...catalogue.tours.map((tour) => ({ ...tour, listingType: 'tour' })),
    ...catalogue.properties.map((property) => ({ ...property, listingType: 'property' })),
  ]).filter((listing) => listing.promotion?.sponsored);

  return (
    <PageShell>
      <section className="coast-hero hero-shell">
        <div className="hero-media">
          <img src="/images/img-12.webp" alt="A palm-lined beach with a white villa and a dhow at the water’s edge" />
        </div>
        <div className="hero-veil" />
        <div className="relative z-10 mx-auto w-full max-w-7xl px-5 pb-24 pt-32 sm:px-8 sm:pb-28 sm:pt-36">
          <div className="hero-copy max-w-3xl text-white">
            <p className="mb-6 inline-flex items-center gap-3 text-xs font-bold uppercase tracking-[0.28em] text-[#a9e2e5]">
              <span className="h-px w-10 bg-current opacity-70" aria-hidden="true" />
              Coast · City · Savannah · Rift Valley
            </p>
            <h1 className="display-font text-[2.85rem] leading-[1.03] sm:text-6xl lg:text-7xl">Kenya, one destination at a time.</h1>
            <p className="mt-6 max-w-xl text-base leading-8 text-white/85 sm:text-lg">
              Sail a dhow off Lamu, walk the old streets of Mombasa, cycle beneath the Rift Valley cliffs, then watch the sun go down over the Mara.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <ButtonLink href="/tours.html">Find your Kenyan experience</ButtonLink>
              <ButtonLink href="/about-kenya.html" secondary>Get to know Kenya</ButtonLink>
            </div>
            <div className="mt-10 flex flex-wrap gap-3">
              {heroStats.map((stat) => (
                <div className="hero-stat" key={stat.label}>
                  <strong>{stat.value}</strong>
                  <span>{stat.label}</span>
                </div>
              ))}
            </div>
            <a className="scroll-cue mt-10" href="#stories">
              <span className="scroll-cue__dot" aria-hidden="true" />
              Scroll to explore
            </a>
          </div>
        </div>
        <div className="hero-float absolute bottom-6 right-6 hidden max-w-xs rounded-2xl border border-white/25 bg-[#06222f]/55 p-5 text-sm text-white backdrop-blur md:block">
          <span className="block font-semibold">Six regions. One country.</span>
          <span className="mt-1 block text-white/75">Coastal Swahili towns, big-city wildlife, and open savannah — all booked through one team.</span>
        </div>
      </section>

      {promoted.length > 0 && (
        <section className="mx-auto max-w-7xl px-5 pt-14 sm:px-8 sm:pt-16">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <SectionHeading
              eyebrow="Sponsored placements"
              title="Featured partners this month."
              description="Paid placements from partners we work with. Every sponsored card is labelled, and the rest of the marketplace stays ranked on bookings, guest ratings and price."
            />
            <ButtonLink className="mb-8 self-start" href="/tours.html">Browse every experience →</ButtonLink>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {promoted.slice(0, 6).map((listing) => (
              <PromotedCard currency={currency} key={`${listing.listingType}-${listing.slug}`} listing={listing} />
            ))}
          </div>
        </section>
      )}

      <section className="mx-auto max-w-7xl px-5 pt-14 sm:px-8 sm:pt-20">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <SectionHeading
            eyebrow="Explore by category"
            title="Start with the kind of trip you have in mind."
            description="Luxury lodges, budget rooms, day tours, overnight safaris and adventure activities — pick a category and see what is bookable right now."
          />
          <ButtonLink className="mb-8 self-start" href="/explore.html">See all categories →</ButtonLink>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {CATEGORIES.map((category) => <CategoryTile category={category} catalogue={catalogue} key={category.slug} />)}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 pt-14 sm:px-8 sm:pt-20">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <SectionHeading
            eyebrow="Browse by region"
            title="Six regions, one country."
            description="Nairobi and the Rift Valley lakes, the Maasai Mara, Amboseli, Tsavo, the Indian Ocean coast and the Mount Kenya highlands. Pick a region to see every destination, tour and stay inside it."
          />
          <ButtonLink className="mb-8 self-start" href="/destinations.html">Explore all regions →</ButtonLink>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {REGIONS.map((region) => <RegionTile catalogue={catalogue} key={region.slug} region={region} />)}
        </div>
      </section>

      <section id="stories" className="mx-auto max-w-7xl scroll-mt-8 px-5 py-16 sm:px-8 sm:py-24">
        <SectionHeading
          eyebrow="Make it your own"
          title="Make room for a different kind of getaway."
          description="Trade the rush for dhow sails, old-town stories, and slow mornings beside the sea. Start with the experience that feels most like you."
        />
        <div className="grid gap-5 md:grid-cols-3">
          {HOME_STORIES.map((story) => (
            <a className="image-card" href={story.href} key={story.number}>
              <img src={story.image} alt={story.alt} loading="lazy" />
              <span className="image-card__body">
                <span className="image-card__meta">{story.number}</span>
                <span className="image-card__title">{story.title}</span>
                <span className="text-sm leading-6 text-white/80">{story.description}</span>
                <span className="image-card__cta">Explore <span className="image-card__arrow" aria-hidden="true">→</span></span>
              </span>
            </a>
          ))}
        </div>
      </section>

      <section className="coast-gallery-wrap px-5 py-16 sm:px-8 sm:py-20">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <SectionHeading eyebrow="Postcards from the coast" title="A country that photographs itself." />
            <div className="mb-8 max-w-sm">
              <p className="text-sm leading-6 text-[#365565]">Light, water and old streets — a few frames from the places we book every week.</p>
              <a className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[#203b35] hover:underline" href="/gallery.html">Open the photo gallery →</a>
            </div>
          </div>
          <div className="mosaic-grid">
            {HOME_GALLERY.map((shot) => (
              <figure className={`mosaic-card${shot.layout ? ` mosaic-card--${shot.layout}` : ''}`} key={shot.src}>
                <img src={shot.src} alt={shot.alt} loading="lazy" />
                <figcaption>{shot.caption}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#efeee7] px-5 py-16 sm:px-8 sm:py-20">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <SectionHeading eyebrow="Go at your own pace" title="The best travel days are never hurried." />
            <ButtonLink className="mb-8 self-start" href="/tours.html">Explore every experience →</ButtonLink>
          </div>
          {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
            <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {catalogue.tours.slice(0, 3).map((tour) => <TourCard currency={currency} key={tour.slug} tour={tour} />)}
              {catalogue.tours.length === 0 && <p className="text-[#52615b]">New Kenyan experiences are on the way. Check back soon.</p>}
            </div>
          )}
        </div>
      </section>

      {(catalogue.services || []).length > 0 && (
        <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-20">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
            <SectionHeading
              eyebrow="Beyond the tour"
              title="Transfers, guides and the services that make a trip easy."
              description="Safari and tour operators also run the practical extras: airport pickups, private guides, 4x4 hire and more. Ask for a quote with your dates."
            />
            <ButtonLink className="mb-8 self-start" href="/services.html">Browse all services →</ButtonLink>
          </div>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {(catalogue.services || []).slice(0, 3).map((service) => <ServiceCard currency={currency} key={service.slug} service={service} />)}
          </div>
        </section>
      )}

      <RecommendationStrip
        currency={currency}
        description="Tours and stays ranked from verified bookings, guest ratings and price value."
        title="Trending now"
      />

      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-24">
        <div className="grid items-center gap-10 lg:grid-cols-[0.92fr_1.08fr]">
          <div className="story-frame">
            <img
              className="h-[24rem] w-full rounded-[1.45rem] lg:h-[32rem]"
              src="/images/Spiritedpursuit_leelitumbe-143_lamu_kenya.webp"
              alt="A donkey carrying sacks down a narrow Lamu lane"
              loading="lazy"
            />
            <span className="story-chip">Hosted in Lamu</span>
          </div>
          <div>
            <SectionHeading
              eyebrow="Why travel with us"
              title="Planned by people who live here."
              description="Every itinerary is shaped with local guides, hoteliers and drivers. Real availability, honest prices, and someone who answers when plans change."
            />
            <ul className="space-y-5">
              {HOME_POINTS.map((point, index) => (
                <li className="story-point" key={point.title}>
                  <span className="story-point__index" aria-hidden="true">0{index + 1}</span>
                  <span>
                    <h3>{point.title}</h3>
                    <span className="mt-1 block text-sm leading-6 text-[#52615b]">{point.body}</span>
                  </span>
                </li>
              ))}
            </ul>
            <ButtonLink className="mt-8" href="/booking.html">Start planning your trip</ButtonLink>
          </div>
        </div>
      </section>

      {catalogue.destinations.length > 0 && (
        <section className="bg-[#efeee7] px-5 py-16 sm:px-8 sm:py-20">
          <div className="mx-auto max-w-7xl">
            <SectionHeading
              eyebrow="Every destination, one country"
              title="Find the place that feels like yours."
              description="From Swahili old towns on the coast to the open plains below Kilimanjaro, pick a destination and see what you can book there."
            />
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {catalogue.destinations.map((item) => (
                <article className="destination-card overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm" key={item.slug}>
                  <img className="h-48 w-full object-cover" src={imageUrl(item.image_url)} alt={item.name} loading="lazy" />
                  <div className="p-5">
                    <h3 className="display-font text-2xl text-[#203b35]">{item.name}</h3>
                    <p className="mt-2 min-h-12 text-sm leading-6 text-[#52615b]">{item.description}</p>
                    <a
                      className="action-link mt-4"
                      href={`/search.html?q=${encodeURIComponent(item.name)}&type=accommodation`}
                    >
                      Find accommodations in {item.name} →
                    </a>
                  </div>
                </article>
              ))}
            </div>
            <div className="mt-8 text-center">
              <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/destinations.html" secondary>Browse destinations by region</ButtonLink>
            </div>
          </div>
        </section>
      )}

      <CommunityReviewsStrip />

      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-20">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <SectionHeading
            eyebrow="Blogs & travel guides"
            title="Plan with the guides we give our own guests."
            description="Seasons, packing lists, old-town walks and itineraries from the team who books these trips every week."
          />
          <ButtonLink className="mb-8 self-start" href="/blog.html">All travel guides →</ButtonLink>
        </div>
        <div className="grid gap-5 md:grid-cols-3">
          {BLOG_POSTS.slice(0, 3).map((post) => <BlogCard key={post.slug} post={post} />)}
        </div>
      </section>

      <section id="places-to-stay" className="mx-auto max-w-7xl scroll-mt-8 px-5 py-16 sm:px-8 sm:py-20">
        <SectionHeading
          eyebrow="Settle in wherever you land"
          title="A welcoming place to call your own."
          description="A calm base for the days you have planned. Browse a few of our favourite stays, then ask our local team to match something to your dates."
        />
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {catalogue.properties.slice(0, 3).map((property) => <PropertyCard currency={currency} key={property.slug} property={property} />)}
            {catalogue.properties.length === 0 && <p className="text-[#52615b]">Accommodations are being added. Please check back soon.</p>}
            {catalogue.properties.length > 3 && <a className="flex min-h-56 items-center justify-center rounded-2xl border border-dashed border-[#c8c9be] font-semibold text-[#203b35] hover:bg-white" href="/booking.html">Looking for something else? Ask our local team →</a>}
          </div>
        )}
      </section>

      <NewsletterBand />

      <section className="mx-auto max-w-7xl px-5 pb-20 sm:px-8">
        <div className="cta-band">
          <img src="/images/Spiritedpursuit_leelitumbe-106_lamu_kenya.webp" alt="" loading="lazy" />
          <div className="cta-veil" />
          <div className="relative z-10 max-w-2xl px-6 py-14 text-white sm:px-12 sm:py-16">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a9e2e5]">Your Kenyan trip starts here</p>
            <h2 className="display-font mt-4 text-4xl sm:text-5xl">Let Kenya be more than a place on the map.</h2>
            <p className="mt-4 leading-7 text-white/75">Tell us what you’re drawn to—sailing, Swahili heritage, wildlife, or a slower few days in the hills—and take the first step toward your Kenyan trip.</p>
            <ButtonLink className="mt-7" href="/booking.html">Start planning your trip</ButtonLink>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function ToursPage({ catalogue, loading, error, retry, currency }) {
  const params = new URLSearchParams(window.location.search);
  const [destination, setDestination] = useState(() => params.get('destination') || '');
  const [category, setCategory] = useState('');
  const [collectionSlug, setCollectionSlug] = useState(() => findCategory(params.get('collection'))?.slug || '');
  const [regionSlug, setRegionSlug] = useState(() => findRegion(params.get('region'))?.slug || '');
  const collection = findCategory(collectionSlug);
  const region = findRegion(regionSlug);
  const scopedTours = region ? catalogue.tours.filter((tour) => inRegion(region, tour)) : catalogue.tours;
  const inCollection = collection ? scopedTours.filter(collection.matches) : scopedTours;
  const categories = [...new Set(inCollection.map((tour) => tour.category || 'Experiences'))].sort();
  const destinationsInScope = region ? regionDestinations(region, catalogue.destinations) : catalogue.destinations;
  const destinationNames = new Map(catalogue.destinations.map((item) => [item.slug, item.name]));
  const visibleTours = sortPromotedFirst(inCollection.filter((tour) => (
    (!destination || tour.destination === destination)
    && (!category || (tour.category || 'Experiences') === category)
  )));

  return (
    <PageShell>
      <PageBanner eyebrow="Find your Kenya" title="Come for one place. Leave with a story from every region." description="Sail a dhow on the coast, follow old-town lanes, cycle beneath the Rift Valley cliffs, or spend a morning on safari. Every experience is led by people who know their corner of Kenya by heart." />
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <SectionHeading eyebrow="Made memorable by local knowledge" title="Your next Kenyan story starts here." description="Filter by destination or by the kind of day you want, then explore the details and pick a published departure time." />
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-2" aria-label="Browse experiences by category">
              <span className="mr-1 text-xs font-bold uppercase tracking-wider text-[#735744]">Categories</span>
              <FilterChip active={collectionSlug === ''} onClick={() => setCollectionSlug('')}>All categories</FilterChip>
              {categoriesFor('experiences').map((item) => (
                <FilterChip active={collectionSlug === item.slug} key={item.slug} onClick={() => setCollectionSlug(collectionSlug === item.slug ? '' : item.slug)}>
                  {item.label}
                </FilterChip>
              ))}
              <a className="ml-auto text-sm font-semibold text-[#9a5534] hover:underline" href="/explore.html">Explore categories →</a>
            </div>
            {region && (
              <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-[#e9eee8] px-4 py-3 text-sm text-[#203b35]">
                <span className="font-semibold">Browsing {region.name}</span>
                <span className="text-[#52615b]">{region.tagline}</span>
                <a className="ml-auto font-semibold text-[#9a5534] hover:underline" href="/tours.html">Clear region ✕</a>
              </div>
            )}
            {destinationsInScope.length > 1 && (
              <div className="mb-4 flex flex-wrap gap-2" aria-label="Filter tours by destination">
                <button className={`rounded-full px-4 py-2 text-sm font-semibold ${destination === '' ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" onClick={() => setDestination('')}>{region ? `All ${region.name}` : 'All Kenya'}</button>
                {destinationsInScope.map((item) => <button className={`rounded-full px-4 py-2 text-sm font-semibold ${destination === item.slug ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" key={item.slug} onClick={() => setDestination(destination === item.slug ? '' : item.slug)}>{item.name}</button>)}
              </div>
            )}
            <div className="mb-7 flex flex-wrap gap-2" aria-label="Filter tours by category">
              <button className={`rounded-full px-4 py-2 text-sm font-semibold ${category === '' ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" onClick={() => setCategory('')}>All experiences</button>
              {categories.map((item) => <button className={`rounded-full px-4 py-2 text-sm font-semibold ${category === item ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" key={item} onClick={() => setCategory(item)}>{item}</button>)}
            </div>
            <p className="mb-5 flex flex-wrap items-center gap-2 text-sm text-[#52615b]" role="status">
              <span className="font-semibold text-[#203b35]">{visibleTours.length}</span>
              <span>{visibleTours.length === 1 ? 'experience' : 'experiences'}</span>
              {region && <><span aria-hidden="true">·</span><span>{region.name}</span></>}
              {collection && <><span aria-hidden="true">·</span><span>{collection.label}</span></>}
              {destination && <><span aria-hidden="true">·</span><span>{destinationNames.get(destination) || destination}</span></>}
              {category && <><span aria-hidden="true">·</span><span>{category}</span></>}
            </p>
            {visibleTours.some((tour) => tour.promotion?.sponsored) && (
              <p className="-mt-3 mb-5 text-xs text-[#735744]">Sponsored results are paid placements and are always labelled.</p>
            )}
            <p className="mb-5 text-xs text-[#735744]">Tap Compare on any card to line up to four experiences side by side.</p>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {visibleTours.map((tour) => <TourCard currency={currency} key={tour.slug} tour={tour} />)}
              {catalogue.tours.length === 0 && <p className="text-[#52615b]">Tours are being added. Please check back soon.</p>}
              {catalogue.tours.length > 0 && visibleTours.length === 0 && <p className="text-[#52615b]">No experiences match this destination and category yet. Try All experiences, All Kenya or another category.</p>}
            </div>
          </>
        )}
      </section>
    </PageShell>
  );
}

function ServicesPage({ catalogue, currency, loading, error, retry }) {
  const [destination, setDestination] = useState('');
  const [serviceType, setServiceType] = useState('');
  const services = catalogue.services || [];
  const destinationNames = new Map(catalogue.destinations.map((item) => [item.slug, item.name]));
  const destinationSlugs = [...new Set(services.map((service) => service.destination).filter(Boolean))];
  const serviceTypeLabels = [...new Set(services.map((service) => service.service_type_label).filter(Boolean))].sort();
  const operators = (catalogue.operators || []).filter((operator) => operator.slug);
  const visibleServices = services.filter((service) => (
    (!destination || service.destination === destination)
    && (!serviceType || service.service_type_label === serviceType)
  ));

  return (
    <PageShell>
      <PageBanner
        eyebrow="Every detail of the journey"
        title="Transfers, guides, vehicles and the services that hold a trip together."
        description="Safari and tour operators list the extras they run themselves: airport pickups, private guides, 4x4 hire, photography, catering and equipment. Prices are a starting point, so send a quote request with your dates."
      />
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <SectionHeading
          eyebrow="Travel services"
          title="Services arranged directly with the operator."
          description="Filter by what you need or by destination, then request a quote on WhatsApp. Nothing is charged online for these services."
        />
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
          <>
            <div className="mb-4 flex flex-wrap gap-2" aria-label="Filter services by destination">
              <button className={`rounded-full px-4 py-2 text-sm font-semibold ${destination === '' ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" onClick={() => setDestination('')}>All Kenya</button>
              {destinationSlugs.map((slug) => (
                <button className={`rounded-full px-4 py-2 text-sm font-semibold ${destination === slug ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" key={slug} onClick={() => setDestination(slug)}>
                  {destinationNames.get(slug) || slug.replace(/-/g, ' ')}
                </button>
              ))}
            </div>
            <div className="mb-7 flex flex-wrap gap-2" aria-label="Filter services by type">
              <button className={`rounded-full px-4 py-2 text-sm font-semibold ${serviceType === '' ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" onClick={() => setServiceType('')}>All services</button>
              {serviceTypeLabels.map((label) => (
                <button className={`rounded-full px-4 py-2 text-sm font-semibold ${serviceType === label ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`} type="button" key={label} onClick={() => setServiceType(label)}>{label}</button>
              ))}
            </div>
            <p className="mb-5 flex flex-wrap items-center gap-2 text-sm text-[#52615b]" role="status">
              <span className="font-semibold text-[#203b35]">{visibleServices.length}</span>
              <span>{visibleServices.length === 1 ? 'service' : 'services'}</span>
              {destination && <><span aria-hidden="true">·</span><span>{destinationNames.get(destination) || destination}</span></>}
              {serviceType && <><span aria-hidden="true">·</span><span>{serviceType}</span></>}
            </p>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {visibleServices.map((service) => <ServiceCard currency={currency} key={service.slug} service={service} />)}
              {services.length === 0 && <p className="text-[#52615b]">Services are being added. Please check back soon, or ask our team for a transfer or guide.</p>}
              {services.length > 0 && visibleServices.length === 0 && <p className="text-[#52615b]">No services match these filters yet. Try All Kenya or All services.</p>}
            </div>
            {operators.length > 0 && (
              <div className="mt-16 border-t border-[#e9e5db] pt-10">
                <SectionHeading eyebrow="Meet the operators" title="Registered safari and tour operators." description="Every operator below publishes their own tours and services. Open a profile to see everything they run." />
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {operators.map((operator) => (
                    <a className="rounded-2xl border border-[#e9e5db] bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-lg" href={`/operators/${operator.slug}`} key={operator.slug}>
                      <p className="text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{operator.business_type_labels.join(' · ') || 'Tour operator'}</p>
                      <h3 className="display-font mt-2 text-2xl text-[#203b35]">{operator.name}</h3>
                      {operator.location && <p className="mt-1 text-sm text-[#52615b]">{operator.location}</p>}
                      {operator.description && <p className="mt-2 line-clamp-2 text-sm leading-6 text-[#52615b]">{operator.description}</p>}
                      <span className="mt-3 inline-flex text-sm font-semibold text-[#9a5534]">View profile →</span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </section>
    </PageShell>
  );
}

const PROPERTY_TYPE_LABELS = {
  hotel: ['Hotel', 'Hotels'],
  lodge: ['Lodge', 'Lodges'],
  resort: ['Resort', 'Resorts'],
  apartment: ['Apartment', 'Apartments'],
  rental: ['Vacation rental', 'Vacation rentals'],
  hostel: ['Hostel', 'Hostels'],
};

function propertyTypeLabel(type, plural = false) {
  const labels = PROPERTY_TYPE_LABELS[type];
  if (!labels) return type ? type.replace(/[-_]/g, ' ') : 'Accommodation';
  return plural ? labels[1] : labels[0];
}

function countLabel(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

function RegionTile({ region, catalogue }) {
  const counts = regionListingCounts(region, catalogue);

  return (
    <a className="group relative flex min-h-52 overflow-hidden rounded-2xl text-white shadow-sm transition hover:-translate-y-1 hover:shadow-xl" href={`/destinations.html?region=${encodeURIComponent(region.slug)}`}>
      <img className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105" src={imageUrl(region.image)} alt={region.imageAlt} loading="lazy" />
      <span className="absolute inset-0 bg-gradient-to-t from-[#0d211d]/90 via-[#0d211d]/40 to-transparent" aria-hidden="true" />
      <span className="relative z-10 mt-auto block p-4">
        <span className="block text-[0.65rem] font-bold uppercase tracking-[0.18em] text-[#a9e2e5]">{region.tagline}</span>
        <span className="display-font mt-1 block text-xl leading-tight">{region.name}</span>
        <span className="mt-1 block text-xs text-white/75">{countLabel(counts.tours, 'experience', 'experiences')} · {countLabel(counts.stays, 'stay', 'stays')}</span>
      </span>
    </a>
  );
}

function FilterChip({ active, children, onClick }) {
  return (
    <button
      className={`rounded-full px-4 py-2 text-sm font-semibold ${active ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b]'}`}
      type="button"
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function PropertiesPage({ catalogue, currency, loading, error, retry }) {
  const params = new URLSearchParams(window.location.search);
  const [destination, setDestination] = useState(params.get('destination') || '');
  const [propertyType, setPropertyType] = useState(params.get('type') || '');
  const [collectionSlug, setCollectionSlug] = useState(() => findCategory(params.get('collection'))?.slug || '');
  const [regionSlug, setRegionSlug] = useState(() => findRegion(params.get('region'))?.slug || '');
  const collection = findCategory(collectionSlug);
  const region = findRegion(regionSlug);
  const properties = catalogue.properties || [];
  const scoped = region ? properties.filter((item) => inRegion(region, item)) : properties;
  const inCollection = collection ? scoped.filter(collection.matches) : scoped;
  const destinationNames = new Map(catalogue.destinations.map((item) => [item.slug, item.name]));
  const destinationSlugs = [...new Set(inCollection.map((item) => item.destination).filter(Boolean))];
  const typeSlugs = [...new Set(inCollection.map((item) => item.property_type).filter(Boolean))];
  const visible = sortPromotedFirst(inCollection.filter((item) => (
    (!destination || item.destination === destination)
    && (!propertyType || item.property_type === propertyType)
  )));

  return (
    <PageShell>
      <PageBanner
        eyebrow="Places to stay"
        title="Hotels, lodges, resorts and vacation rentals across Kenya."
        description="Every stay below is listed by the host who runs it: city hotels, beach lodges, safari camps, resorts and self-catering rentals. Compare what is included, then ask for a quote with your dates."
      />
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <SectionHeading
          eyebrow="Accommodation"
          title="Find the base that fits the trip."
          description="Filter by the kind of property or by destination. Rates are per night and shown as a starting price, so send a request for an exact quote."
        />
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
          <>
            {region && (
              <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-[#e9eee8] px-4 py-3 text-sm text-[#203b35]">
                <span className="font-semibold">Browsing {region.name}</span>
                <span className="text-[#52615b]">{region.tagline}</span>
                <a className="ml-auto font-semibold text-[#9a5534] hover:underline" href="/properties.html">Clear region ✕</a>
              </div>
            )}
            <div className="mb-4 flex flex-wrap items-center gap-2" aria-label="Browse accommodations by category">
              <span className="mr-1 text-xs font-bold uppercase tracking-wider text-[#735744]">Categories</span>
              <FilterChip active={collectionSlug === ''} onClick={() => setCollectionSlug('')}>All stays</FilterChip>
              {categoriesFor('stays').map((category) => (
                <FilterChip active={collectionSlug === category.slug} key={category.slug} onClick={() => setCollectionSlug(collectionSlug === category.slug ? '' : category.slug)}>
                  {category.label}
                </FilterChip>
              ))}
              <a className="ml-auto text-sm font-semibold text-[#9a5534] hover:underline" href="/explore.html">Explore categories →</a>
            </div>
            <div className="mb-4 flex flex-wrap gap-2" aria-label="Filter accommodations by type">
              <FilterChip active={propertyType === ''} onClick={() => setPropertyType('')}>All property types</FilterChip>
              {typeSlugs.map((type) => (
                <FilterChip active={propertyType === type} key={type} onClick={() => setPropertyType(type)}>{propertyTypeLabel(type, true)}</FilterChip>
              ))}
            </div>
            {destinationSlugs.length > 1 && (
              <div className="mb-7 flex flex-wrap gap-2" aria-label="Filter accommodations by destination">
                <FilterChip active={destination === ''} onClick={() => setDestination('')}>{region ? `All ${region.name}` : 'All Kenya'}</FilterChip>
                {destinationSlugs.map((slug) => (
                  <FilterChip active={destination === slug} key={slug} onClick={() => setDestination(slug)}>
                    {destinationNames.get(slug) || slug.replace(/-/g, ' ')}
                  </FilterChip>
                ))}
              </div>
            )}
            <p className="mb-5 flex flex-wrap items-center gap-2 text-sm text-[#52615b]" role="status">
              <span className="font-semibold text-[#203b35]">{visible.length}</span>
              <span>{visible.length === 1 ? 'place to stay' : 'places to stay'}</span>
              {region && <><span aria-hidden="true">·</span><span>{region.name}</span></>}
              {collection && <><span aria-hidden="true">·</span><span>{collection.label}</span></>}
              {propertyType && <><span aria-hidden="true">·</span><span>{propertyTypeLabel(propertyType, true)}</span></>}
              {destination && <><span aria-hidden="true">·</span><span>{destinationNames.get(destination) || destination}</span></>}
            </p>
            {visible.some((item) => item.promotion?.sponsored) && (
              <p className="-mt-3 mb-5 text-xs text-[#735744]">Sponsored results are paid placements and are always labelled.</p>
            )}
            <p className="mb-5 text-xs text-[#735744]">Tap Compare on any card to line up to four stays side by side.</p>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {visible.map((property) => <PropertyCard currency={currency} key={property.slug} property={property} />)}
              {properties.length === 0 && <p className="text-[#52615b]">Accommodation is being added. Please check back soon, or ask our team to find something for your dates.</p>}
              {properties.length > 0 && visible.length === 0 && <p className="text-[#52615b]">Nothing matches these filters yet. Try All stays, All property types or All Kenya.</p>}
            </div>
            {typeSlugs.length > 0 && (
              <p className="mt-10 text-sm leading-6 text-[#52615b]">
                Looking for something specific? Our team matches guests to hotels, lodges, resorts and private rentals that are not always published online.{' '}
                <a className="font-semibold text-[#9a5534] hover:underline" href="/contact.html">Tell us what you need</a>.
              </p>
            )}
          </>
        )}
      </section>
      <section className="bg-[#efeee7] px-5 py-14 sm:px-8 sm:py-20">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <SectionHeading
            eyebrow="For property owners"
            title="Do you host guests in Kenya?"
            description="List your hotel, lodge, camp, resort or vacation rental on the marketplace and manage rooms and bookings from the partner dashboard."
          />
          <ButtonLink className="shrink-0" href="/partner/register">Become a host</ButtonLink>
        </div>
      </section>
    </PageShell>
  );
}

function operatorListingCounts(catalogue, slug) {
  return {
    tours: (catalogue.tours || []).filter((item) => item.operator?.slug === slug).length,
    properties: (catalogue.properties || []).filter((item) => item.operator?.slug === slug).length,
    services: (catalogue.services || []).filter((item) => item.operator?.slug === slug).length,
  };
}

function operatorCountSummary(counts) {
  const plural = (count, one, many) => `${count} ${count === 1 ? one : many}`;
  return [
    counts.tours ? plural(counts.tours, 'tour', 'tours') : '',
    counts.properties ? plural(counts.properties, 'stay', 'stays') : '',
    counts.services ? plural(counts.services, 'service', 'services') : '',
  ].filter(Boolean).join(' · ');
}

function SafariOperatorsPage({ catalogue, loading, error, retry }) {
  const [businessType, setBusinessType] = useState('');
  const operators = (catalogue.operators || []).filter((operator) => operator.slug);
  const businessTypes = [...new Set(operators.flatMap((operator) => operator.business_type_labels || []))].sort();
  const visible = operators.filter((operator) => (
    !businessType || (operator.business_type_labels || []).includes(businessType)
  ));

  return (
    <PageShell>
      <PageBanner
        eyebrow="Licensed safari and tour operators"
        title="Book with the operators who actually run the trip."
        description="These are the licensed companies listing on the marketplace. Each one publishes its own tours, safaris, transfers and experiences, so you can read the profile, see the prices, and deal directly with the team that leads the day."
      />
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <SectionHeading
          eyebrow="Meet the operators"
          title="Tour companies, safari operators and travel specialists."
          description="Filter by the kind of operator you are looking for, open a profile, and see everything they run across Kenya."
        />
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
          <>
            <div className="mb-7 flex flex-wrap gap-2" aria-label="Filter operators by business type">
              <FilterChip active={businessType === ''} onClick={() => setBusinessType('')}>All operators</FilterChip>
              {businessTypes.map((label) => (
                <FilterChip active={businessType === label} key={label} onClick={() => setBusinessType(label)}>{label}</FilterChip>
              ))}
            </div>
            <p className="mb-5 flex flex-wrap items-center gap-2 text-sm text-[#52615b]" role="status">
              <span className="font-semibold text-[#203b35]">{visible.length}</span>
              <span>{visible.length === 1 ? 'operator' : 'operators'}</span>
              {businessType && <><span aria-hidden="true">·</span><span>{businessType}</span></>}
            </p>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {visible.map((operator) => {
                const summary = operatorCountSummary(operatorListingCounts(catalogue, operator.slug));
                return (
                  <article className="flex flex-col overflow-hidden rounded-2xl border border-[#e9e5db] bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:shadow-lg" key={operator.slug}>
                    <div className="flex items-center gap-3">
                      {operator.logo_url ? (
                        <img className="h-14 w-14 shrink-0 rounded-full object-cover" src={imageUrl(operator.logo_url)} alt="" loading="lazy" />
                      ) : (
                        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[#e9eee8] text-lg font-bold text-[#203b35]" aria-hidden="true">{operator.name.slice(0, 1)}</span>
                      )}
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{(operator.business_type_labels || []).join(' · ') || 'Tour operator'}</p>
                        <h3 className="display-font text-2xl leading-tight text-[#203b35]">{operator.name}</h3>
                      </div>
                    </div>
                    {operator.location && <p className="mt-3 text-sm text-[#52615b]">Based in {operator.location}</p>}
                    {operator.description && <p className="mt-2 line-clamp-3 text-sm leading-6 text-[#52615b]">{operator.description}</p>}
                    {summary && <p className="mt-3 text-xs font-semibold text-[#735744]">On the marketplace: {summary}</p>}
                    <a className="mt-auto inline-flex pt-5 text-sm font-semibold text-[#9a5534] hover:underline" href={`/operators/${operator.slug}`}>View operator profile →</a>
                  </article>
                );
              })}
              {operators.length === 0 && <p className="text-[#52615b]">Operator profiles are being added. In the meantime, our team can connect you with a licensed company for your dates.</p>}
              {operators.length > 0 && visible.length === 0 && <p className="text-[#52615b]">No operators match this business type yet. Try All operators.</p>}
            </div>
            <div className="mt-12 rounded-2xl bg-[#e9eee8] p-6 sm:p-8">
              <h2 className="display-font text-2xl text-[#203b35]">Run safaris or tours in Kenya?</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#52615b]">Licensed operators can publish tours, safaris, transfers and travel services on the marketplace, with no listing fee to start.</p>
              <ButtonLink className="mt-5" href="/partner/register">List your company</ButtonLink>
            </div>
          </>
        )}
      </section>
    </PageShell>
  );
}

function DestinationsPage({ catalogue, loading, error, retry }) {
  const params = new URLSearchParams(window.location.search);
  const [regionSlug, setRegionSlug] = useState(() => findRegion(params.get('region'))?.slug || '');
  const activeRegion = findRegion(regionSlug);
  const destinations = catalogue.destinations || [];
  const visibleRegions = activeRegion ? [activeRegion] : REGIONS;
  const toursIn = (slug) => (catalogue.tours || []).filter((tour) => tour.destination === slug).length;
  const staysIn = (slug) => (catalogue.properties || []).filter((item) => item.destination === slug).length;

  return (
    <PageShell>
      <PageBanner
        eyebrow="Browse by region"
        title="Six regions, one country."
        description="Nairobi and the Rift Valley lakes, the Maasai Mara, Amboseli, Tsavo, the Indian Ocean coast and the Mount Kenya highlands. Pick a region, then a destination, and go straight to the tours and places to stay there."
      />
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <SectionHeading
          eyebrow="Where to go"
          title="Choose a region, then a destination."
          description="Every destination below has experiences and accommodation listed by local partners. Counts show what is published right now."
        />
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : (
          <>
            <div className="mb-8 flex flex-wrap gap-2" aria-label="Filter destinations by region">
              <FilterChip active={regionSlug === ''} onClick={() => setRegionSlug('')}>All regions</FilterChip>
              {REGIONS.map((region) => (
                <FilterChip active={regionSlug === region.slug} key={region.slug} onClick={() => setRegionSlug(regionSlug === region.slug ? '' : region.slug)}>
                  {region.name}
                </FilterChip>
              ))}
            </div>
            <div className="space-y-16">
              {visibleRegions.map((region) => {
                const regionItems = regionDestinations(region, destinations);
                const counts = regionListingCounts(region, catalogue);
                return (
                  <div key={region.slug}>
                    <div className="mb-6 flex flex-col gap-4 border-b border-[#e9e5db] pb-4 sm:flex-row sm:items-end sm:justify-between">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#a75f3a]">{region.tagline}</p>
                        <h3 className="display-font mt-1 text-3xl text-[#203b35]">{region.name}</h3>
                        <p className="mt-1 max-w-2xl text-sm leading-6 text-[#52615b]">{region.description}</p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <a className="rounded-full bg-[#203b35] px-4 py-2 text-sm font-semibold text-white hover:bg-[#31554b]" href={regionHref(region, 'tours')}>{counts.tours} {counts.tours === 1 ? 'experience' : 'experiences'}</a>
                        <a className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" href={regionHref(region, 'stays')}>{counts.stays} {counts.stays === 1 ? 'place to stay' : 'places to stay'}</a>
                      </div>
                    </div>
                    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                      {regionItems.map((item) => {
                        const tourCount = toursIn(item.slug);
                        const stayCount = staysIn(item.slug);
                        return (
                          <article className="flex flex-col overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm" key={item.slug}>
                            <img className="h-44 w-full object-cover" src={imageUrl(item.image_url)} alt={item.name} loading="lazy" />
                            <div className="flex flex-1 flex-col p-5">
                              <h4 className="display-font text-2xl text-[#203b35]">{item.name}</h4>
                              <p className="mt-2 line-clamp-3 text-sm leading-6 text-[#52615b]">{item.description}</p>
                              <p className="mt-3 text-xs font-semibold text-[#735744]">
                                {tourCount} {tourCount === 1 ? 'experience' : 'experiences'} · {stayCount} {stayCount === 1 ? 'place to stay' : 'places to stay'}
                              </p>
                              <div className="mt-auto flex flex-wrap gap-2 pt-4">
                                <a className="rounded-full bg-[#203b35] px-4 py-2 text-sm font-semibold text-white hover:bg-[#31554b]" href={`/tours.html?destination=${encodeURIComponent(item.slug)}`}>Tours</a>
                                <a className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" href={`/properties.html?destination=${encodeURIComponent(item.slug)}`}>Places to stay</a>
                              </div>
                            </div>
                          </article>
                        );
                      })}
                      {regionItems.length === 0 && <p className="text-[#52615b]">Destinations in this region are being added. Ask our team what we can arrange in the meantime.</p>}
                    </div>
                  </div>
                );
              })}
              {destinations.length === 0 && <p className="text-[#52615b]">Destinations are being added. Please check back soon.</p>}
            </div>
          </>
        )}
      </section>
      <section className="bg-[#efeee7] px-5 py-14 sm:px-8 sm:py-20">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[1.2fr_1fr] lg:items-center">
          <SectionHeading
            eyebrow="Not sure where to start?"
            title="Tell us the trip you have in mind."
            description="Two nights or two weeks, coast or savannah, a family group or a solo escape. Our team will suggest an itinerary built around the places that fit."
          />
          <div className="flex flex-wrap gap-3">
            <ButtonLink href="/booking.html">Plan a trip with us</ButtonLink>
            <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/tours.html" secondary>Browse all tours</ButtonLink>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function formatPostDate(value) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
}

function formatReviewDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function NewsletterForm({ source = 'website', className = '' }) {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    if (status === 'loading') return;
    setStatus('loading');
    setMessage('');
    try {
      const response = await fetch('/api/newsletter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ email, source }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || 'That signup did not go through. Please try again.');
      setStatus('done');
      setMessage(data.message || 'You are on the list.');
      setEmail('');
    } catch (error) {
      setStatus('error');
      setMessage(getErrorMessage(error));
    }
  }

  return (
    <div className={className}>
      <form className="flex flex-col gap-2 sm:flex-row" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor={`newsletter-email-${source}`}>Email address</label>
        <input
          className="w-full rounded-full border border-white/25 bg-white/10 px-4 py-2.5 text-sm text-white placeholder:text-white/55 focus:border-white/70 focus:outline-none"
          id={`newsletter-email-${source}`}
          name="email"
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          required
          type="email"
          value={email}
        />
        <button
          className="shrink-0 rounded-full bg-[#b96e45] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#a75f3a] disabled:opacity-70"
          disabled={status === 'loading'}
          type="submit"
        >
          {status === 'loading' ? 'Joining…' : 'Join the list'}
        </button>
      </form>
      <p className="mt-2 text-xs leading-5 text-[#a9b8b1]" aria-live="polite">
        {status === 'error' ? <span className="text-[#ffd0c2]">{message}</span> : status === 'done' ? <span className="text-[#a9e2e5]">{message}</span> : 'One email a month with travel notes from Kenya. Unsubscribe any time.'}
      </p>
    </div>
  );
}

function NewsletterBand() {
  return (
    <section className="mx-auto max-w-7xl scroll-mt-8 px-5 pb-16 sm:px-8 sm:pb-20" id="newsletter">
      <div className="rounded-3xl bg-[#203b35] px-6 py-10 text-white sm:px-10 sm:py-12">
        <div className="grid gap-8 lg:grid-cols-[1.15fr_1fr] lg:items-center">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a9e2e5]">Travel notes</p>
            <h2 className="display-font mt-3 text-3xl sm:text-4xl">One email a month, from the coast and the parks.</h2>
            <p className="mt-3 max-w-xl text-sm leading-6 text-white/75">Seasons worth booking, new experiences and the quiet weeks we would choose ourselves. Written by the team in Kenya, never more than once a month.</p>
          </div>
          <NewsletterForm source="home" />
        </div>
      </div>
    </section>
  );
}

function ReviewQuote({ review }) {
  return (
    <article className="flex h-full flex-col rounded-2xl border border-[#e9e5db] bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <StarRow rating={review.rating} />
        <span className="text-xs text-[#8a8172]">{formatReviewDate(review.created_at)}</span>
      </div>
      <blockquote className="mt-3 flex-1 text-sm leading-6 text-[#33443f]">“{review.comment}”</blockquote>
      <footer className="mt-5 flex items-center gap-3 border-t border-[#ece9e0] pt-4 text-xs text-[#52615b]">
        {review.listing_image && (
          <img className="h-11 w-11 shrink-0 rounded-lg object-cover" src={imageUrl(review.listing_image)} alt="" loading="lazy" />
        )}
        <span className="min-w-0">
          <span className="block truncate font-semibold text-[#203b35]">{review.reviewer_name}</span>
          <span className="block truncate">{review.listing_name}</span>
        </span>
        {review.url && <a className="ml-auto shrink-0 font-semibold text-[#9a5534] hover:underline" href={review.url}>View →</a>}
      </footer>
    </article>
  );
}

function useCommunityReviews(limit, targetType = '') {
  const [state, setState] = useState({ loading: true, error: '', data: null });

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: String(limit) });
    if (targetType) params.set('target_type', targetType);
    setState((current) => ({ ...current, loading: true, error: '' }));
    fetch(`/api/community/reviews?${params}`, { signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Guest reviews could not be loaded (HTTP ${response.status}).`);
        return response.json();
      })
      .then((data) => setState({ loading: false, error: '', data }))
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setState({ loading: false, error: getErrorMessage(error), data: null });
      });
    return () => controller.abort();
  }, [limit, targetType]);

  return state;
}

function CommunityReviewsStrip() {
  const { data } = useCommunityReviews(3);
  const reviews = data?.reviews || [];
  if (!reviews.length) return null;

  return (
    <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 sm:py-20">
      <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
        <SectionHeading
          eyebrow="Community reviews"
          title="What guests say when they get home."
          description="Every review below comes from a traveller who booked through the marketplace. Read them before you choose where to stay and what to do."
        />
        <ButtonLink className="mb-8 self-start" href="/reviews.html">All community reviews →</ButtonLink>
      </div>
      <div className="grid gap-5 md:grid-cols-3">
        {reviews.map((review) => <ReviewQuote key={review.id} review={review} />)}
      </div>
    </section>
  );
}

function CommunityReviewsPage() {
  const [targetType, setTargetType] = useState('');
  const [rating, setRating] = useState(0);
  const { loading, error, data } = useCommunityReviews(48, targetType);
  const summary = data?.summary;
  const reviews = (data?.reviews || []).filter((review) => !rating || review.rating === rating);

  return (
    <PageShell>
      <PageBanner
        eyebrow="Community reviews"
        title="Honest words from travellers, not marketing copy."
        description="Reviews are written by guests after a stay or an experience booked here. Ratings feed the badges and rankings you see across the marketplace."
      />
      <section className="mx-auto max-w-7xl px-5 py-12 sm:px-8 sm:py-16">
        {!summary ? (
          error ? null : <p className="text-sm text-[#52615b]" role="status">Loading guest reviews…</p>
        ) : summary.review_count === 0 ? (
          <div className="rounded-3xl border border-[#e9e5db] bg-white p-8 text-center shadow-sm sm:p-12">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#a75f3a]">No reviews yet</p>
            <h2 className="display-font mt-3 text-3xl text-[#203b35]">Be the first guest to review.</h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-[#52615b]">Reviews open after a completed booking: book a tour or a stay, travel, then write your review from <a className="font-semibold text-[#9a5534] hover:underline" href="/my-bookings">My bookings</a>. The ratings shown on each listing come only from those reviews, so this page stays honest.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <ButtonLink href="/tours.html">Book an experience</ButtonLink>
              <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/properties.html" secondary>Find a place to stay</ButtonLink>
            </div>
          </div>
        ) : (
          <>
            <div className="grid gap-8 rounded-3xl border border-[#e9e5db] bg-white p-6 shadow-sm lg:grid-cols-[1fr_1.2fr] lg:items-center sm:p-8">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#a75f3a]">Rating across the marketplace</p>
                <p className="mt-3 flex items-baseline gap-2">
                  <span className="display-font text-5xl text-[#203b35]">{summary ? Number(summary.rating || 0).toFixed(1) : '—'}</span>
                  <span className="text-sm text-[#52615b]">/ 5</span>
                </p>
                <div className="mt-2"><StarRow rating={summary?.rating || 0} /></div>
                <p className="mt-3 text-sm text-[#52615b]">
                  {summary ? `${summary.review_count} review${summary.review_count === 1 ? '' : 's'} on this feed` : 'Loading reviews…'}
                  {summary ? ` · ${summary.tour_count} experience${summary.tour_count === 1 ? '' : 's'} and ${summary.property_count} stay${summary.property_count === 1 ? '' : 's'} reviewed across the site` : ''}
                </p>
              </div>
              <div className="space-y-2" aria-hidden={!summary}>
                {(summary?.distribution || []).map((row) => (
                  <div className="flex items-center gap-3 text-sm text-[#52615b]" key={row.rating}>
                    <span className="w-10 shrink-0 font-semibold text-[#203b35]">{row.rating} ★</span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-[#efeee7]">
                      <span className="block h-full rounded-full bg-[#b96e45]" style={{ width: `${row.share}%` }} />
                    </span>
                    <span className="w-8 shrink-0 text-right text-xs">{row.count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-2" aria-label="Filter community reviews">
              <FilterChip active={targetType === ''} onClick={() => setTargetType('')}>Everything</FilterChip>
              <FilterChip active={targetType === 'tour'} onClick={() => setTargetType('tour')}>Experiences</FilterChip>
              <FilterChip active={targetType === 'property'} onClick={() => setTargetType('property')}>Places to stay</FilterChip>
              <span className="mx-1 h-5 w-px bg-[#dcd8cc]" aria-hidden="true" />
              <FilterChip active={rating === 0} onClick={() => setRating(0)}>All ratings</FilterChip>
              {[5, 4, 3].map((star) => (
                <FilterChip active={rating === star} key={star} onClick={() => setRating(star)}>{star} ★</FilterChip>
              ))}
            </div>
          </>
        )}

        {error && <p className="mt-6 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</p>}
        {loading && !data && <p className="mt-6 text-sm text-[#52615b]" role="status">Loading guest reviews…</p>}
        {!loading && !error && summary?.review_count > 0 && reviews.length === 0 && (
          <p className="mt-6 rounded-2xl border border-dashed border-[#d9d3c4] p-8 text-center text-sm text-[#52615b]">No reviews match that filter yet. Try another rating or type.</p>
        )}
        <div className="mt-6 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {reviews.map((review) => <ReviewQuote key={review.id} review={review} />)}
        </div>
      </section>
      <section className="bg-[#efeee7] px-5 py-14 sm:px-8 sm:py-16">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-6 sm:flex-row sm:items-center">
          <SectionHeading eyebrow="Travel, then tell us" title="The next review could be yours." description="Book a tour or a stay, travel with a local team, then share what worked. Your words help the next guest choose well." />
          <div className="flex flex-wrap gap-3">
            <ButtonLink href="/tours.html">Browse experiences</ButtonLink>
            <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/properties.html" secondary>Browse stays</ButtonLink>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function GalleryLightbox({ photos, index, onClose, onStep }) {
  const photo = photos[index];

  useEffect(() => {
    function handleKey(event) {
      if (event.key === 'Escape') onClose();
      else if (event.key === 'ArrowRight') onStep(1);
      else if (event.key === 'ArrowLeft') onStep(-1);
    }
    document.addEventListener('keydown', handleKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose, onStep]);

  if (!photo) return null;
  return (
    <div
      aria-label={photo.title}
      aria-modal="true"
      className="fixed inset-0 z-[95] flex flex-col bg-[#0f1b18]/95 px-4 py-4 text-white"
      onClick={onClose}
      role="dialog"
    >
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/60">{photo.place}</p>
        <button className="rounded-full border border-white/25 px-4 py-2 text-sm font-semibold transition hover:border-white/70" onClick={onClose} type="button">Close</button>
      </div>
      <div className="flex min-h-0 flex-1 items-center justify-center gap-2 py-3" onClick={(event) => event.stopPropagation()}>
        <button aria-label="Previous photo" className="shrink-0 rounded-full border border-white/25 p-2.5 transition hover:border-white/70" onClick={() => onStep(-1)} type="button">
          <svg aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" viewBox="0 0 24 24"><path d="m14.5 5-7 7 7 7" /></svg>
        </button>
        <figure className="flex min-h-0 flex-col items-center">
          <img alt={photo.alt} className="max-h-[74vh] w-auto max-w-full rounded-xl object-contain shadow-2xl" src={photo.src} />
          <figcaption className="mt-4 text-center">
            <span className="block font-semibold">{photo.title}</span>
            <span className="mt-1 block text-xs text-white/60">{photo.place}</span>
            {photo.href && <a className="mt-2 inline-block text-sm font-semibold text-[#a9e2e5] hover:underline" href={photo.href}>View this listing →</a>}
          </figcaption>
        </figure>
        <button aria-label="Next photo" className="shrink-0 rounded-full border border-white/25 p-2.5 transition hover:border-white/70" onClick={() => onStep(1)} type="button">
          <svg aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" viewBox="0 0 24 24"><path d="m9.5 5 7 7-7 7" /></svg>
        </button>
      </div>
      <p className="text-center text-xs text-white/50">{index + 1} of {photos.length} · Use the arrow keys to browse</p>
    </div>
  );
}

function PhotoGalleryPage({ catalogue, loading }) {
  const [regionSlug, setRegionSlug] = useState('');
  const [scope, setScope] = useState('all');
  const [activeIndex, setActiveIndex] = useState(-1);

  const photos = useMemo(() => [...GALLERY_PHOTOS, ...cataloguePhotos(catalogue)], [catalogue]);
  const regionSlugs = useMemo(() => galleryRegions(catalogue), [catalogue]);
  const visible = photos.filter((photo) => (
    (!regionSlug || photo.region === regionSlug)
    && (scope === 'all' || (scope === 'listings' ? Boolean(photo.href) : !photo.href))
  ));

  function changeFilter(update) {
    setActiveIndex(-1);
    update();
  }

  function step(direction) {
    setActiveIndex((current) => {
      if (!visible.length) return -1;
      return (current + direction + visible.length) % visible.length;
    });
  }

  return (
    <PageShell>
      <PageBanner
        eyebrow="Photo gallery"
        title="Kenya, one frame at a time."
        description="Dhow sails at sunset, red dust in Tsavo, the lanes of Lamu and the beaches we book every week. Photographs from our destinations and the partners who host you."
      />
      <section className="mx-auto max-w-7xl px-5 py-12 sm:px-8 sm:py-16">
        <div className="flex flex-wrap items-center gap-2" aria-label="Filter photos by region">
          <FilterChip active={regionSlug === ''} onClick={() => changeFilter(() => setRegionSlug(''))}>All regions</FilterChip>
          {regionSlugs.map((slug) => (
            <FilterChip active={regionSlug === slug} key={slug} onClick={() => changeFilter(() => setRegionSlug(slug))}>
              {findRegion(slug)?.name || slug}
            </FilterChip>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Filter photos by source">
          <FilterChip active={scope === 'all'} onClick={() => changeFilter(() => setScope('all'))}>Everything</FilterChip>
          <FilterChip active={scope === 'curated'} onClick={() => changeFilter(() => setScope('curated'))}>Destinations &amp; coast</FilterChip>
          <FilterChip active={scope === 'listings'} onClick={() => changeFilter(() => setScope('listings'))}>From our listings</FilterChip>
        </div>

        {loading && <p className="mt-6 text-sm text-[#52615b]" role="status">Loading photographs from the catalogue…</p>}
        <div className="mt-8 columns-1 gap-4 sm:columns-2 lg:columns-3">
          {visible.map((photo, index) => (
            <button
              className="group relative mb-4 block w-full break-inside-avoid overflow-hidden rounded-2xl bg-[#e7e3d8] text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#203b35]"
              key={`${photo.src}-${photo.title}`}
              onClick={() => setActiveIndex(index)}
              type="button"
            >
              <img alt={photo.alt} className="w-full object-cover transition duration-500 group-hover:scale-[1.03]" loading="lazy" src={imageUrl(photo.src)} />
              <span className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 via-black/25 to-transparent p-4 pt-12 text-white">
                <span className="block text-sm font-semibold">{photo.title}</span>
                <span className="block text-xs text-white/75">{photo.place}{photo.href ? ' · listing photo' : ''}</span>
              </span>
            </button>
          ))}
        </div>
        {visible.length === 0 && (
          <p className="mt-8 rounded-2xl border border-dashed border-[#d9d3c4] p-8 text-center text-sm text-[#52615b]">No photographs in this filter yet. Try another region.</p>
        )}
      </section>
      {activeIndex >= 0 && visible[activeIndex] && (
        <GalleryLightbox
          index={activeIndex}
          onClose={() => setActiveIndex(-1)}
          onStep={step}
          photos={visible}
        />
      )}
    </PageShell>
  );
}

const COMPARE_TYPE_LABELS = { tour: 'Experience', property: 'Place to stay' };

function compareListingHref(listing) {
  return listing.type === 'tour'
    ? `/tour-details.html?id=${encodeURIComponent(listing.slug)}`
    : `/booking.html?stay=${encodeURIComponent(listing.slug)}&guests=${listing.guests}`;
}

function comparisonRows(listings, destinationNames, currency) {
  const dash = '—';
  const anyTour = listings.some((listing) => listing.type === 'tour');
  const anyStay = listings.some((listing) => listing.type === 'property');
  const rows = [
    {
      label: 'Price',
      get: (listing) => (listing.type === 'tour'
        ? `${formatPrice(listing.price, currency)} per guest`
        : stayPriceText(listing, currency)),
    },
    {
      label: 'Destination',
      get: (listing) => destinationNames.get(listing.destination) || listing.location || dash,
    },
    {
      label: 'Guest rating',
      get: (listing) => (listing.review_count > 0
        ? `${Number(listing.rating).toFixed(1)} / 5 · ${listing.review_count} review${listing.review_count === 1 ? '' : 's'}`
        : 'No reviews yet'),
    },
    { label: 'Value badges', get: (listing) => (listing.badges || []).join(', ') || dash },
  ];

  if (anyTour) {
    rows.push(
      { label: 'Duration', get: (listing) => (listing.type === 'tour' ? listing.duration || dash : dash) },
      { label: 'Experience type', get: (listing) => (listing.type === 'tour' ? listing.tour_type_label || 'Experience' : dash) },
      {
        label: 'Group size',
        get: (listing) => {
          if (listing.type !== 'tour') return dash;
          const min = listing.min_group_size;
          const max = listing.max_group_size;
          if (!min && !max) return dash;
          return min && max ? `${min}–${max} guests` : `${max || min} guests`;
        },
      },
      { label: 'Group style', get: (listing) => (listing.type === 'tour' ? listing.group_type_label || 'Private group' : dash) },
      { label: 'Languages', get: (listing) => (listing.type === 'tour' && listing.languages?.length ? listing.languages.join(', ') : dash) },
      { label: 'Meeting point', get: (listing) => (listing.type === 'tour' ? listing.pickup_point || dash : dash) },
      { label: 'What is included', get: (listing) => (listing.type === 'tour' && listing.inclusions?.length ? listing.inclusions.slice(0, 6).join(' · ') : dash) },
    );
  }

  if (anyStay) {
    rows.push(
      { label: 'Property type', get: (listing) => (listing.type === 'property' ? propertyTypeLabel(listing.property_type) : dash) },
      { label: 'Neighbourhood', get: (listing) => (listing.type === 'property' ? listing.location || dash : dash) },
      { label: 'Sleeps', get: (listing) => (listing.type === 'property' ? `${listing.guests} guest${listing.guests === 1 ? '' : 's'}` : dash) },
      {
        label: 'Room types',
        get: (listing) => (listing.type === 'property' && listing.room_types > 0
          ? `${listing.room_types} room ${listing.room_types === 1 ? 'type' : 'types'}`
          : dash),
      },
      { label: 'Amenities', get: (listing) => (listing.type === 'property' && listing.amenities?.length ? listing.amenities.slice(0, 8).join(' · ') : dash) },
    );
  }

  rows.push(
    { label: 'Price position', get: (listing) => priceComparisonText(listing.price_comparison) || dash },
    {
      label: 'Run by',
      get: (listing) => (listing.operator?.name
        ? `${listing.operator.name}${listing.operator.location ? ` · ${listing.operator.location}` : ''}`
        : 'Kenya Tours & Marketplace'),
    },
  );

  return rows.map((row) => {
    const values = listings.map((listing) => row.get(listing));
    const distinct = new Set(values.filter((value) => value && value !== dash));
    return { ...row, values, differs: distinct.size > 1 };
  });
}

function ComparePage({ catalogue, currency, loading, error, retry }) {
  const [selection, setSelection] = useState(() => {
    const fromUrl = parseCompareParam(new URLSearchParams(window.location.search).get('items'));
    return fromUrl.length ? fromUrl : readCompare();
  });
  const [copyState, setCopyState] = useState('');

  const resolved = useMemo(() => {
    const byKey = new Map();
    (catalogue.tours || []).forEach((tour) => byKey.set(`tour:${tour.slug}`, { ...tour, type: 'tour' }));
    (catalogue.properties || []).forEach((property) => byKey.set(`property:${property.slug}`, { ...property, type: 'property' }));
    return selection.map((item) => byKey.get(compareKey(item))).filter(Boolean);
  }, [catalogue, selection]);

  const destinationNames = useMemo(() => new Map((catalogue.destinations || []).map((item) => [item.slug, item.name])), [catalogue]);
  const rows = useMemo(() => comparisonRows(resolved, destinationNames, currency), [resolved, destinationNames, currency]);

  useEffect(() => {
    // The shareable URL and the stored selection always describe the same listings.
    replaceCompare(selection);
    const href = compareHref(selection);
    if (`${window.location.pathname}${window.location.search}` !== href) {
      window.history.replaceState({}, '', href);
    }
  }, [selection]);

  useEffect(() => {
    // Drop listings that were removed from the catalogue since the shortlist was saved.
    if (loading || error || selection.length === 0) return;
    const available = new Set([
      ...(catalogue.tours || []).map((tour) => `tour:${tour.slug}`),
      ...(catalogue.properties || []).map((property) => `property:${property.slug}`),
    ]);
    const stillListed = selection.filter((item) => available.has(compareKey(item)));
    if (stillListed.length !== selection.length) setSelection(stillListed);
  }, [catalogue, loading, error, selection]);

  useEffect(() => {
    if (!copyState) return undefined;
    const timer = window.setTimeout(() => setCopyState(''), 4000);
    return () => window.clearTimeout(timer);
  }, [copyState]);

  function remove(listing) {
    setSelection((current) => current.filter((item) => compareKey(item) !== compareKey(listing)));
  }

  function clearAll() {
    setSelection([]);
    clearCompare();
  }

  async function copyLink() {
    const url = `${window.location.origin}${compareHref(selection)}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  }

  return (
    <PageShell>
      <PageBanner
        eyebrow="Compare"
        title="Line up your shortlist, side by side."
        description="Prices, ratings, group sizes, amenities and what each listing includes in one table. Add up to four tours or stays from any page and the shortlist follows you while you browse."
      />
      <section className="mx-auto max-w-7xl px-5 py-12 sm:px-8 sm:py-16">
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : resolved.length === 0 ? (
          <div className="rounded-3xl border border-[#e9e5db] bg-white p-8 text-center shadow-sm sm:p-12">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#a75f3a]">Nothing selected yet</p>
            <h2 className="display-font mt-3 text-3xl text-[#203b35]">Pick two listings and we will do the rest.</h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-[#52615b]">Open any tour or place to stay and tap Compare on the card. Your shortlist follows you across the site, and you can share the finished comparison as a link.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <ButtonLink href="/tours.html">Browse experiences</ButtonLink>
              <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/properties.html" secondary>Browse stays</ButtonLink>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <SectionHeading
                eyebrow="Side by side"
                title={`${resolved.length} listing${resolved.length === 1 ? '' : 's'} in this comparison.`}
                description={resolved.length === 1
                  ? 'Add one more listing to see the differences highlighted.'
                  : 'Highlighted rows differ between your selections.'}
              />
              <div className="mb-8 flex flex-wrap items-center gap-3">
                <button className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" onClick={copyLink} type="button">Copy comparison link</button>
                <button className="text-sm font-semibold text-[#52615b] hover:text-[#203b35]" onClick={clearAll} type="button">Clear all</button>
              </div>
            </div>
            {copyState === 'copied' && <p className="mb-4 text-sm font-semibold text-[#177b5b]" role="status">Comparison link copied.</p>}
            {copyState === 'failed' && <p className="mb-4 text-sm font-semibold text-[#9a5534]" role="status">Your browser blocked the copy. Use the address bar instead.</p>}
            <div className="overflow-x-auto rounded-3xl border border-[#e9e5db] bg-white shadow-sm">
              <table className="w-full min-w-[48rem] border-collapse text-sm">
                <caption className="sr-only">Side-by-side comparison of the selected tours and places to stay</caption>
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 w-32 border-b border-[#efede7] bg-white p-4 text-left align-bottom text-xs font-bold uppercase tracking-wider text-[#735744]" scope="col">
                      Compare
                    </th>
                    {resolved.map((listing) => (
                      <th className="min-w-56 border-b border-l border-[#efede7] p-4 align-top text-left font-normal" key={compareKey(listing)} scope="col">
                        <img alt={listing.name} className="h-28 w-full rounded-xl object-cover" loading="lazy" src={imageUrl(listing.image_url)} />
                        <p className="mt-3 text-[0.65rem] font-bold uppercase tracking-[0.14em] text-[#a75f3a]">{COMPARE_TYPE_LABELS[listing.type]}</p>
                        <p className="display-font mt-1 text-lg leading-snug text-[#203b35]">{listing.name}</p>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <a className="rounded-full bg-[#203b35] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#31554b]" href={compareListingHref(listing)}>View listing</a>
                          <button className="text-xs font-semibold text-[#52615b] hover:text-[#203b35]" onClick={() => remove(listing)} type="button">Remove</button>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr className={row.differs ? 'bg-[#fdf6ee]' : 'bg-white'} key={row.label}>
                      <th className={`sticky left-0 z-10 border-b border-[#efede7] p-4 text-left align-top text-xs font-bold uppercase tracking-wider text-[#735744] ${row.differs ? 'bg-[#fdf6ee]' : 'bg-white'}`} scope="row">
                        {row.label}
                      </th>
                      {row.values.map((value, index) => (
                        <td className="border-b border-l border-[#efede7] p-4 align-top leading-6 text-[#33443f]" key={compareKey(resolved[index])}>
                          {value === '—' ? <span className="text-[#b3ad9f]">—</span> : value}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-xs text-[#735744]">Prices are starting prices per guest or per night. Sponsored listings keep their label in the table.</p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <ButtonLink href="/tours.html">Add an experience</ButtonLink>
              <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/properties.html" secondary>Add a place to stay</ButtonLink>
            </div>
          </>
        )}
      </section>
    </PageShell>
  );
}

function BlogCard({ post }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
      <a href={`/blog/${post.slug}`} aria-label={`Read ${post.title}`}>
        <img className="h-52 w-full object-cover" src={imageUrl(post.image)} alt={post.imageAlt} loading="lazy" />
      </a>
      <div className="flex flex-1 flex-col p-5">
        <p className="text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{post.category} · {post.readingTime}</p>
        <h3 className="display-font mt-2 text-2xl leading-tight text-[#203b35]">
          <a className="hover:underline" href={`/blog/${post.slug}`}>{post.title}</a>
        </h3>
        <p className="mt-2 line-clamp-3 text-sm leading-6 text-[#52615b]">{post.excerpt}</p>
        <div className="mt-auto flex items-center justify-between gap-3 pt-5 text-xs text-[#52615b]">
          <span>{formatPostDate(post.published)}</span>
          <a className="text-sm font-semibold text-[#9a5534] hover:underline" href={`/blog/${post.slug}`}>Read the guide →</a>
        </div>
      </div>
    </article>
  );
}

function BlogPage() {
  const [category, setCategory] = useState('');
  const categories = blogCategories();
  const posts = BLOG_POSTS.filter((post) => !category || post.category === category);

  return (
    <PageShell>
      <PageBanner
        eyebrow="Blogs & travel guides"
        title="Everything we know about visiting Kenya, written down."
        description="Seasons, packing lists, old-town walks, itineraries and how money works here. Practical guides from the team who plan these trips every week."
      />
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <SectionHeading
          eyebrow="The travel journal"
          title="Read up before you fly."
          description="Choose a topic, or start with the season guide if you have not picked your dates yet."
        />
        <div className="mb-7 flex flex-wrap gap-2" aria-label="Filter guides by category">
          <FilterChip active={category === ''} onClick={() => setCategory('')}>All guides</FilterChip>
          {categories.map((label) => (
            <FilterChip active={category === label} key={label} onClick={() => setCategory(label)}>{label}</FilterChip>
          ))}
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((post) => <BlogCard key={post.slug} post={post} />)}
        </div>
        <div className="mt-12 rounded-2xl bg-[#e9eee8] p-6 sm:p-8">
          <h2 className="display-font text-2xl text-[#203b35]">Still have a question?</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#52615b]">The FAQ covers bookings, payments and travelling with us. For anything else, our team answers messages directly.</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <ButtonLink href="/faq.html">Read the FAQ</ButtonLink>
            <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/contact.html" secondary>Ask us directly</ButtonLink>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function BlogArticlePage() {
  const slug = decodeURIComponent(window.location.pathname.replace(/^\/blog\//i, '')).replace(/\/+$/, '');
  const post = findBlogPost(slug);

  if (!post) {
    return (
      <PageShell>
        <section className="mx-auto max-w-3xl px-5 py-20 text-center sm:px-8 sm:py-28">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">Guide not found</p>
          <h1 className="display-font mt-4 text-4xl text-[#203b35]">That guide has moved or never existed.</h1>
          <p className="mt-4 text-[#52615b]">Browse the travel journal for everything we have published about visiting Kenya.</p>
          <div className="mt-7 flex justify-center gap-3">
            <ButtonLink href="/blog.html">All travel guides</ButtonLink>
            <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/index.html" secondary>Go home</ButtonLink>
          </div>
        </section>
      </PageShell>
    );
  }

  const related = (post.related || []).map((relatedSlug) => findBlogPost(relatedSlug)).filter(Boolean);

  return (
    <PageShell>
      <article className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-16">
        <nav className="text-sm text-[#52615b]" aria-label="Breadcrumb">
          <a className="hover:underline" href="/blog.html">Blogs &amp; travel guides</a>
          <span aria-hidden="true"> / </span>
          <span>{post.category}</span>
        </nav>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">{post.category} · {post.readingTime}</p>
        <h1 className="display-font mt-4 text-4xl leading-tight text-[#203b35] sm:text-5xl">{post.title}</h1>
        <p className="mt-4 text-sm text-[#52615b]">{post.author} · {formatPostDate(post.published)}</p>
        <ShareRow className="mt-5" title={post.title} />
        <img className="mt-8 h-72 w-full rounded-3xl object-cover sm:h-96" src={imageUrl(post.image)} alt={post.imageAlt} />
        <p className="mt-8 text-lg leading-8 text-[#3f4f49]">{post.lede}</p>
        {post.sections.map((section) => (
          <section className="mt-9" key={section.heading}>
            <h2 className="display-font text-2xl text-[#203b35] sm:text-3xl">{section.heading}</h2>
            {section.paragraphs.map((paragraph) => (
              <p className="mt-3 leading-7 text-[#52615b]" key={paragraph.slice(0, 40)}>{paragraph}</p>
            ))}
          </section>
        ))}
        {post.tips?.length > 0 && (
          <aside className="mt-10 rounded-2xl bg-[#e9eee8] p-6">
            <h2 className="font-semibold text-[#203b35]">Quick tips</h2>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-[#52615b]">
              {post.tips.map((tip) => (
                <li className="flex gap-2" key={tip}>
                  <span aria-hidden="true" className="text-[#b96e45]">•</span>
                  <span>{tip}</span>
                </li>
              ))}
            </ul>
          </aside>
        )}
        <div className="mt-10 rounded-2xl border border-[#e9e5db] bg-white p-6 text-center shadow-sm">
          <h2 className="display-font text-2xl text-[#203b35]">Ready to plan the trip?</h2>
          <p className="mt-2 text-sm leading-6 text-[#52615b]">Browse experiences and places to stay, or ask our team to put an itinerary together.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <ButtonLink href="/tours.html">Browse tours</ButtonLink>
            <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/contact.html" secondary>Talk to us</ButtonLink>
          </div>
        </div>
      </article>
      {related.length > 0 && (
        <section className="mx-auto max-w-7xl px-5 pb-20 sm:px-8">
          <SectionHeading eyebrow="Keep reading" title="More travel guides." />
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((item) => <BlogCard key={item.slug} post={item} />)}
          </div>
        </section>
      )}
    </PageShell>
  );
}

const FAQ_GROUPS = [
  {
    title: 'Bookings and payments',
    description: 'How reserving, paying and confirming works.',
    items: [
      ['How do I book a tour or a place to stay?', 'Open a tour and pick one of its published departure dates, or open an accommodation and choose your check-in and check-out dates. Send the request and you will get the next step by M-Pesa prompt or WhatsApp, depending on where you are booking from.'],
      ['How do I pay?', 'Kenyan guests pay in shillings through a secure M-Pesa prompt sent to their phone. International travellers are contacted on WhatsApp to confirm availability and arrange payment. Nothing is charged until you approve it.'],
      ['When is my booking confirmed?', 'A booking is confirmed only once payment has been verified or, for international requests, once our team has confirmed availability in writing. A request on its own does not hold a date or a room.'],
      ['What does the price include?', 'Each listing states what is included: guide fees, park entries, meals, transfers and so on. Anything not listed, such as drinks, tips or park fees where noted, is paid separately.'],
      ['Can I cancel or change a booking?', 'A paid booking can be cancelled from your account up to 48 hours before the start time for a full refund. Inside 48 hours, message us and we will speak to the operator or host on your behalf.'],
      ['Are prices in shillings or dollars?', 'Prices are published in Kenyan shillings and can be shown in other currencies using the currency selector. The amount charged is always settled in shillings.'],
    ],
  },
  {
    title: 'Accommodation',
    description: 'Hotels, lodges, resorts, apartments and rentals.',
    items: [
      ['What kinds of accommodation can I book?', 'Hotels, lodges, safari camps, resorts, apartments, vacation rentals and hostels. Each listing shows the property type, the number of guests it sleeps and the nightly rate it starts from.'],
      ['Can I see what a room costs for my dates?', 'Yes. Choose your dates and guest count on the booking page and the available room types with their rates for those nights are shown before you commit.'],
      ['Who do I speak to about a stay?', 'Every property is listed by its host, and the host is named on the listing. For anything the page does not answer, message our team and we will put you in touch.'],
      ['Can you accommodate families and groups?', 'Many properties have family rooms or can be booked as a whole house. Tell us the group size and ages and we will suggest the options that work.'],
      ['Do you list properties that are not shown online?', 'Sometimes. If nothing published fits your dates, ask us. Our team works with hosts across the country and can often find an alternative.'],
    ],
  },
  {
    title: 'Tours, safaris and services',
    description: 'Guided experiences, licensed operators and add-ons.',
    items: [
      ['Who runs the tours?', 'Tours are run by the licensed safari and tour operators listed on this site. Each tour page names the operator, and every operator has a profile showing everything they sell.'],
      ['Are the operators licensed?', 'Profiles are created by the operators themselves and reviewed by our team before they are published. If you need to see a licence or certificate for a specific trip, ask us and we will request it.'],
      ['How do transfers, guides and equipment hire work?', 'Travel services such as airport transfers, private guides, 4x4 hire and photography are arranged by enquiry. You send a request, agree a price with the operator, and pay them directly. Nothing is charged on the site for these.'],
      ['Are safaris private or shared?', 'Both are available. The tour page states whether a departure is private or shared, and how many guests the vehicle takes.'],
      ['Can you build a custom itinerary?', 'Yes. Tell us your dates, budget and what you want to see, and our team will put an itinerary together using operators and hosts we work with.'],
    ],
  },
  {
    title: 'Accounts and partners',
    description: 'Signing in, managing bookings and listing with us.',
    items: [
      ['Do I need an account to book?', 'You can browse and send enquiries without one. Creating an account keeps your bookings, guest details and reviews together so you can return to them later.'],
      ['How do I sign in or register?', 'Use Sign in / Register in the top navigation. Guests and partners use separate sign-in pages, so make sure you choose the guest account unless you are listing with us.'],
      ['I am a host or operator. How do I list?', 'Create a partner account, add your company details, and publish tours, safaris, services or accommodation from the partner dashboard. There is no listing fee to start.'],
      ['Can I list both tours and accommodation?', 'Yes. One partner account can publish tours, travel services and accommodation, and you can manage rooms, departure dates and availability from the same dashboard.'],
    ],
  },
  {
    title: 'Travelling in Kenya',
    description: 'Practical questions before you fly.',
    items: [
      ['Do I need a visa?', 'Most visitors need to apply for an electronic travel authorisation before flying. Apply only through the official government portal, and do it well before your departure date.'],
      ['When is the best time to visit?', 'Late December to March and July to October are dry in most of the country. The coast is calmest in the kaskazi months and breezier from June, and the migration in the Maasai Mara generally falls between July and October.'],
      ['What should I pack?', 'Light layers, neutral colours for safari, a warm mid-layer for early game drives, sun protection and soft bags if you are flying between parks. Our packing guide covers the details.'],
      ['Is travel insurance needed?', 'Strongly recommended. Cover medical treatment, evacuation, cancellation and luggage, and check that your policy includes safari and coastal activities.'],
      ['How do I get around the country?', 'Domestic flights connect Nairobi, the Mara, Amboseli and the coast; road transfers work well for shorter hops. Tell us your route and we will suggest the quickest option.'],
    ],
  },
];

function FaqPage() {
  return (
    <PageShell>
      <PageBanner
        eyebrow="Frequently asked questions"
        title="Answers to the questions we get asked most."
        description="Bookings, payments, accommodation, safaris and travelling in Kenya. If your question is not here, our team is one message away."
      />
      <section className="mx-auto max-w-4xl px-5 py-14 sm:px-8 sm:py-20">
        <nav className="mb-10 flex flex-wrap gap-2" aria-label="Jump to a section">
          {FAQ_GROUPS.map((group) => (
            <a className="rounded-full border border-[#d9d7cd] px-4 py-2 text-sm font-semibold text-[#52615b] hover:bg-[#203b35] hover:text-white" href={`#${group.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`} key={group.title}>
              {group.title}
            </a>
          ))}
        </nav>
        <div className="space-y-14">
          {FAQ_GROUPS.map((group) => (
            <div id={group.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')} className="scroll-mt-32" key={group.title}>
              <h2 className="display-font text-3xl text-[#203b35]">{group.title}</h2>
              <p className="mt-1 text-sm leading-6 text-[#52615b]">{group.description}</p>
              <div className="mt-5 divide-y divide-[#e9e5db] overflow-hidden rounded-2xl border border-[#e9e5db] bg-white">
                {group.items.map(([question, answer]) => (
                  <details className="group p-5" key={question}>
                    <summary className="flex cursor-pointer items-center justify-between gap-4 font-semibold text-[#203b35]">
                      <span>{question}</span>
                      <span aria-hidden="true" className="text-lg text-[#a75f3a] transition group-open:rotate-45">+</span>
                    </summary>
                    <p className="mt-3 text-sm leading-7 text-[#52615b]">{answer}</p>
                  </details>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-14 rounded-3xl bg-[#203b35] p-8 text-white sm:p-10">
          <h2 className="display-font text-3xl">Still not sure about something?</h2>
          <p className="mt-3 max-w-2xl text-white/75">Send us a note or call the team. We answer questions about itineraries, dates and payments every day.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <ButtonLink href="/contact.html">Contact our team</ButtonLink>
            <ButtonLink className="border-white/60" href={CONTACT_PHONE_HREF} secondary>Call {CONTACT_PHONE_DISPLAY}</ButtonLink>
          </div>
        </div>
        <p className="mt-8 text-sm leading-6 text-[#52615b]">
          Looking for the formal details? Read <a className="font-semibold text-[#9a5534] hover:underline" href="/how-it-works.html">how it works</a>, the <a className="font-semibold text-[#9a5534] hover:underline" href="/booking-guide.html">booking guide</a>, the <a className="font-semibold text-[#9a5534] hover:underline" href="/cancellation-policy.html">cancellation policy</a>, our <a className="font-semibold text-[#9a5534] hover:underline" href="/privacy-policy.html">privacy policy</a> and the <a className="font-semibold text-[#9a5534] hover:underline" href="/terms.html">terms &amp; conditions</a>.
        </p>
      </section>
    </PageShell>
  );
}

function SupportPage({ page }) {
  const otherPages = SUPPORT_PAGES.filter((item) => item.slug !== page.slug);

  return (
    <PageShell>
      <PageBanner eyebrow={page.eyebrow} title={page.title} description={page.summary} />
      <section className="mx-auto max-w-3xl px-5 py-14 sm:px-8 sm:py-20">
        <p className="text-sm text-[#52615b]">Last updated {formatPostDate(page.updated)}</p>
        {page.sections.map((section) => (
          <section className="mt-9" key={section.heading}>
            <h2 className="display-font text-2xl text-[#203b35] sm:text-3xl">{section.heading}</h2>
            {(section.paragraphs || []).map((paragraph) => (
              <p className="mt-3 leading-7 text-[#52615b]" key={paragraph.slice(0, 40)}>{paragraph}</p>
            ))}
            {section.list?.length > 0 && (
              <ul className="mt-4 space-y-2 text-sm leading-6 text-[#52615b]">
                {section.list.map((item) => (
                  <li className="flex gap-2" key={item}>
                    <span aria-hidden="true" className="text-[#b96e45]">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            )}
            {section.note && <p className="mt-4 rounded-xl bg-[#e9eee8] p-4 text-sm leading-6 text-[#203b35]">{section.note}</p>}
          </section>
        ))}
        <div className="mt-12 rounded-2xl border border-[#e9e5db] bg-white p-6 shadow-sm">
          <h2 className="display-font text-2xl text-[#203b35]">Need a hand?</h2>
          <p className="mt-2 text-sm leading-6 text-[#52615b]">If anything here is unclear, our team answers questions about bookings, dates and payments every day.</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <ButtonLink href="/contact.html">Contact our team</ButtonLink>
            <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/faq.html" secondary>Read the FAQ</ButtonLink>
          </div>
        </div>
        <nav className="mt-10 border-t border-[#e9e5db] pt-6" aria-label="More support pages">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">More support pages</p>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
            {otherPages.map((item) => (
              <a className="font-semibold text-[#9a5534] hover:underline" href={item.path} key={item.slug}>{item.title}</a>
            ))}
          </div>
        </nav>
      </section>
    </PageShell>
  );
}

function categoryCountLabel(category, count) {
  if (category.kind === 'stays') return count === 1 ? '1 stay' : `${count} stays`;
  return count === 1 ? '1 experience' : `${count} experiences`;
}

function CategoryTile({ category, catalogue }) {
  const count = categoryItems(category, catalogue).length;

  return (
    <a className="group relative flex min-h-56 overflow-hidden rounded-2xl text-white shadow-sm transition hover:-translate-y-1 hover:shadow-xl" href={category.href}>
      <img className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105" src={imageUrl(category.image)} alt={category.imageAlt} loading="lazy" />
      <span className="absolute inset-0 bg-gradient-to-t from-[#0d211d]/90 via-[#0d211d]/40 to-transparent" aria-hidden="true" />
      <span className="relative z-10 mt-auto block p-4">
        <span className="block text-[0.65rem] font-bold uppercase tracking-[0.18em] text-[#a9e2e5]">{category.tagline}</span>
        <span className="display-font mt-1 block text-xl leading-tight">{category.label}</span>
        <span className="mt-1 block text-xs text-white/75">{categoryCountLabel(category, count)}</span>
      </span>
    </a>
  );
}

function CategoryCard({ category, catalogue }) {
  const items = categoryItems(category, catalogue);
  const samples = items.slice(0, 3).map((item) => item.name).filter(Boolean);

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-xl">
      <a className="relative block" href={category.href} aria-label={`${category.cta} (${category.label})`}>
        <img className="h-52 w-full object-cover" src={imageUrl(category.image)} alt={category.imageAlt} loading="lazy" />
        <span className="absolute left-4 top-4 rounded-full bg-white/90 px-3 py-1 text-[0.65rem] font-bold uppercase tracking-[0.16em] text-[#203b35]">{category.tagline}</span>
      </a>
      <div className="flex flex-1 flex-col p-5">
        <h3 className="display-font text-2xl text-[#203b35]">{category.label}</h3>
        <p className="mt-2 text-sm leading-6 text-[#52615b]">{category.description}</p>
        {samples.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {samples.map((name) => (
              <span className="rounded-full bg-[#f3eee6] px-3 py-1 text-xs font-semibold text-[#735744]" key={name}>{name}</span>
            ))}
          </div>
        )}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-5">
          <span className="text-xs font-bold uppercase tracking-wider text-[#735744]">{categoryCountLabel(category, items.length)}</span>
          <a className="action-link" href={category.href}>{category.cta} →</a>
        </div>
      </div>
    </article>
  );
}

const EXPLORE_GROUPS = [
  {
    kind: 'stays',
    eyebrow: 'Ways to stay',
    title: 'A lodge in the Mara, or a simple room near the old town.',
    description: 'Accommodations split by how much space and service you want, not by star ratings. Both ends of the range are places we have walked through ourselves.',
  },
  {
    kind: 'experiences',
    eyebrow: 'Ways to explore',
    title: 'One day out, one night in the park, or a week of both.',
    description: 'Tours grouped by the shape of the day: single-day outings, overnight safaris with park fees included, and the activities that get the heart going.',
  },
];

function ExplorePage({ catalogue, loading, error, retry }) {
  return (
    <PageShell>
      <PageBanner
        eyebrow="Explore by category"
        title="Start with the kind of trip you have in mind."
        description="Luxury lodges or good-value rooms, a single day out or a safari with nights in the park. Pick a category and see exactly what is bookable right now."
      />
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        {loading || error ? <LoadingState error={error} onRetry={retry} /> : EXPLORE_GROUPS.map((group) => (
          <div className={group.kind === 'stays' ? '' : 'mt-16'} key={group.kind}>
            <SectionHeading eyebrow={group.eyebrow} title={group.title} description={group.description} />
            <div className="grid gap-5 md:grid-cols-2">
              {categoriesFor(group.kind).map((category) => (
                <CategoryCard category={category} catalogue={catalogue} key={category.slug} />
              ))}
            </div>
          </div>
        ))}
        <div className="mt-16 rounded-3xl bg-[#203b35] p-8 text-white sm:p-10">
          <h2 className="display-font text-3xl">Nothing quite fits?</h2>
          <p className="mt-3 max-w-2xl text-white/75">Tell us the dates and the kind of trip you are imagining. Our team matches travellers to lodges, guides and itineraries every day, including combinations that are not on the site yet.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <ButtonLink href="/booking.html">Plan your trip</ButtonLink>
            <ButtonLink className="border-white/60" href="/contact.html" secondary>Contact our team</ButtonLink>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

const SEARCH_TYPE_OPTIONS = [
  ['all', 'Everything'],
  ['tour', 'Tours & safaris'],
  ['accommodation', 'Accommodations'],
  ['service', 'Services'],
  ['destination', 'Places'],
];

const SEARCH_SORT_OPTIONS = [
  ['relevance', 'Relevance'],
  ['price_low', 'Price: low to high'],
  ['price_high', 'Price: high to low'],
  ['rating', 'Guest rating'],
  ['popular', 'Most booked'],
];

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function HighlightedText({ text, terms }) {
  const activeTerms = (terms || []).filter((term) => term && term.length > 1);
  if (!text || activeTerms.length === 0) return text;
  const pattern = new RegExp(`(${activeTerms.map(escapeRegExp).join('|')})`, 'gi');
  const matchedTerms = new Set(activeTerms.map((term) => term.toLowerCase()));
  return text.split(pattern).map((part, index) => (
    matchedTerms.has(part.toLowerCase())
      ? <mark className="rounded bg-[#f6dfc4] px-0.5 text-[#203b35]" key={`${part}-${index}`}>{part}</mark>
      : part
  ));
}

function SearchResultCard({ result, currency, terms }) {
  const unit = result.price_unit || 'per guest';
  const price = Number.isFinite(result.price)
    ? result.price_unit === 'per night'
      ? result.price_to > result.price
        ? `From ${formatPrice(result.price, currency)} to ${formatPrice(result.price_to, currency)} per night`
        : `${formatPrice(result.price, currency)} per night`
      : `From ${formatPrice(result.price, currency)} ${unit}`
    : 'Ask our team';
  const actionLabel = result.type === 'destination'
    ? 'See tours there'
    : result.type === 'accommodation'
      ? 'Enquire about this accommodation'
      : result.type === 'service'
        ? 'Enquire about this service'
        : 'View tour details';

  return (
    <article className="tour-card overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm transition hover:-translate-y-1 hover:shadow-xl">
      <a className="relative block" href={result.url} aria-label={`${actionLabel}: ${result.title}`} onClick={() => trackPromotionClick(result.type === 'accommodation' ? 'property' : 'tour', result.slug, result.promotion)}>
        <img className="h-48 w-full object-cover" src={imageUrl(result.image_url)} alt={result.title} loading="lazy" />
        <SponsoredTag className="absolute left-3 top-3 shadow-sm" promotion={result.promotion} />
      </a>
      <div className="p-5">
        <p className="mb-2 text-xs font-bold uppercase tracking-wider text-[#a75f3a]">{result.type_label}</p>
        <h3 className="display-font text-2xl text-[#203b35]"><HighlightedText text={result.title} terms={terms} /></h3>
        {result.subtitle && <p className="mt-1 text-sm font-semibold text-[#735744]"><HighlightedText text={result.subtitle} terms={terms} /></p>}
        <BadgeList badges={result.badges} />
        {result.review_count > 0 && <p className="mt-2 flex items-center gap-2 text-sm text-[#52615b]">
          <StarRow rating={result.rating} />
          <span>{Number(result.rating).toFixed(1)}</span>
          <span>· {result.review_count} review{result.review_count === 1 ? '' : 's'}</span>
        </p>}
        {result.snippet && <p className="mt-3 line-clamp-3 text-sm leading-6 text-[#52615b]"><HighlightedText text={result.snippet} terms={terms} /></p>}
        <div className="mt-5 flex items-center justify-between gap-3 border-t border-[#efede7] pt-4">
          <div>
            <p className="text-sm text-[#52615b]">{price}</p>
            <p className="mt-1 text-xs font-semibold text-[#177b5b]">{priceComparisonText(result.price_comparison)}</p>
          </div>
          <a className="rounded-full bg-[#203b35] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#31554b]" href={result.url}>{actionLabel}</a>
        </div>
      </div>
    </article>
  );
}

function SearchSuggestions({ suggestions, onSelect }) {
  if (suggestions.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {suggestions.map((suggestion) => (
        <button
          className="rounded-full border border-[#d9d7cd] px-4 py-2 text-sm font-semibold text-[#52615b] hover:border-[#203b35] hover:text-[#203b35]"
          key={suggestion}
          onClick={() => onSelect(suggestion)}
          type="button"
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
}

function SearchPage({ catalogue, currency }) {
  const initialParams = new URLSearchParams(window.location.search);
  const requestedType = initialParams.get('type') || 'all';
  const initialType = SEARCH_TYPE_OPTIONS.some(([value]) => value === requestedType) ? requestedType : 'all';
  const initialQuery = (initialParams.get('q') || '').slice(0, 120);
  const requestedSort = initialParams.get('sort') || 'relevance';
  const initialSort = SEARCH_SORT_OPTIONS.some(([value]) => value === requestedSort) ? requestedSort : 'relevance';
  const [query, setQuery] = useState(initialQuery);
  const [type, setType] = useState(initialType);
  const [sort, setSort] = useState(initialSort);
  const [results, setResults] = useState([]);
  const [counts, setCounts] = useState({});
  const [terms, setTerms] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const trimmedQuery = query.trim();
  const canSearch = trimmedQuery.length >= 2;

  const suggestions = useMemo(() => {
    const destinationNames = catalogue.destinations.slice(0, 5).map((item) => item.name);
    const categories = [...new Set(catalogue.tours.map((tour) => tour.category).filter(Boolean))].slice(0, 5);
    return [...new Set([...destinationNames, ...categories])].slice(0, 8);
  }, [catalogue]);

  useEffect(() => {
    if (!canSearch) {
      setResults([]);
      setCounts({});
      setTerms([]);
      setTotal(0);
      setError('');
      setLoading(false);
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError('');
      const search = new URLSearchParams({ q: trimmedQuery });
      if (type !== 'all') search.set('type', type);
      if (sort !== 'relevance') search.set('sort', sort);
      fetch(`/api/search?${search}`, { signal: controller.signal, headers: { Accept: 'application/json' } })
        .then(async (response) => {
          const data = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(data.error || `Search could not be completed (HTTP ${response.status}).`);
          return data;
        })
        .then((data) => {
          setResults(Array.isArray(data.results) ? data.results : []);
          setCounts(data.counts || {});
          setTerms(Array.isArray(data.terms) ? data.terms : []);
          setTotal(Number(data.total) || 0);
        })
        .catch((searchError) => {
          if (searchError.name !== 'AbortError') setError(getErrorMessage(searchError));
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 300);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [canSearch, trimmedQuery, type, sort]);

  function updateAddressBar(nextQuery, nextType, nextSort = sort) {
    const search = new URLSearchParams();
    if (nextQuery) search.set('q', nextQuery);
    if (nextType !== 'all') search.set('type', nextType);
    if (nextSort !== 'relevance') search.set('sort', nextSort);
    const address = search.toString();
    window.history.replaceState(null, '', `/search.html${address ? `?${address}` : ''}`);
  }

  function submitSearch(event) {
    event.preventDefault();
    updateAddressBar(query.trim(), type);
  }

  function changeType(nextType) {
    setType(nextType);
    updateAddressBar(trimmedQuery, nextType);
  }

  function changeSort(nextSort) {
    setSort(nextSort);
    updateAddressBar(trimmedQuery, type, nextSort);
  }

  function runSuggestion(suggestion) {
    setQuery(suggestion);
    updateAddressBar(suggestion, type);
  }

  return (
    <PageShell>
      <section className="bg-[#203b35] px-5 py-14 text-white sm:px-8 sm:py-20">
        <div className="mx-auto max-w-4xl">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#f1b28b]">Search the marketplace</p>
          <h1 className="display-font mt-4 text-4xl leading-tight sm:text-5xl">Find tours, accommodations and places across Kenya.</h1>
          <form className="mt-7" role="search" onSubmit={submitSearch}>
            <div className="flex flex-col gap-3 sm:flex-row">
              <label className="sr-only" htmlFor="search-page-input">Search tours, accommodations and places</label>
              <input
                autoFocus
                className="field flex-1"
                id="search-page-input"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search tours, accommodations and places"
                type="search"
                value={query}
              />
              <button className="min-h-12 shrink-0 rounded-full bg-[#b96e45] px-7 text-sm font-semibold text-white hover:bg-[#a45d38]" type="submit">Search</button>
            </div>
          </form>
          <div className="mt-4 flex flex-wrap gap-2" aria-label="Filter search results by listing type">
            {SEARCH_TYPE_OPTIONS.map(([value, label]) => (
              <button
                className={`rounded-full px-4 py-2 text-sm font-semibold ${type === value ? 'bg-white text-[#203b35]' : 'border border-white/40 text-white/80 hover:bg-white/10'}`}
                key={value}
                onClick={() => changeType(value)}
                type="button"
                aria-pressed={type === value}
              >
                {label}
                {counts[value] ? <span className="ml-2 text-xs opacity-80">{counts[value]}</span> : null}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        {error && <p className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</p>}
        {!canSearch && (
          <div>
            <h2 className="display-font text-3xl text-[#203b35]">Start with a place, a tour, or a feeling</h2>
            <p className="mt-3 max-w-2xl leading-7 text-[#52615b]">
              Search titles, descriptions, amenities and destinations across every tour, accommodation and place on the marketplace. Type at least two letters.
            </p>
            <div className="mt-6">
              <SearchSuggestions onSelect={runSuggestion} suggestions={suggestions} />
            </div>
          </div>
        )}
        {canSearch && (
          <>
            <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="display-font text-3xl text-[#203b35]">Search results</h2>
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-sm text-[#52615b]">
                  <span>Sort results</span>
                  <select
                    className="field min-h-10 w-auto py-2"
                    onChange={(event) => changeSort(event.target.value)}
                    value={sort}
                  >
                    {SEARCH_SORT_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                <p aria-live="polite" className="text-sm text-[#52615b]" role="status">
                  {loading ? 'Searching…' : `${total} ${total === 1 ? 'result' : 'results'} for “${trimmedQuery}”`}
                </p>
              </div>
            </div>
            {loading && results.length === 0 && <p className="py-8 text-center text-[#52615b]" role="status">Searching every listing…</p>}
            {!loading && !error && results.length === 0 && (
              <div className="rounded-2xl bg-[#f5f3ed] p-6">
                <p className="text-[#52615b]">No listings match “{trimmedQuery}”. Try a destination such as Lamu, or a shorter keyword.</p>
                <div className="mt-4">
                  <SearchSuggestions onSelect={runSuggestion} suggestions={suggestions.slice(0, 5)} />
                </div>
              </div>
            )}
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {results.map((result) => (
                <SearchResultCard currency={currency} key={`${result.type}-${result.slug}`} result={result} terms={terms} />
              ))}
            </div>
            {!loading && results.length > 0 && (
              <RecommendationStrip
                currency={currency}
                description="Popular listings outside these results, ranked from guest bookings, ratings and price value."
                embedded
                exclude={results.map((result) => result.slug).join(',')}
                title="More to explore"
              />
            )}
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
  const initialCheckIn = params.get('check_in') || params.get('date') || todayInKenya();
  const initialCheckOut = params.get('check_out') || addDaysToIsoDate(initialCheckIn, 1);
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
  const [stayRooms, setStayRooms] = useState([]);
  const [stayRoomsLoading, setStayRoomsLoading] = useState(false);
  const [stayRoomsError, setStayRoomsError] = useState('');
  const [roomId, setRoomId] = useState('');
  const [stayQuoteUrl, setStayQuoteUrl] = useState('');
  const [language, setLanguage] = useState(documentLanguage());
  const [travelerType, setTravelerType] = useState(currency.code === 'KES' ? 'domestic' : 'international');
  const [travelerChoiceTouched, setTravelerChoiceTouched] = useState(false);
  const allOptions = [
    ...catalogue.tours.map((tour) => ({ ...tour, kind: 'tour', price: tour.price })),
    ...catalogue.properties.map((property) => ({ ...property, kind: 'stay', price: property.price_per_night })),
  ];
  const selectedListing = allOptions.find((item) => item.slug === selected);
  const stayNights = Math.max(0, Math.round((Date.parse(`${checkOutDate}T00:00:00Z`) - Date.parse(`${checkInDate}T00:00:00Z`)) / 86400000));
  const selectedRoom = stayRooms.find((room) => String(room.id) === String(roomId)) || null;
  const total = selectedListing
    ? selectedListing.kind === 'stay'
      ? (selectedRoom ? selectedRoom.total : selectedListing.price * stayNights)
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
    document.addEventListener('kenya-language-changed', syncLanguage);
    return () => document.removeEventListener('kenya-language-changed', syncLanguage);
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

  useEffect(() => {
    if (!selectedListing || selectedListing.kind !== 'stay' || stayNights < 1) {
      setStayRooms([]);
      setRoomId('');
      setStayRoomsError('');
      return undefined;
    }
    const controller = new AbortController();
    setStayRoomsLoading(true);
    setStayRoomsError('');
    const query = new URLSearchParams({
      check_in: checkInDate,
      check_out: checkOutDate,
      guests: String(Number(guests) || 1),
    });
    fetch(`/api/properties/${encodeURIComponent(selectedListing.slug)}/availability?${query}`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Room availability could not be loaded.');
        return result.rooms;
      })
      .then((rooms) => {
        setStayRooms(rooms);
        setRoomId((current) => {
          const kept = rooms.find((room) => String(room.id) === String(current));
          if (kept && kept.is_available) return String(current);
          const firstOpen = rooms.find((room) => room.is_available);
          return firstOpen ? String(firstOpen.id) : '';
        });
      })
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') setStayRoomsError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setStayRoomsLoading(false);
      });
    return () => controller.abort();
  }, [selected, selectedListing?.kind, checkInDate, checkOutDate, guests]);

  async function submitBooking(event) {
    event.preventDefault();
    setSubmitError('');
    const data = Object.fromEntries(new FormData(event.currentTarget));
    if (selectedListing?.kind === 'stay') {
      if (stayNights < 1) {
        setSubmitError('Choose a check-out date after check-in.');
        return;
      }
      setStayQuoteUrl('');
      if (travelerType === 'domestic') {
        if (!selectedRoom) {
          setSubmitError('Choose an available room for these dates.');
          return;
        }
        if (!selectedRoom.is_available) {
          setSubmitError('Those dates are no longer available. Pick another room or different dates.');
          return;
        }
        data.booking_type = 'property';
        data.room_id = String(selectedRoom.id);
        data.check_in = checkInDate;
        data.check_out = checkOutDate;
      } else {
        const dateLabel = (date) => new Date(`${date}T12:00:00`).toLocaleDateString(language === 'sw' ? 'sw-KE' : 'en-KE');
        const details = String(data.message || '').trim();
        const contactLines = [
          `Traveler: ${data.name} (International traveler from ${data.country_of_residence})`,
          `Email: ${data.email}`,
          `Phone: ${data.international_phone}`,
        ];
        const message = language === 'sw'
          ? [
            'Habari Kenya Tours, tafadhali thibitisheni malazi haya:',
            ...contactLines,
            `Malazi: ${selectedListing.name} (${selectedListing.location})`,
            `Kuingia: ${dateLabel(checkInDate)}`,
            `Kutoka: ${dateLabel(checkOutDate)} (${stayNights} usiku)`,
            `Wageni: ${guests}`,
            `Jumla ya makadirio: ${formatKenyanShillings(total)}`,
            ...(details ? [`Maelezo: ${details}`] : []),
            'Tafadhali thibitisheni nafasi na mtumie hatua za malipo ya kimataifa. Nafasi haitahifadhiwa hadi mthibitisho.',
          ].join('\n')
          : [
            'Hello Kenya Tours, please confirm this accommodation before I pay:',
            ...contactLines,
            `Accommodation: ${selectedListing.name} (${selectedListing.location})`,
            `Check-in: ${dateLabel(checkInDate)}`,
            `Check-out: ${dateLabel(checkOutDate)} (${stayNights} ${stayNights === 1 ? 'night' : 'nights'})`,
            `Guests: ${guests}`,
            `Estimated accommodation total: ${formatKenyanShillings(total)}`,
            ...(details ? [`Notes: ${details}`] : []),
            'Please confirm availability and share international payment options. I understand this request does not hold the accommodation until confirmed.',
          ].join('\n');
        setStayQuoteUrl(whatsappUrl(message, catalogue.whatsapp_business_phone));
        return;
      }
    }
    if (travelerType === 'international') {
      const dateLabel = selectedSchedule
        ? `${selectedSchedule.starts_at.slice(0, 10)} at ${selectedSchedule.starts_at.slice(11, 16)} Kenya time`
        : `${data.date} at ${data.time} Kenya time`;
      const details = String(data.message || '').trim();
      const message = [
        'Hello Kenya Tours, I am an international traveler and would like to arrange this booking:',
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
        eyebrow={selectedListing?.kind === 'stay' ? (language === 'sw' ? 'Uhifadhi wa malazi' : 'Accommodation booking') : 'A few details, then Kenya is closer'}
        title={selectedListing?.kind === 'stay' ? (language === 'sw' ? 'Panga malazi yako Kenya.' : 'Plan your accommodation in Kenya.') : 'Let’s bring your Kenyan plans to life.'}
        description={selectedListing?.kind === 'stay' ? (language === 'sw' ? 'Chagua tarehe zako na chumba, kisha lipa kwa M-Pesa. Wasafiri wa kimataifa wanaweza kuuliza kupitia WhatsApp.' : 'Choose your dates and room, then pay securely with M-Pesa. International travelers can still enquire on WhatsApp.') : travelerType === 'domestic' ? 'Choose an experience and available departure, then confirm your booking securely with M-Pesa.' : 'Choose an experience and departure, then contact our local team to confirm availability and arrange payment.'}
      />
      <div className="mx-auto max-w-7xl px-5 pt-10 sm:px-8 sm:pt-14">
        <SmartTripPlanner tours={catalogue.tours} properties={catalogue.properties} destinations={catalogue.destinations} whatsappPhone={catalogue.whatsapp_business_phone} guests={Number(guests) || 1} />
      </div>
      <section className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div id="booking-checkout" className="rounded-3xl border border-[#e9e5db] bg-white p-6 shadow-sm sm:p-9">
          <h2 className="display-font text-3xl text-[#203b35]">{selectedListing?.kind === 'stay' ? 'Book your stay' : 'Make it a date with Kenya.'}</h2>
          <p className="mt-2 text-sm leading-6 text-[#52615b]">{selectedListing?.kind === 'stay' ? 'Pick your dates and room type. We hold those nights while M-Pesa confirms your payment and release them if it does not go through. International travelers can send an enquiry on WhatsApp instead.' : travelerType === 'domestic' ? 'Choose a published departure, tell us who’s coming, and approve the M-Pesa prompt sent to your Kenyan mobile number. Your booking is confirmed after payment is verified.' : 'Share your details with our local team on WhatsApp. We’ll confirm the departure and provide an international payment option.'}</p>
          {selectedListing && selectedListing.review_count > 0 && <p className="mt-3 flex flex-wrap items-center gap-2 text-sm font-semibold text-[#203b35]">
            <StarRow rating={selectedListing.rating} />
            <span>{Number(selectedListing.rating).toFixed(1)} / 5</span>
            <span className="font-normal text-[#52615b]">· {selectedListing.review_count} review{selectedListing.review_count === 1 ? '' : 's'}</span>
          </p>}
          {errorMessage && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{errorMessage}</p>}
          {submitError && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{submitError}</p>}
          {stayQuoteUrl && <div className="mt-5 rounded-xl bg-[#e9eee8] p-4" role="status"><p className="text-sm text-[#203b35]">Your accommodation request is ready. The host will confirm dates before payment.</p><a className="mt-3 inline-flex min-h-11 items-center justify-center rounded-full bg-[#177b5b] px-5 text-sm font-semibold text-white hover:bg-[#126448]" href={stayQuoteUrl} target="_blank" rel="noreferrer">{catalogue.whatsapp_business_phone ? 'Message Kenya Tours on WhatsApp' : 'Share enquiry in WhatsApp'}</a></div>}
          {loading || error ? <div className="mt-6"><LoadingState error={error} onRetry={retry} /></div> : (
            <form className="mt-7 grid gap-x-5 gap-y-5 sm:grid-cols-2" onSubmit={submitBooking}>
              <label className="sm:col-span-2">
                <span className="field-label">Tour or accommodation</span>
                <select className="field" name="tour" value={selected} onChange={(event) => { setSelected(event.target.value); setStayQuoteUrl(''); }} required>
                  <option value="">Choose an experience or accommodation</option>
                  {catalogue.tours.length > 0 && <optgroup label="Tours">{catalogue.tours.map((tour) => <option key={tour.slug} value={tour.slug}>{tour.name} — {formatKenyanShillings(tour.price)} / person</option>)}</optgroup>}
                  {catalogue.properties.length > 0 && <optgroup label="Accommodations">{catalogue.properties.map((property) => <option key={property.slug} value={property.slug}>{property.name} — {formatKenyanShillings(property.price_per_night)} / night</option>)}</optgroup>}
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
                      {departureDates.map((date) => <option value={date} key={date}>{new Date(`${date}T12:00:00`).toLocaleDateString(numberLocale(), { weekday: 'short', year: 'numeric', month: 'long', day: 'numeric' })}</option>)}
                    </select>
                  </label>
                  <label>
                    <span className="field-label">Departure time (Kenya time)</span>
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
                  <label><span className="field-label">Check-in</span><input className="field" name="check_in" type="date" min={todayInKenya()} value={checkInDate} onChange={(event) => { setCheckInDate(event.target.value); setStayQuoteUrl(''); }} required /></label>
                  <label><span className="field-label">Check-out</span><input className="field" name="check_out" type="date" min={checkInDate} value={checkOutDate} onChange={(event) => { setCheckOutDate(event.target.value); setStayQuoteUrl(''); }} required /></label>
                  <div className="sm:col-span-2">
                    <span className="field-label">Room type</span>
                    {stayRoomsLoading && <p className="mt-1 text-sm text-[#52615b]" role="status">Checking room availability…</p>}
                    {stayRoomsError && <p className="mt-1 rounded-xl bg-red-50 p-3 text-sm text-red-800" role="alert">{stayRoomsError}</p>}
                    {!stayRoomsLoading && !stayRoomsError && stayRooms.length === 0 && stayNights >= 1 && <p className="mt-1 rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No rooms are published for this accommodation yet. Contact our team and we’ll help arrange your stay.</p>}
                    {stayNights < 1 && <p className="mt-1 rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">Choose a check-out date after your check-in date to see rooms.</p>}
                    <div className="mt-2 space-y-3">
                      {stayRooms.map((room) => (
                        <label
                          className={`flex cursor-pointer flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 ${String(room.id) === String(roomId) ? 'border-[#17617a] bg-[#e6f0f1]' : 'border-[#d1e0e2]'} ${room.is_available ? '' : 'opacity-60'}`}
                          key={room.id}
                        >
                          <span className="flex items-center gap-3">
                            <input className="accent-[#17617a]" type="radio" name="room_id" value={room.id} checked={String(room.id) === String(roomId)} onChange={() => setRoomId(String(room.id))} disabled={!room.is_available} />
                            <span>
                              <span className="block text-sm font-semibold text-[#203b35]">{room.name}</span>
                              <span className="block text-xs text-[#52615b]">Sleeps {room.guests} · {formatKenyanShillings(room.rate)} per night</span>
                            </span>
                          </span>
                          <span className="text-sm font-semibold text-[#9a5534]">{room.is_available ? `${formatKenyanShillings(room.total)} total · ${room.remaining} left` : 'Sold out'}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <label><span className="field-label">Preferred date</span><input className="field" name="date" type="date" min={todayInKenya()} required /></label>
                  <label><span className="field-label">Preferred time</span><input className="field" name="time" type="time" required /></label>
                </>
              )}
              <label>
                <span className="field-label">Number of guests</span>
                <input
                  className="field"
                  name="guests"
                  type="number"
                  min={selectedListing?.kind === 'tour' ? (selectedListing.min_group_size ?? 1) : 1}
                  max={selectedListing?.kind === 'stay'
                    ? (selectedRoom?.guests ?? selectedListing?.guests ?? 12)
                    : Math.min(selectedListing?.max_group_size ?? 12, selectedSchedule?.remaining || selectedListing?.max_group_size || 12)}
                  value={guests}
                  onChange={(event) => {
                    const value = event.target.value;
                    const roomLimit = selectedListing?.kind === 'stay' ? selectedRoom?.guests : null;
                    setGuests(roomLimit && Number(value) > roomLimit ? String(roomLimit) : value);
                    setStayQuoteUrl('');
                  }}
                  required
                />
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
                  ? selectedRoom
                    ? language === 'sw'
                      ? `${stayNights} usiku kwa ${formatKenyanShillings(selectedRoom.rate)} kwa usiku katika ${selectedRoom.name}. Jumla imehesabiwa na mwenyeji.`
                      : `${stayNights} ${stayNights === 1 ? 'night' : 'nights'} at ${formatKenyanShillings(selectedRoom.rate)} per night in ${selectedRoom.name}. The total is calculated by the host and confirmed before payment.`
                    : language === 'sw'
                      ? 'Chagua chumba kinachopatikana ili kuona jumla ya malazi.'
                      : 'Choose an available room to see the accommodation total.'
                  : `Charged in Kenyan shillings (KES). Tour prices are per person.${currency.code !== 'KES' ? ` Approximate total in ${currency.code}: ${formatPrice(total, currency)}.` : ''}`}</p>
              </div>
              <button className="min-h-12 rounded-full bg-[#b96e45] px-6 font-semibold text-white hover:bg-[#a45d38] disabled:opacity-50 sm:col-span-2" type="submit" disabled={submitting || (selectedListing?.kind === 'tour' && (!selectedSchedule || Number(guests) > selectedSchedule.remaining || availabilityLoading)) || (selectedListing?.kind === 'stay' && (stayNights < 1 || (travelerType === 'domestic' && (!selectedRoom || !selectedRoom.is_available))))}>
                {selectedListing?.kind === 'stay'
                  ? travelerType === 'domestic'
                    ? submitting ? 'Opening secure checkout…' : 'Continue to secure payment'
                    : 'Request availability on WhatsApp'
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
            <p className="mt-2 leading-6">{selectedListing?.kind === 'stay' ? (travelerType === 'domestic' ? 'Nights are held while M-Pesa verifies your payment. Your stay is confirmed as soon as the payment is verified.' : 'International stay requests are sent to our team on WhatsApp. No nights are held until the team confirms availability and payment arrangements.') : travelerType === 'domestic' ? 'Payments are requested securely through M-Pesa STK Push in Kenyan shillings. Your booking is confirmed only after Daraja verifies successful payment.' : 'International requests are sent to our team on WhatsApp. Your booking is not held until the team confirms availability and payment arrangements.'}</p>
          </div>
        </aside>
      </section>
    </PageShell>
  );
}

function AboutKenyaPage() {
  return (
    <PageShell>
      <PageBanner eyebrow="A country with a thousand stories" title="One country. Six very different regions." description="Kenya is a coastline of Swahili towns, a capital with a national park inside it, a rift of cliffs and lakes, and savannah beneath Kilimanjaro. Pick the corner that suits the trip you have in mind." />
      <section className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-2 lg:items-center">
        <img className="h-[26rem] w-full rounded-3xl object-cover" src="/images/Lamu,_Kenya_(45275410485).jpeg" alt="Historic Swahili town on the Kenyan coast" />
        <div>
          <SectionHeading eyebrow="Meet Kenya" title="Coast, city, highlands, and savannah in one country." />
          <p className="leading-7 text-[#52615b]">Kenya runs from the Indian Ocean to the Great Rift Valley and on to the foothills of Kilimanjaro. Along the way you pass centuries-old Swahili ports, coral reefs, highland farms, and grassland that holds some of the densest wildlife on earth.</p>
          <p className="mt-4 leading-7 text-[#52615b]">We work with guides, boat crews, and hosts who live in each place, so a day out is shaped by people who know the tides, the seasons, and the roads rather than by a script.</p>
          <ButtonLink className="mt-7" href="/tours.html">Browse experiences across Kenya</ButtonLink>
        </div>
      </section>
      <section className="bg-[#efeee7] px-5 py-14 sm:px-8 sm:py-20">
        <div className="mx-auto max-w-7xl">
          <SectionHeading centered eyebrow="Follow your curiosity" title="Many regions. One unforgettable country." />
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {[
              ['images/Lamu_Fort_Museum\'s.jpg', 'The Swahili coast', 'Lamu, Mombasa, Watamu, and Diani: carved doors, dhow sails, reef gardens, and old towns that are still lived in.'],
              ['images/shela-lamu-kenya-01.jpg', 'The islands and the reef', 'Take the long way along the sand, feel the sea breeze, and leave a little room in the day for doing nothing.'],
              ['images/Lamu_Donkey_Sanctuary.jpg', 'A slower coastal rhythm', 'Discover the local traditions, familiar faces, and everyday moments that make the coast feel like nowhere else.'],
              ['images/fatma.png', 'Everyday life by the sea', 'Share the simple pleasures of island life: a fresh coconut, warm sand, and the Indian Ocean in the background.'],
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
      <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <SectionHeading eyebrow="Lamu, one of many" title="Where living culture meets the Indian Ocean." />
        <div className="grid gap-8 lg:grid-cols-[1.25fr_1fr] lg:items-start">
          <div>
            <p className="leading-7 text-[#52615b]">Off Kenya’s northern coast, Lamu is one of East Africa’s oldest and best-preserved Swahili settlements. Coral-stone buildings, intricately carved doors, and winding lanes hold traces of generations shaped by Indian Ocean trade and travel.</p>
            <p className="mt-4 leading-7 text-[#52615b]">Life here moves at a gentler pace—on foot, by dhow, and along familiar neighborhood paths. Lamu Old Town was recognized as a UNESCO World Heritage Site in 2001, and its sense of place is still part of daily life.</p>
            <ButtonLink className="mt-7" href="/tours.html">See Lamu experiences</ButtonLink>
          </div>
          <div className="rounded-2xl bg-[#e9eee8] p-6">
            <p className="font-semibold text-[#203b35]">Where else you can book</p>
            <p className="mt-2 text-sm leading-6 text-[#52615b]">Lamu is just one of the destinations on this site. The rest of the country is just as bookable.</p>
            <ul className="mt-4 grid gap-2 text-sm text-[#52615b] sm:grid-cols-2 lg:grid-cols-1">
              {['Mombasa — fort, old town, and harbour sails', 'Diani Beach — reef snorkelling and sacred forest', 'Watamu — marine park and Gede ruins', 'Nairobi — a national park inside the capital', 'Lake Naivasha — boat safaris and Hell’s Gate', 'Maasai Mara — game drives and balloon flights', 'Amboseli — elephants below Kilimanjaro', 'Tsavo — red elephants and lava flows', 'Mount Kenya — forest treks and highland farms'].map((item) => (
                <li className="flex gap-2" key={item}>
                  <span aria-hidden="true" className="text-[#b96e45]">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <ButtonLink className="mt-6" href="/destinations.html">Browse destinations by region</ButtonLink>
          </div>
        </div>
      </section>
    </PageShell>
  );
}

function ContactPage() {
  const [status, setStatus] = useState({ message: '', error: false, sending: false });
  const phone = useWhatsAppPhone();

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
      <PageBanner eyebrow="A local team, one message away" title="Let’s make your Kenyan plans easier." description="Wondering which experience suits your trip, or need help with a booking? Tell us what you’re looking for and our team will be glad to help." />
      <section className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-[0.8fr_1.2fr]">
        <div>
          <SectionHeading eyebrow="Get in touch" title="Tell us what you have in mind." description="A tour, accommodation, a question about your plans—we’re listening. Send a note and our team will follow up." />
          <div className="rounded-2xl bg-[#e9eee8] p-6">
            <p className="font-semibold text-[#203b35]">Kenya Tours &amp; Marketplace</p>
            <p className="mt-3 text-sm leading-6 text-[#52615b]">
              Kenya<br />
              <a className="inline-flex items-center gap-2 font-medium text-[#9a5534] hover:underline" href={CONTACT_PHONE_HREF}>
                <PhoneIcon />
                <span>Call {CONTACT_PHONE_DISPLAY}</span>
              </a><br />
              <a className="inline-flex items-center gap-2 font-medium text-[#9a5534] hover:underline" href={whatsappUrl(WHATSAPP_GREETING, phone)} target="_blank" rel="noopener noreferrer">
                <WhatsAppIcon />
                <span>Message us on WhatsApp</span>
              </a>
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

  const destinationName = catalogue.destinations.find((item) => item.slug === tour.destination)?.name;

  return (
    <PageShell>
      <section className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
        <a className="text-sm font-semibold text-[#9a5534] hover:underline" href="/tours.html">← All tours</a>
        <div className="mt-6 grid gap-10 lg:grid-cols-[1.15fr_0.85fr]">
          <img className="max-h-[34rem] w-full rounded-3xl object-cover" src={imageUrl(tour.image_url)} alt={tour.name} />
          <div className="py-2">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">{tour.tour_type_label || tour.category || 'A Kenya experience'}</p>
            <h1 className="display-font mt-4 text-4xl leading-tight text-[#203b35] sm:text-5xl">{tour.name}</h1>
            <BadgeList badges={tour.badges} />
            {tour.review_count > 0 && <p className="mt-3 flex items-center gap-2 text-sm text-[#52615b]">
              <StarRow rating={tour.rating} />
              <span>{Number(tour.rating).toFixed(1)}</span>
              <span>· {tour.review_count} review{tour.review_count === 1 ? '' : 's'}</span>
            </p>}
            <p className="mt-5 leading-7 text-[#52615b]">{tour.description}</p>
            <ShareRow className="mt-5" title={tour.name} />
            {tour.operator && tour.operator.slug && (
              <div className="mt-6 rounded-2xl border border-[#d1e0e2] bg-[#f5f3ed] p-4">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#17617a]">Run by</p>
                <a className="mt-1 inline-flex text-lg font-semibold text-[#203b35] hover:underline" href={`/operators/${tour.operator.slug}`}>{tour.operator.name}</a>
                {tour.operator.location && <p className="text-sm text-[#52615b]">{tour.operator.location}</p>}
                <a className="mt-2 inline-flex text-sm font-semibold text-[#9a5534] hover:underline" href={`/operators/${tour.operator.slug}`}>See everything this operator offers →</a>
              </div>
            )}
            <div className="mt-7 grid grid-cols-2 gap-4 rounded-2xl bg-[#efeee7] p-5">
              <div><span className="block text-xs text-[#52615b]">Duration</span><strong className="mt-1 block text-[#203b35]">{tour.duration}</strong></div>
              <div>
                <span className="block text-xs text-[#52615b]">From</span>
                <strong className="mt-1 block text-[#203b35]">{formatPrice(tour.price, currency)} / person</strong>
                <span className="mt-1 block text-xs font-semibold text-[#177b5b]">{priceComparisonText(tour.price_comparison)}</span>
              </div>
              <div><span className="block text-xs text-[#52615b]">Pickup point</span><strong className="mt-1 block text-[#203b35]">{tour.pickup_point || 'Confirmed after booking'}</strong></div>
              <div><span className="block text-xs text-[#52615b]">Group size</span><strong className="mt-1 block text-[#203b35]">{tour.min_group_size || 1}–{tour.max_group_size || 12} guests</strong></div>
              {tour.tour_type_label && <div><span className="block text-xs text-[#52615b]">Tour style</span><strong className="mt-1 block text-[#203b35]">{tour.tour_type_label}</strong></div>}
              {tour.group_type_label && <div><span className="block text-xs text-[#52615b]">Group style</span><strong className="mt-1 block text-[#203b35]">{tour.group_type_label}</strong></div>}
              {destinationName && <div><span className="block text-xs text-[#52615b]">Destination</span><strong className="mt-1 block text-[#203b35]">{destinationName}</strong></div>}
              {tour.languages?.length > 0 && <div><span className="block text-xs text-[#52615b]">Languages</span><strong className="mt-1 block text-[#203b35]">{tour.languages.join(', ')}</strong></div>}
            </div>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <ButtonLink href={`/booking.html?tour=${encodeURIComponent(tour.slug)}`}>Book this tour</ButtonLink>
              <WishlistButton listingType="tour" name={tour.name} slug={tour.slug} variant="inline" />
            </div>
          </div>
        </div>
        {(tour.itinerary?.length || tour.inclusions?.length || tour.exclusions?.length) > 0 && <div className="mt-12 grid gap-6 md:grid-cols-3">
          {tour.itinerary?.length > 0 && <TourDetailList title="Itinerary" items={tour.itinerary} />}
          {tour.inclusions?.length > 0 && <TourDetailList title="What's included" items={tour.inclusions} />}
          {tour.exclusions?.length > 0 && <TourDetailList title="What's not included" items={tour.exclusions} />}
        </div>}
        <RecommendationStrip
          currency={currency}
          description="Experiences that match this destination, style and price range."
          destination={tour.destination}
          embedded
          slug={tour.slug}
          title="You may also like"
          type="tour"
        />
        <section className="mt-14 border-t border-[#e9e5db] pt-10">
          <SectionHeading eyebrow="Guest reviews" title="What travelers said." description="Reviews are published by guests who booked this tour. Booked it too? Rate it from your account after the trip." />
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

function OperatorPage({ currency }) {
  const slug = decodeURIComponent(window.location.pathname.replace(/^\/operators\//, '').replace(/\/+$/, ''));
  const sitePhone = useWhatsAppPhone();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(`/api/operators/${encodeURIComponent(slug)}`, { signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || `This operator could not be loaded (HTTP ${response.status}).`);
        return payload;
      })
      .then((payload) => {
        setProfile({
          operator: payload.operator || {},
          tours: Array.isArray(payload.tours) ? payload.tours : [],
          services: Array.isArray(payload.services) ? payload.services : [],
          properties: Array.isArray(payload.properties) ? payload.properties : [],
        });
      })
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') setError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [slug]);

  useEffect(() => {
    if (profile?.operator?.name) document.title = `${profile.operator.name} | Kenya Tours & Marketplace`;
  }, [profile]);

  const operator = profile?.operator;
  const telephone = (operator?.phone || '').replace(/[^\d+]/g, '');
  const whatsappPhone = operator?.phone || sitePhone;
  const website = operator?.website
    ? (/^https?:\/\//i.test(operator.website) ? operator.website : `https://${operator.website.replace(/^\/+/, '')}`)
    : '';

  return (
    <PageShell>
      {loading && <section className="mx-auto max-w-5xl px-5 py-20 sm:px-8"><p className="py-8 text-center text-[#52615b]" role="status">Loading operator profile…</p></section>}
      {!loading && error && (
        <section className="mx-auto max-w-3xl px-5 py-20 text-center sm:px-8">
          <h1 className="display-font text-4xl text-[#203b35]">Operator not found</h1>
          <p className="mt-4 text-[#52615b]">{error} Browse the registered operators to find another.</p>
          <ButtonLink className="mt-7" href="/services.html">Browse services</ButtonLink>
        </section>
      )}
      {!loading && !error && operator && (
        <>
          <section className="bg-[#203b35] px-5 py-14 text-white sm:px-8 sm:py-20">
            <div className="mx-auto flex max-w-5xl flex-col gap-6 sm:flex-row sm:items-start">
              {operator.logo_url && (
                <img className="h-24 w-24 shrink-0 rounded-3xl bg-white object-contain p-2" src={imageUrl(operator.logo_url)} alt={`${operator.name} logo`} />
              )}
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#f1b28b]">{operator.business_type_labels.join(' · ') || 'Tour operator'}</p>
                <h1 className="display-font mt-3 text-4xl leading-tight sm:text-5xl">{operator.name}</h1>
                {operator.location && <p className="mt-2 text-sm text-white/70">{operator.location}</p>}
                {operator.description && <p className="mt-4 max-w-2xl leading-7 text-white/75">{operator.description}</p>}
                <div className="mt-6 flex flex-wrap gap-3">
                  <a className="inline-flex min-h-11 items-center rounded-full bg-[#16833b] px-5 text-sm font-semibold text-white hover:bg-[#116b30]" href={whatsappUrl(`Hello ${operator.name}, I would like to plan a trip with you.`, whatsappPhone)} target="_blank" rel="noopener noreferrer">
                    Message on WhatsApp
                  </a>
                  {telephone && <a className="inline-flex min-h-11 items-center rounded-full border border-white/40 px-5 text-sm font-semibold text-white hover:bg-white/10" href={`tel:${telephone}`}>Call {operator.phone}</a>}
                  {website && <a className="inline-flex min-h-11 items-center rounded-full border border-white/40 px-5 text-sm font-semibold text-white hover:bg-white/10" href={website} target="_blank" rel="noopener noreferrer">Visit website</a>}
                </div>
              </div>
            </div>
          </section>
          <section className="mx-auto max-w-7xl space-y-16 px-5 py-14 sm:px-8 sm:py-20">
            <a className="text-sm font-semibold text-[#9a5534] hover:underline" href="/services.html">← All operators and services</a>
            {profile.tours.length > 0 && (
              <div>
                <SectionHeading eyebrow="Safaris and tours" title="Tours published by this operator." description="Multi-day safaris, day trips and excursions, each with published departure times you can book online." />
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {profile.tours.map((tour) => <TourCard currency={currency} key={tour.slug} tour={tour} />)}
                </div>
              </div>
            )}
            {profile.services.length > 0 && (
              <div id="services">
                <SectionHeading eyebrow="Travel services" title="Services arranged by enquiry." description="Send a WhatsApp quote request with your dates and the operator will confirm availability and a final price." />
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {profile.services.map((service) => <ServiceCard currency={currency} key={service.slug} service={service} />)}
                </div>
              </div>
            )}
            {profile.properties.length > 0 && (
              <div>
                <SectionHeading eyebrow="Where to stay" title="Accommodation from this operator." description="Stays run by the same team, so you can arrange the whole trip in one conversation." />
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {profile.properties.map((property) => <PropertyCard currency={currency} key={property.slug || property.id} property={property} />)}
                </div>
              </div>
            )}
            {profile.tours.length === 0 && profile.services.length === 0 && profile.properties.length === 0 && (
              <div className="rounded-2xl bg-[#f5f3ed] p-6 text-[#52615b]">
                <p>{operator.name} has not published any listings yet. Send them a message to ask what they can arrange.</p>
              </div>
            )}
          </section>
        </>
      )}
    </PageShell>
  );
}

function AuthPage({ register = false }) {
  const params = new URLSearchParams(window.location.search);
  const error = params.get('error');
  const next = params.get('next') || '';
  return (
    <PageShell>
      <section className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-20">
        <div className="rounded-3xl border border-[#e9e5db] bg-white p-6 shadow-sm sm:p-10">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">Kenya Tours</p>
          <h1 className="display-font mt-3 text-4xl text-[#203b35]">{register ? 'Join the Kenya experience.' : 'Welcome back to Kenya Tours.'}</h1>
          <p className="mt-3 text-[#52615b]">{register ? 'Create an account to plan and manage your bookings.' : 'Sign in to continue planning your Kenyan trip.'}</p>
          {error && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</p>}
          <form className="mt-7 space-y-5" action={register ? '/register' : '/login'} method="post">
            {next && <input name="next" type="hidden" value={next} />}
            {register && <label className="block"><span className="field-label">Full name</span><input className="field" name="name" autoComplete="name" required /></label>}
            <label className="block"><span className="field-label">Email address</span><input className="field" name="email" type="email" autoComplete="email" required /></label>
            <label className="block"><span className="field-label">Password</span><input className="field" name="password" type="password" minLength={register ? 8 : undefined} autoComplete={register ? 'new-password' : 'current-password'} required /></label>
            {register && <label className="block"><span className="field-label">Confirm password</span><input className="field" name="confirm_password" type="password" minLength="8" autoComplete="new-password" required /></label>}
            <button className="min-h-12 w-full rounded-full bg-[#b96e45] px-6 font-semibold text-white hover:bg-[#a45d38]" type="submit">{register ? 'Create account' : 'Sign in'}</button>
          </form>
          <p className="mt-6 text-sm text-[#52615b]">
            {register ? 'Already have an account?' : 'New to Kenya Tours?'}{' '}
            <a className="font-semibold text-[#9a5534] hover:underline" href={`${register ? '/login.html' : '/register.html'}${next ? `?next=${encodeURIComponent(next)}` : ''}`}>{register ? 'Sign in' : 'Create an account'}</a>
          </p>
          {!register && <p className="mt-4 text-sm"><a className="font-semibold text-[#9a5534] underline" href="/my-bookings">View or manage your bookings</a></p>}
          <p className="mt-4 text-sm text-[#52615b]">For partners: <a className="font-semibold text-[#9a5534] hover:underline" href="/partner/login">Sign in</a> or <a className="font-semibold text-[#9a5534] hover:underline" href="/partner/register">create an account</a>.</p>
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
              ? 'Your M-Pesa payment has been verified. Thanks for booking with Kenya Tours.'
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
              <li>Plans changed? Cancel at least 48 hours ahead in My bookings and we refund the full amount.</li>
              <li>When the trip is over, sign in to My bookings to rate it and write a review.</li>
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

function BookingReviewForm({ booking, csrfToken, onSubmitted }) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/review-submit', {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify({ booking_id: booking.id, rating, comment }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Your review could not be published.');
      await onSubmitted();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="mt-5 rounded-2xl border border-[#f0d9c7] bg-[#fdf6ef] p-5" onSubmit={submit}>
      <h3 className="display-font text-xl text-[#203b35]">Rate this booking</h3>
      <p className="mt-1 text-sm text-[#52615b]">Tell other travelers how it went. Your review is published with your name.</p>
      <div className="mt-4" role="radiogroup" aria-label="Star rating">
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={rating === value}
              aria-label={`${value} star${value === 1 ? '' : 's'}`}
              className={`text-3xl leading-none ${value <= rating ? 'text-[#b96e45]' : 'text-[#d8cfc2]'}`}
              onClick={() => setRating(value)}
            >★</button>
          ))}
        </div>
      </div>
      <label className="mt-3 block"><span className="field-label">Your review</span><textarea className="field min-h-24 resize-y" value={comment} onChange={(event) => setComment(event.target.value)} maxLength={3000} required /></label>
      {error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p>}
      <button className="mt-4 rounded-full bg-[#203b35] px-5 py-3 text-sm font-semibold text-white hover:bg-[#31554b] disabled:opacity-50" type="submit" disabled={busy || rating < 1 || !comment.trim()}>Publish review</button>
    </form>
  );
}

function CustomerBookingCard({ booking, csrfToken, onChanged }) {
  const [schedules, setSchedules] = useState([]);
  const [scheduleId, setScheduleId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const canChange = ['requested', 'confirmed'].includes(booking.status);
  const isStay = booking.booking_type === 'property';
  const refundAmount = Number(booking.refund_amount || booking.amount || 0).toLocaleString(numberLocale());
  const refundLabel = { pending: 'Refund due', paid: 'Refund paid', rejected: 'Refund declined' }[booking.refund_status] || '';
  const refundMessage = {
    pending: 'Our team sends refunds manually and will email you as soon as the money is on its way.',
    paid: 'The refund was sent. Check your M-Pesa statement; it should reflect shortly.',
    rejected: 'This refund was declined. Contact our team if you would like the case reviewed again.',
  }[booking.refund_status] || '';
  const cancellationPrompt = booking.payment_status === 'paid'
    ? `Cancel this booking? KSh ${refundAmount} will be refunded to you in full.`
    : 'Cancel this booking? Changes are allowed only more than 48 hours before departure.';
  const listingLabel = isStay
    ? (booking.property_name || booking.tour.replaceAll('-', ' '))
    : booking.tour.replaceAll('-', ' ');

  useEffect(() => {
    if (isStay || !booking.schedule_id || !canChange) return undefined;
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
        <div><h2 className="display-font text-2xl text-[#203b35]">{listingLabel}</h2><p className="mt-1 text-sm text-[#52615b]">{isStay ? `${booking.room_name || 'Room'} · ${booking.check_in} to ${booking.check_out} · ${booking.nights} night${booking.nights === 1 ? '' : 's'}` : `${booking.date} at ${booking.time}`} · {booking.guests} guest{booking.guests === 1 ? '' : 's'}</p></div>
        <span className="rounded-full bg-[#efeee7] px-3 py-1 text-sm font-semibold capitalize text-[#52615b]">{booking.status}</span>
      </div>
      <p className="mt-3 text-sm text-[#52615b]">Booking #{booking.id} · KSh {Number(booking.amount).toLocaleString(numberLocale())} · Payment: {booking.payment_status}</p>
      {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p>}
      {canChange && booking.schedule_id && <div className="mt-5 flex flex-wrap items-end gap-3">
        <label className="min-w-64 flex-1"><span className="field-label">Reschedule departure</span><select className="field" value={scheduleId} onChange={(event) => setScheduleId(event.target.value)}><option value="">Choose another available time</option>{schedules.map((slot) => <option key={slot.id} value={slot.id}>{slot.starts_at.replace('T', ' ')} · {slot.remaining} spaces</option>)}</select></label>
        <button className="rounded-full border border-[#203b35] px-5 py-3 text-sm font-semibold text-[#203b35] disabled:opacity-50" type="button" disabled={busy || !scheduleId} onClick={() => mutate('reschedule', { schedule_id: Number(scheduleId) })}>Reschedule</button>
        <button className="rounded-full border border-red-200 px-5 py-3 text-sm font-semibold text-red-700 disabled:opacity-50" type="button" disabled={busy} onClick={() => { if (window.confirm(cancellationPrompt)) mutate('cancel'); }}>Cancel booking</button>
      </div>}
      {canChange && isStay && <div className="mt-5">
        <button className="rounded-full border border-red-200 px-5 py-3 text-sm font-semibold text-red-700 disabled:opacity-50" type="button" disabled={busy} onClick={() => { if (window.confirm(booking.payment_status === 'paid' ? cancellationPrompt : 'Cancel this booking? Nights are released for other guests.')) mutate('cancel'); }}>Cancel booking</button>
      </div>}
      {canChange && <p className="mt-3 text-xs text-[#52615b]">{isStay
        ? 'Cancellation is available at least 48 hours before check-in and paid bookings are refunded in full. To change your dates, cancel and book again.'
        : 'Cancellation and rescheduling are available at least 48 hours before departure, and paid bookings are refunded in full.'}</p>}
      {booking.refund_status !== 'none' && <section className="mt-5 rounded-2xl border border-[#e9e5db] bg-[#f5f3ed] p-4" role="status">
        <h3 className="display-font text-xl text-[#203b35]">Refund</h3>
        <p className="mt-1 text-sm font-semibold text-[#203b35]">KSh {refundAmount} · {refundLabel}{booking.refund_paid_at ? ` · ${new Date(booking.refund_paid_at).toLocaleDateString(numberLocale())}` : ''}</p>
        <p className="mt-2 text-sm leading-6 text-[#52615b]">{refundMessage}</p>
      </section>}
      {booking.can_review && <BookingReviewForm booking={booking} csrfToken={csrfToken} onSubmitted={onChanged} />}
      {booking.review && <section className="mt-5 rounded-2xl border border-[#e9e5db] bg-[#f5f3ed] p-4">
        <h3 className="display-font text-xl text-[#203b35]">Your review</h3>
        <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-[#203b35]">
          <StarRow rating={booking.review.rating} />
          <span>{booking.review.rating}/5</span>
        </p>
        <p className="mt-2 text-sm leading-6 text-[#52615b]">{booking.review.comment}</p>
      </section>}
      {!booking.can_review && !booking.review && booking.review_status === 'upcoming' && <p className="mt-5 rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">{isStay ? 'After your stay, come back here to rate it and write a review.' : 'After your experience, come back here to rate it and write a review.'}</p>}
    </article>
  );
}

function SavedListingCard({ item, currency }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const isTour = item.listing_type === 'tour';

  async function remove() {
    setBusy(true);
    setError('');
    try {
      await removeSaved(item);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-[#e9e5db] bg-white shadow-sm">
      {item.still_listed ? (
        <a className="block" href={item.url} aria-label={`View ${item.name}`}>
          <img className="h-44 w-full object-cover" src={imageUrl(item.image_url)} alt={item.name} loading="lazy" />
        </a>
      ) : (
        <div className="grid h-44 place-items-center bg-[#f5f3ed] px-6 text-center text-sm font-semibold text-[#8a8172]">
          No longer available
        </div>
      )}
      <div className="flex flex-1 flex-col p-5">
        <p className="text-xs font-bold uppercase tracking-wider text-[#a75f3a]">
          {item.listing_type_label}{item.destination_name ? ` · ${item.destination_name}` : ''}
        </p>
        <h3 className="display-font mt-2 text-xl text-[#203b35]">{item.name}</h3>
        {item.still_listed ? (
          <>
            {item.review_count > 0 && (
              <p className="mt-1 flex items-center gap-2 text-sm text-[#52615b]">
                <StarRow rating={item.rating} />
                <span>{Number(item.rating).toFixed(1)} · {item.review_count} review{item.review_count === 1 ? '' : 's'}</span>
              </p>
            )}
            <p className="mt-2 text-sm text-[#52615b]">
              {item.price > 0 ? `${formatPrice(item.price, currency)} ${item.price_unit}` : 'Ask our team for a price'}
            </p>
            <a className="mt-3 inline-flex w-fit rounded-full bg-[#203b35] px-4 py-2 text-sm font-semibold text-white hover:bg-[#31554b]" href={item.url}>
              {isTour ? 'View tour' : 'View stay'}
            </a>
          </>
        ) : (
          <p className="mt-2 text-sm leading-6 text-[#52615b]">This listing was removed from the marketplace, so it cannot be opened or booked.</p>
        )}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-[#efede7] pt-4">
          {item.still_listed
            ? <CompareToggle name={item.name} slug={item.listing_slug} type={item.listing_type} />
            : <span aria-hidden="true" />}
          <button className="text-sm font-semibold text-[#52615b] hover:text-[#9a5534] disabled:opacity-50" disabled={busy} onClick={remove} type="button">
            {busy ? 'Removing…' : 'Remove'}
          </button>
        </div>
        {error && <p className="mt-2 text-xs font-semibold text-[#9a5534]" role="alert">{error}</p>}
      </div>
    </article>
  );
}

function WishlistPage({ currency }) {
  const wishlist = useWishlist();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    // The header already fetches on mount; only fetch again when that failed.
    const state = getWishlistSnapshot();
    if (state.status === 'idle' || state.status === 'error') loadWishlist();
  }, []);

  async function clearAll() {
    if (!window.confirm('Remove every listing from your wishlist?')) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await clearSaved();
      setNotice('Your wishlist is empty now. Save a tour or stay to start a new one.');
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  const loading = wishlist.status === 'idle' || wishlist.status === 'loading';
  const available = wishlist.items.filter((item) => item.still_listed);
  const removed = wishlist.items.filter((item) => !item.still_listed);

  return (
    <PageShell>
      <PageBanner
        eyebrow="Your wishlist"
        title="Everything you saved, ready when you are."
        description="Keep the tours and stays you love in one place. Prices and availability are always shown live, so you can plan without second-guessing what you saw earlier."
      />
      <section className="mx-auto max-w-7xl space-y-6 px-5 py-12 sm:px-8 sm:py-16">
        {loading && <p className="text-[#52615b]" role="status">Loading your saved listings…</p>}

        {!loading && wishlist.status === 'error' && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800" role="alert">
            <p>{wishlist.error || 'Your wishlist could not be loaded.'}</p>
            <button className="mt-3 rounded-full border border-red-300 px-4 py-2 text-sm font-semibold" onClick={() => loadWishlist({ force: true })} type="button">Try again</button>
          </div>
        )}

        {!loading && wishlist.status === 'guest' && (
          <div className="rounded-3xl border border-[#e9e5db] bg-white p-8 text-center shadow-sm sm:p-12">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#a75f3a]">Sign in to save</p>
            <h2 className="display-font mt-3 text-3xl text-[#203b35]">Your wishlist lives in your account.</h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-[#52615b]">Tap the heart on any tour or stay while signed in and it lands here, on every device you use. New here? Create an account in under a minute.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <ButtonLink href="/login.html?next=/wishlist.html">Sign in</ButtonLink>
              <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/register.html" secondary>Create an account</ButtonLink>
            </div>
          </div>
        )}

        {!loading && wishlist.status === 'ready' && (
          <>
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <SectionHeading
                eyebrow="Saved"
                title={wishlist.items.length === 0
                  ? 'Nothing saved yet.'
                  : `${wishlist.items.length} saved listing${wishlist.items.length === 1 ? '' : 's'}.`}
                description={wishlist.items.length === 0
                  ? 'Tap the heart on any tour or stay and it will wait for you here.'
                  : 'Prices and availability refresh every time you open this page.'}
              />
              {wishlist.items.length > 0 && (
                <div className="mb-8">
                  <button className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white disabled:opacity-50" disabled={busy} onClick={clearAll} type="button">Clear all</button>
                </div>
              )}
            </div>

            {notice && <p className="text-sm font-semibold text-[#177b5b]" role="status">{notice}</p>}
            {error && <p className="rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</p>}

            {wishlist.items.length === 0 ? (
              <div className="rounded-3xl border border-[#e9e5db] bg-white p-8 text-center shadow-sm sm:p-12">
                <HeartIcon className="mx-auto h-10 w-10 text-[#c9b8a8]" />
                <p className="mt-4 text-sm leading-6 text-[#52615b]">Browse experiences and places to stay, then save the ones that fit your trip.</p>
                <div className="mt-6 flex flex-wrap justify-center gap-3">
                  <ButtonLink href="/tours.html">Browse experiences</ButtonLink>
                  <ButtonLink className="border-[#203b35] bg-white text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/properties.html" secondary>Browse stays</ButtonLink>
                </div>
              </div>
            ) : (
              <>
                {available.length > 0 && (
                  <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    {available.map((item) => <SavedListingCard currency={currency} item={item} key={item.id} />)}
                  </div>
                )}
                {removed.length > 0 && (
                  <section className="space-y-4" aria-labelledby="wishlist-removed-heading">
                    <h2 className="display-font text-2xl text-[#203b35]" id="wishlist-removed-heading">No longer available</h2>
                    <p className="text-sm leading-6 text-[#52615b]">These listings left the marketplace after you saved them. Remove them to keep your wishlist tidy.</p>
                    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                      {removed.map((item) => <SavedListingCard currency={currency} item={item} key={item.id} />)}
                    </div>
                  </section>
                )}
              </>
            )}
          </>
        )}
      </section>
    </PageShell>
  );
}

function MyBookingsPage() {
  const [profile, setProfile] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const pendingReviews = bookings.filter((booking) => booking.can_review).length;

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
      <PageBanner eyebrow="Your account" title="My account and bookings." description="View your account details, manage your trips and review the ones you have taken." />
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
          <div className="mt-5 flex flex-wrap gap-3 border-t border-[#efede7] pt-4">
            <a className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" href="/wishlist.html">Saved listings</a>
            <a className="rounded-full border border-[#dedbd2] px-4 py-2 text-sm font-semibold text-[#52615b] hover:bg-[#eeeee6]" href="/compare.html">Compare shortlist</a>
          </div>
        </section>}
        {profile && pendingReviews > 0 && <section className="rounded-2xl border border-[#f0d9c7] bg-[#fdf6ef] p-5" role="status">
          <h2 className="display-font text-2xl text-[#203b35]">{pendingReviews === 1 ? 'One booking is waiting for your review.' : `${pendingReviews} bookings are waiting for your review.`}</h2>
          <p className="mt-2 text-sm text-[#52615b]">Rate each trip below so other travelers can book with confidence. Your review is published with your name.</p>
        </section>}
        {!loading && !error && bookings.length === 0 && <div className="rounded-2xl bg-white p-7"><h2 className="display-font text-2xl text-[#203b35]">No bookings yet</h2><p className="mt-2 text-[#52615b]">When you book while signed in, your trips will appear here.</p><ButtonLink className="mt-5" href="/tours.html">Explore tours</ButtonLink></div>}
        {profile && bookings.map((booking) => <CustomerBookingCard key={booking.id} booking={booking} csrfToken={profile.csrf_token} onChanged={load} />)}
        {profile && bookings.length > 0 && <p className="rounded-2xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">We will keep reminding you here to rate each booking once the trip is over.</p>}
      </section>
    </PageShell>
  );
}

function NotFoundPage() {
  return (
    <PageShell>
      <section className="mx-auto max-w-3xl px-5 py-20 text-center sm:px-8 sm:py-28">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">404 · Page not found</p>
        <h1 className="display-font mt-4 text-4xl text-[#203b35]">This isn’t the destination you’re looking for.</h1>
        <p className="mt-4 text-[#52615b]">The page may have moved. Head home or browse the Kenya tours instead.</p>
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
    if (pathname.startsWith('/admin') || pathname.startsWith('/partner') || pathname.startsWith('/vendor') || pathname === '/dashboard') return;

    const campaignSource = new URLSearchParams(window.location.search).get('utm_source');
    let referrerSource = '';
    try {
      referrerSource = document.referrer ? new URL(document.referrer).hostname : '';
    } catch {
      referrerSource = '';
    }

    let source = campaignSource || referrerSource;
    try {
      const sourceKey = 'kenya-first-touch-source';
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

    const selector = [
      'main > section',
      'main > div',
      '.image-card',
      '.mosaic-card',
      '.story-frame',
      '.story-point',
      '.tour-card',
      '.stay-card',
    ].join(', ');
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

    document.addEventListener('kenya-language-changed', refreshLocalizedValues);
    return () => document.removeEventListener('kenya-language-changed', refreshLocalizedValues);
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
        document.documentElement.dataset.socialLinks = JSON.stringify(data.social_links || []);
        const compareMeta = {};
        data.tours.forEach((tour) => { compareMeta[`tour:${tour.slug}`] = { name: tour.name, image: tour.image_url }; });
        data.properties.forEach((property) => { compareMeta[`property:${property.slug}`] = { name: property.name, image: property.image_url }; });
        document.documentElement.dataset.compareMeta = JSON.stringify(compareMeta);
        document.dispatchEvent(new Event('kenya-catalogue-ready'));
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
      '/': 'Kenya Tours & Marketplace | Tours and accommodations across Kenya',
      '/index.html': 'Kenya Tours & Marketplace | Tours and accommodations across Kenya',
      '/tours.html': 'Kenya tours and experiences | Kenya Tours & Marketplace',
      '/properties.html': 'Hotels, lodges, resorts and vacation rentals in Kenya | Kenya Tours & Marketplace',
      '/explore.html': 'Explore by category | Kenya Tours & Marketplace',
      '/safari-operators.html': 'Licensed safari and tour operators in Kenya | Kenya Tours & Marketplace',
      '/destinations.html': 'Kenya destinations by region | Kenya Tours & Marketplace',
      '/blog.html': 'Travel guides for visiting Kenya | Kenya Tours & Marketplace',
      '/gallery.html': 'Photo gallery of Kenya destinations | Kenya Tours & Marketplace',
      '/reviews.html': 'Community reviews from guests | Kenya Tours & Marketplace',
      '/compare.html': 'Compare tours and stays side by side | Kenya Tours & Marketplace',
      '/wishlist.html': 'Your wishlist | Kenya Tours & Marketplace',
      '/faq.html': 'Frequently asked questions | Kenya Tours & Marketplace',
      '/how-it-works.html': 'How it works | Kenya Tours & Marketplace',
      '/booking-guide.html': 'Booking guide | Kenya Tours & Marketplace',
      '/cancellation-policy.html': 'Cancellation policy | Kenya Tours & Marketplace',
      '/privacy-policy.html': 'Privacy policy | Kenya Tours & Marketplace',
      '/terms.html': 'Terms & conditions | Kenya Tours & Marketplace',
      '/services.html': 'Safari operators and travel services | Kenya Tours & Marketplace',
      '/booking.html': 'Plan your Kenya trip | Kenya Tours & Marketplace',
      '/about-kenya.html': 'Discover Kenya | Kenya Tours & Marketplace',
      '/about-lamu.html': 'Discover Kenya | Kenya Tours & Marketplace',
      '/contact.html': 'Contact us | Kenya Tours & Marketplace',
      '/search.html': 'Search tours, accommodations and places | Kenya Tours & Marketplace',
      '/login.html': 'Sign in | Kenya Tours & Marketplace',
      '/register.html': 'Create an account | Kenya Tours & Marketplace',
      '/tour-details.html': 'Tour details | Kenya Tours & Marketplace',
      '/booking-confirmation.html': 'Booking request received | Kenya Tours & Marketplace',
      '/my-bookings': 'My account | Kenya Tours & Marketplace',
      '/admin/login': 'Admin sign in | Kenya Tours',
      '/admin': 'Admin dashboard | Kenya Tours',
      '/admin/dashboard': 'Admin dashboard | Kenya Tours',
      '/dashboard': 'Bookings and messages | Kenya Tours',
      '/vendor/login': 'Partner sign in | Kenya Tours',
      '/vendor/register': 'Partner registration | Kenya Tours',
      '/vendor/dashboard': 'Partner dashboard | Kenya Tours',
      '/partner/login': 'Partner sign in | Kenya Tours',
      '/partner/register': 'Partner registration | Kenya Tours',
      '/partner/dashboard': 'Partner dashboard | Kenya Tours',
    };
    document.title = titles[pathname] || 'Kenya Tours & Marketplace';
  }, [pathname]);

  if (pathname === '/admin/login') return <AdminLoginPage />;
  if (pathname === '/admin' || pathname === '/admin/dashboard') return <AdminDashboardPage />;
  if (pathname === '/dashboard') return <AdminActivityDashboardPage />;
  if (pathname === '/vendor/login' || pathname === '/partner/login') return <VendorLoginPage />;
  if (pathname === '/vendor/register' || pathname === '/partner/register') return <VendorRegistrationPage />;
  if (pathname === '/vendor/dashboard' || pathname === '/partner/dashboard') return <VendorDashboardPage />;
  if (pathname === '/search.html') return <SearchPage catalogue={catalogue} currency={currency} />;
  if (pathname === '/properties.html') return <PropertiesPage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname === '/explore.html') return <ExplorePage catalogue={catalogue} error={error} loading={loading} retry={retry} />;
  if (pathname === '/safari-operators.html') return <SafariOperatorsPage catalogue={catalogue} error={error} loading={loading} retry={retry} />;
  if (pathname === '/destinations.html') return <DestinationsPage catalogue={catalogue} error={error} loading={loading} retry={retry} />;
  if (pathname === '/blog.html') return <BlogPage />;
  if (pathname.startsWith('/blog/')) return <BlogArticlePage />;
  if (pathname === '/gallery.html') return <PhotoGalleryPage catalogue={catalogue} loading={loading} />;
  if (pathname === '/reviews.html') return <CommunityReviewsPage />;
  if (pathname === '/compare.html') return <ComparePage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname === '/wishlist.html') return <WishlistPage currency={currency} />;
  if (pathname === '/faq.html') return <FaqPage />;
  const supportPage = findSupportPage(pathname);
  if (supportPage) return <SupportPage page={supportPage} />;
  if (pathname === '/services.html') return <ServicesPage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname.startsWith('/operators/')) return <OperatorPage currency={currency} />;
  if (pathname === '/tours.html') return <ToursPage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname === '/booking.html') return <BookingPage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname === '/my-bookings') return <MyBookingsPage />;
  if (pathname === '/about-kenya.html' || pathname === '/about-lamu.html') return <AboutKenyaPage />;
  if (pathname === '/contact.html') return <ContactPage />;
  if (pathname === '/login.html' || pathname === '/login') return <AuthPage />;
  if (pathname === '/register.html' || pathname === '/register') return <AuthPage register />;
  if (pathname === '/tour-details.html') return <TourDetailPage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  if (pathname === '/booking-confirmation.html') return <ConfirmationPage />;
  if (pathname === '/' || pathname === '/index.html') return <HomePage catalogue={catalogue} currency={currency} error={error} loading={loading} retry={retry} />;
  return <NotFoundPage />;
}
