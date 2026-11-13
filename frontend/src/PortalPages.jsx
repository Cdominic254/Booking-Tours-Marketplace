import { useEffect, useState } from 'react';
import { documentLanguage, formatNumber, getErrorMessage as messageFrom, numberLocale } from './utils.js';

async function apiRequest(path, { method = 'GET', data, csrfToken, signal } = {}) {
  const headers = { Accept: 'application/json' };
  if (data) headers['Content-Type'] = 'application/json';
  if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
  const response = await fetch(path, {
    method,
    headers,
    ...(data ? { body: JSON.stringify(data) } : {}),
    ...(signal ? { signal } : {}),
  });
  if (response.status === 204) return null;
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (HTTP ${response.status}).`);
  return result;
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString(numberLocale());
}

function LanguageToggle() {
  const [language, setLanguage] = useState(documentLanguage());

  useEffect(() => {
    function syncLanguage(event) {
      setLanguage(event.detail.language);
    }

    document.addEventListener('kenya-language-changed', syncLanguage);
    return () => document.removeEventListener('kenya-language-changed', syncLanguage);
  }, []);

  function toggleLanguage() {
    const nextLanguage = language === 'en' ? 'sw' : 'en';
    window.setKenyaLanguage?.(nextLanguage);
    setLanguage(nextLanguage);
  }

  return (
    <button
      className="rounded-full border border-[#dedbd2] px-4 py-2 text-sm font-semibold text-[#52615b] hover:bg-[#eeeee6]"
      type="button"
      data-language-toggle
      aria-label={language === 'en' ? 'Switch to Kiswahili' : 'Switch to English'}
      aria-pressed={language === 'sw'}
      onClick={toggleLanguage}
    >
      {language === 'en' ? 'Kiswahili' : 'English'}
    </button>
  );
}

function PortalCard({ children }) {
  return <main className="mx-auto max-w-3xl px-5 py-12 sm:px-8 sm:py-20"><div className="rounded-3xl border border-[#e9e5db] bg-white p-6 shadow-sm sm:p-10">{children}</div></main>;
}

const businessTypeOptions = [
  ['safari', 'Safari operator'],
  ['tours', 'Tour operator'],
  ['accommodation', 'Accommodation host'],
  ['transport', 'Transport & transfers'],
  ['services', 'Other travel services'],
];

const fallbackServiceTypes = [
  ['transfer', 'Airport & hotel transfer'],
  ['guide', 'Private guide'],
  ['vehicle', 'Vehicle & driver hire'],
  ['photography', 'Photography'],
  ['catering', 'Catering & dining'],
  ['equipment', 'Equipment hire'],
  ['other', 'Other travel service'],
];

const fallbackPriceUnits = ['per person', 'per group', 'per day', 'per trip', 'per hour'];
const fallbackTourTypes = [
  ['experience', 'Experience'],
  ['day-safari', 'Day safari'],
  ['multi-day-safari', 'Multi-day safari'],
  ['excursion', 'Excursion'],
];
const fallbackGroupTypes = [['private', 'Private group'], ['shared', 'Shared group']];

function destinationOptions(destinations) {
  return destinations?.length
    ? destinations.map((destination) => [destination.slug, destination.name])
    : [['lamu', 'Lamu']];
}

function PortalIdentity({ children }) {
  return (
    <a className="brand-lockup flex items-center gap-3" href="/" aria-label={`Kenya Tours & Marketplace ${children}`}>
      <img className="brand-mark h-12 w-12" src="/logo.svg" alt="" />
      <span className="flex flex-col">
        <span className="brand-name text-lg font-bold text-[#203b35] sm:text-xl">Kenya Tours & Marketplace</span>
        <span className="brand-tagline text-[0.6rem] font-bold uppercase tracking-[0.14em] text-[#52718a]">{children}</span>
      </span>
    </a>
  );
}

function PortalLogin({ role }) {
  const isPartner = role === 'partner';
  const error = new URLSearchParams(window.location.search).get('error');
  return (
    <div className="min-h-screen bg-[#f8f7f2]">
      <header className="border-b border-[#e9e5db] bg-white px-5 py-4 sm:px-8"><div className="mx-auto flex max-w-7xl items-center justify-between gap-4"><PortalIdentity>{isPartner ? 'Partner portal' : 'Admin portal'}</PortalIdentity><LanguageToggle /></div></header>
      <PortalCard>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">{isPartner ? 'Partner access' : 'Administration'}</p>
        <h1 className="display-font mt-3 text-4xl text-[#203b35]">{isPartner ? 'Welcome back to your business.' : 'Welcome to your control room.'}</h1>
        <p className="mt-3 text-[#52615b]">{isPartner ? 'Your Kenyan tours, services, stays, departures, and guest bookings are all waiting here.' : 'Your Kenya marketplace overview, catalog, and account controls.'}</p>
        {error && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</p>}
        <form className="mt-7 space-y-5" action={isPartner ? '/partner/login' : '/admin/login'} method="post">
          <label className="block"><span className="field-label">Email address</span><input className="field" name="email" type="email" autoComplete="username" required /></label>
          <label className="block"><span className="field-label">Password</span><input className="field" name="password" type="password" autoComplete="current-password" required /></label>
          <button className="min-h-12 w-full rounded-full bg-[#203b35] px-6 font-semibold text-white hover:bg-[#31554b]" type="submit">Sign in</button>
        </form>
        {isPartner ? (
          <p className="mt-6 text-sm text-[#52615b]">New partner? <a className="font-semibold text-[#9a5534] hover:underline" href="/partner/register">Create a partner account</a></p>
        ) : (
          <p className="mt-6 text-sm text-[#52615b]">Traveler or partner? <a className="font-semibold text-[#9a5534] hover:underline" href="/login.html">Use the traveler sign-in</a></p>
        )}
        <a className="mt-5 inline-block text-sm text-[#52615b] underline" href="/">Return to the public site</a>
      </PortalCard>
    </div>
  );
}

export function AdminLoginPage() {
  return <PortalLogin role="admin" />;
}

export function VendorLoginPage() {
  return <PortalLogin role="partner" />;
}

export function VendorRegistrationPage() {
  const [csrfToken, setCsrfToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest('/api/vendor/registration-token', { signal: controller.signal })
      .then(({ csrf_token: token }) => setCsrfToken(token))
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setError(messageFrom(requestError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  async function submitRegistration(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    const formData = new FormData(event.currentTarget);
    const data = Object.fromEntries(formData);
    data.business_types = formData.getAll('business_types');
    try {
      await apiRequest('/partner/register', {
        method: 'POST',
        data,
        csrfToken,
      });
      window.location.assign('/partner/dashboard');
    } catch (requestError) {
      setError(messageFrom(requestError));
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f7f2]">
      <header className="border-b border-[#e9e5db] bg-white px-5 py-4 sm:px-8"><div className="mx-auto flex max-w-7xl items-center justify-between gap-4"><PortalIdentity>Partner portal</PortalIdentity><LanguageToggle /></div></header>
      <PortalCard>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#a75f3a]">Partner with us</p>
        <h1 className="display-font mt-3 text-4xl text-[#203b35]">Bring your Kenyan experience to more travelers.</h1>
        <p className="mt-3 text-[#52615b]">Safari operators, tour guides, transport providers and hosts: create a partner account to publish tours, services and stays, and keep your bookings in view.</p>
        {error && <p className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</p>}
        <form className="mt-7 space-y-5" onSubmit={submitRegistration}>
          <label className="block"><span className="field-label">Your name or business name</span><input className="field" name="name" autoComplete="organization" required /></label>
          <label className="block"><span className="field-label">Email address</span><input className="field" name="email" type="email" autoComplete="email" required /></label>
          <label className="block"><span className="field-label">Password</span><input className="field" name="password" type="password" minLength="12" autoComplete="new-password" required /><span className="mt-1 block text-xs text-[#52615b]">Use at least 12 characters.</span></label>
          <fieldset>
            <legend className="field-label">What do you offer?</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {businessTypeOptions.map(([value, label]) => (
                <label className="flex items-center gap-3 rounded-xl border border-[#e9e5db] p-3 text-sm text-[#203b35]" key={value}>
                  <input name="business_types" type="checkbox" value={value} defaultChecked={value === 'tours'} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="block"><span className="field-label">Base location (optional)</span><input className="field" name="location" placeholder="Lamu, Maasai Mara, Nairobi…" /></label>
            <label className="block"><span className="field-label">Phone or WhatsApp (optional)</span><input className="field" name="phone" type="tel" placeholder="+254 7xx xxx xxx" /></label>
          </div>
          <label className="block"><span className="field-label">About your business (optional)</span><textarea className="field min-h-24 resize-y" name="description" placeholder="Tell travellers about your guides, vehicles, camps and the trips you run." /></label>
          <button className="min-h-12 w-full rounded-full bg-[#b96e45] px-6 font-semibold text-white hover:bg-[#a45d38] disabled:opacity-60" type="submit" disabled={loading || submitting || !csrfToken}>
            {loading ? 'Preparing secure sign-up…' : submitting ? 'Creating account…' : 'Create partner account'}
          </button>
        </form>
        <p className="mt-6 text-sm text-[#52615b]">Already registered? <a className="font-semibold text-[#9a5534] hover:underline" href="/partner/login">Partner sign in</a></p>
        <a className="mt-5 inline-block text-sm text-[#52615b] underline" href="/">Return to the public site</a>
      </PortalCard>
    </div>
  );
}

function PortalHeader({ role, actor, onSignOut }) {
  return (
    <header className="portal-header bg-[#203b35] text-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#f1b28b]">{role} portal</p>
          <h1 className="display-font mt-1 text-3xl">{actor}</h1>
        </div>
        <div className="flex items-center gap-3">
          <LanguageToggle />
          <a className="rounded-full border border-white/30 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10" href="/">Public site</a>
          {onSignOut && <button className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-[#203b35] hover:bg-[#e8eee9]" type="button" onClick={onSignOut}>Sign out</button>}
        </div>
      </div>
    </header>
  );
}

function Notice({ children, error = false }) {
  if (!children) return null;
  return <p className={`rounded-xl p-4 text-sm ${error ? 'bg-red-50 text-red-800' : 'bg-green-50 text-green-800'}`} role={error ? 'alert' : 'status'}>{children}</p>;
}

function tourFields(destinations = []) {
  return [
    { name: 'name', label: 'Name', required: true },
    { name: 'category', label: 'Category', required: true },
    { name: 'tour_type', label: 'Tour style', type: 'select', options: fallbackTourTypes, required: true },
    { name: 'destination', label: 'Destination', type: 'select', options: destinationOptions(destinations), required: true },
    { name: 'duration', label: 'Duration (e.g. 3 days / 2 nights)', required: true },
    { name: 'duration_days', label: 'Length in days', type: 'number', min: 1, required: true },
    { name: 'group_type', label: 'Group style', type: 'select', options: fallbackGroupTypes, required: true },
    { name: 'price', label: 'Price (KSh per guest)', type: 'number', min: 1, required: true },
    { name: 'pickup_point', label: 'Pickup or departure point', required: true },
    { name: 'min_group_size', label: 'Minimum group size', type: 'number', min: 1, required: true },
    { name: 'max_group_size', label: 'Maximum group size', type: 'number', min: 1, required: true },
    { name: 'languages', label: 'Guide languages (comma separated)', wide: true },
    { name: 'image_url', label: 'Image URL or images/ path' },
    { name: 'itinerary', label: 'Day-by-day itinerary (one line per stop; Highlights: ...)', type: 'textarea', wide: true },
    { name: 'inclusions', label: "What's included (one item per line)", type: 'textarea', wide: true },
    { name: 'exclusions', label: "What's not included (one item per line)", type: 'textarea', wide: true },
    { name: 'description', label: 'Description', type: 'textarea', wide: true, required: true },
  ];
}

function serviceFields({ service_types: serviceTypes, service_price_units: priceUnits, destinations } = {}) {
  return [
    { name: 'name', label: 'Service name', required: true },
    { name: 'service_type', label: 'Service type', type: 'select', options: serviceTypes?.length ? serviceTypes : fallbackServiceTypes, required: true },
    { name: 'price_from', label: 'Starting price (KSh)', type: 'number', min: 1, required: true },
    { name: 'price_unit', label: 'Priced', type: 'select', options: (priceUnits?.length ? priceUnits : fallbackPriceUnits).map((unit) => [unit, unit]), required: true },
    { name: 'location', label: 'Where travellers meet or collect', required: true },
    { name: 'destination', label: 'Destination', type: 'select', options: destinationOptions(destinations), required: true },
    { name: 'is_active', label: 'Visibility', type: 'select', options: [['true', 'Visible to travellers'], ['false', 'Hidden']] },
    { name: 'image_url', label: 'Image URL or images/ path' },
    { name: 'coverage', label: 'Areas covered (one per line)', type: 'textarea', wide: true },
    { name: 'inclusions', label: 'What the price includes (one per line)', type: 'textarea', wide: true },
    { name: 'description', label: 'Description', type: 'textarea', wide: true, required: true },
  ];
}

const propertyFields = [
  { name: 'name', label: 'Name', required: true },
  { name: 'property_type', label: 'Type', type: 'select', options: ['hotel', 'lodge', 'resort', 'apartment', 'rental', 'hostel'], required: true },
  { name: 'location', label: 'Location', required: true },
  { name: 'amenities', label: 'Amenities (one per line)', type: 'textarea', wide: true },
  { name: 'latitude', label: 'Latitude', type: 'number', step: 'any' },
  { name: 'longitude', label: 'Longitude', type: 'number', step: 'any' },
  { name: 'price_per_night', label: 'Price per night (KSh)', type: 'number', min: 1, required: true },
  { name: 'guests', label: 'Guest capacity', type: 'number', min: 1, required: true },
  { name: 'image_url', label: 'Image URL or images/ path' },
  { name: 'description', label: 'Description', type: 'textarea', wide: true, required: true },
];

const destinationFields = [
  { name: 'name', label: 'Name', required: true },
  { name: 'search_location', label: 'Search location', required: true },
  { name: 'site_type', label: 'Nearby site type', type: 'select', options: ['area', 'beach', 'heritage'] },
  { name: 'latitude', label: 'Latitude', type: 'number', step: 'any' },
  { name: 'longitude', label: 'Longitude', type: 'number', step: 'any' },
  { name: 'image_url', label: 'Image URL or pictures/ path' },
  { name: 'description', label: 'Description', type: 'textarea', wide: true, required: true },
];

function DashboardField({ field, value }) {
  const common = {
    className: 'field',
    name: field.name,
    required: Boolean(field.required),
    ...(field.min ? { min: field.min } : {}),
    ...(field.type === 'number' ? { step: field.step || '1' } : {}),
  };
  const options = (field.options || []).map((option) => (Array.isArray(option) ? option : [option, option]));
  const selectValue = value === undefined || value === null || value === ''
    ? String(options[0]?.[0] ?? '')
    : String(value);
  return (
    <label className={field.wide ? 'block sm:col-span-2' : 'block'}>
      <span className="field-label">{field.label}</span>
      {field.type === 'textarea'
        ? <textarea {...common} className="field min-h-24 resize-y" defaultValue={Array.isArray(value) ? value.join('\n') : value ?? ''} />
        : field.type === 'select'
          ? <select {...common} defaultValue={selectValue}>{options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}</select>
          : <input {...common} type={field.type || 'text'} minLength={field.minLength} defaultValue={Array.isArray(value) ? value.join(', ') : value ?? ''} />}
    </label>
  );
}

function DataForm({ fields, item = {}, submitLabel, onSubmit, children }) {
  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(Object.fromEntries(new FormData(event.currentTarget)), event.currentTarget);
      }}
    >
      {fields.map((field) => <DashboardField field={field} key={field.name} value={item[field.name]} />)}
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <button className="rounded-full bg-[#203b35] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#31554b] disabled:opacity-60" type="submit">{submitLabel}</button>
        {children}
      </div>
    </form>
  );
}

function SectionCard({ title, description, children }) {
  return (
    <section className="rounded-2xl border border-[#e9e5db] bg-white p-5 shadow-sm sm:p-7">
      <div className="mb-5">
        <h2 className="display-font text-2xl text-[#203b35]">{title}</h2>
        {description && <p className="mt-2 text-sm leading-6 text-[#52615b]">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function PhotoUpload({ endpoint, csrfToken, fieldName = 'image_url' }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  async function upload(event) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    const form = input.form;
    if (!file || !form) return;
    setUploading(true);
    setError('');
    const body = new FormData();
    body.append('image', file);
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { Accept: 'application/json', 'X-CSRF-Token': csrfToken || '' },
        body,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Photo upload failed.');
      const imageField = form.elements.namedItem(fieldName);
      if (imageField) imageField.value = result.image_url;
    } catch (uploadError) {
      setError(messageFrom(uploadError));
    } finally {
      setUploading(false);
      input.value = '';
    }
  }

  return (
    <label className="block">
      <span className="field-label">Upload a photo</span>
      <input className="field" type="file" accept="image/jpeg,image/png,image/webp" onChange={upload} disabled={uploading} />
      {uploading && <span className="mt-1 block text-xs text-[#52615b]">Uploading photo…</span>}
      {error && <span className="mt-1 block text-xs text-red-700" role="alert">{error}</span>}
    </label>
  );
}

function CatalogSection({ title, items, fields, basePath, onMutation, ownerLabel, csrfToken }) {
  const [formError, setFormError] = useState('');
  const itemLabel = title.endsWith('ies') ? `${title.slice(0, -3)}y` : title.slice(0, -1);
  const uploadEndpoint = basePath.startsWith('/api/vendor') ? '/api/vendor/uploads' : '/api/admin/uploads';

  async function create(data, form) {
    setFormError('');
    const success = await onMutation(basePath, 'POST', data, `${itemLabel} added.`);
    if (success) form.reset();
    else setFormError('The new listing could not be saved.');
  }

  async function update(url, data) {
    setFormError('');
    const success = await onMutation(url, 'PUT', data, 'Changes saved.');
    if (!success) setFormError('Changes could not be saved.');
  }

  async function remove(url, name) {
    if (!window.confirm(`Delete ${name}? This cannot be undone.`)) return;
    setFormError('');
    const success = await onMutation(url, 'DELETE', undefined, 'Listing deleted.');
    if (!success) setFormError('This listing could not be deleted.');
  }

  return (
    <SectionCard title={title} description={`Create and manage ${title.toLowerCase()}.`}>
      <DataForm fields={fields} submitLabel={`Add ${itemLabel.toLowerCase()}`} onSubmit={create}>
        {fields.some((field) => field.name === 'image_url') && <PhotoUpload endpoint={uploadEndpoint} csrfToken={csrfToken} />}
      </DataForm>
      <Notice error>{formError}</Notice>
      <div className="mt-6 space-y-4">
        {items.length === 0 && <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No {title.toLowerCase()} yet.</p>}
        {items.map((item) => {
          const url = `${basePath}/${encodeURIComponent(item.slug ?? item.id)}`;
          return (
            <article className="rounded-xl border border-[#e9e5db] p-4 sm:p-5" key={`${item.id ?? item.slug}-${JSON.stringify(item)}`}>
              <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold text-[#203b35]">{item.name}</h3>
                  {ownerLabel?.(item) && <p className="mt-1 text-xs text-[#52615b]">{ownerLabel(item)}</p>}
                  {item.promotion && (
                    <p className="mt-1 text-xs font-semibold text-[#8a5a25]">
                      Sponsored · {item.promotion.live ? `live until ${formatDate(item.promotion.ends_on)}` : `${formatDate(item.promotion.starts_on)} to ${formatDate(item.promotion.ends_on)}`}
                    </p>
                  )}
                </div>
                {item.price != null && <span className="text-sm font-semibold text-[#9a5534]">KSh {formatNumber(item.price)}</span>}
                {item.price_per_night != null && <span className="text-sm font-semibold text-[#9a5534]">KSh {formatNumber(item.price_per_night)} / night</span>}
                {item.price_from != null && <span className="text-sm font-semibold text-[#9a5534]">From KSh {formatNumber(item.price_from)} {item.price_unit}</span>}
              </div>
              <DataForm fields={fields} item={item} submitLabel="Save changes" onSubmit={(data) => update(url, data)}>
                {fields.some((field) => field.name === 'image_url') && <PhotoUpload endpoint={uploadEndpoint} csrfToken={csrfToken} />}
                <button
                  className="rounded-full border border-red-200 px-5 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-50"
                  type="button"
                  onClick={() => remove(url, item.name)}
                >
                  Delete
                </button>
              </DataForm>
            </article>
          );
        })}
      </div>
    </SectionCard>
  );
}

function PromotionSection({ promotions = [], tours = [], properties = [], tiers = [], maxActive = 6, onMutation }) {
  const [formError, setFormError] = useState('');
  const isoDay = (offsetDays) => {
    const day = new Date();
    day.setDate(day.getDate() + offsetDays);
    return day.toISOString().slice(0, 10);
  };
  const listingOptions = [
    ...tours.filter((tour) => tour.slug).map((tour) => [`tour:${tour.slug}`, `Experience · ${tour.name}`]),
    ...properties.filter((item) => item.slug).map((item) => [`property:${item.slug}`, `Stay · ${item.name}`]),
  ];
  const fields = [
    { name: 'listing', label: 'Listing to promote', type: 'select', options: listingOptions, required: true },
    { name: 'tier', label: 'Tier', type: 'select', options: tiers.length ? tiers : [['featured', 'Featured'], ['spotlight', 'Spotlight']], required: true },
    { name: 'headline', label: 'Headline shown beside “Sponsored”', wide: true },
    { name: 'starts_on', label: 'Starts', type: 'date', required: true },
    { name: 'ends_on', label: 'Ends', type: 'date', required: true },
  ];
  const initial = { starts_on: isoDay(0), ends_on: isoDay(30) };
  const liveCount = promotions.filter((promotion) => promotion.live).length;

  async function save(data, form) {
    setFormError('');
    const [listingType, ...slugParts] = String(data.listing || '').split(':');
    const payload = {
      listing_type: listingType,
      listing_slug: slugParts.join(':'),
      tier: data.tier,
      headline: data.headline,
      starts_on: data.starts_on,
      ends_on: data.ends_on,
    };
    const success = await onMutation('/api/admin/promotions', 'POST', payload, 'Promotion saved.');
    if (success) form.reset();
    else setFormError('The promotion could not be saved. Check the listing and dates.');
  }

  async function end(promotion) {
    const label = promotion.listing_name || promotion.listing_slug;
    if (!window.confirm(`End the promotion for ${label}?`)) return;
    setFormError('');
    const success = await onMutation(`/api/admin/promotions/${promotion.id}`, 'DELETE', undefined, 'Promotion ended.');
    if (!success) setFormError('This promotion could not be ended.');
  }

  return (
    <SectionCard
      title="Promotions"
      description={`Paid placements appear in the home page “Featured partners” rail and above organic results, always labelled Sponsored. Up to ${maxActive} can run at once; ${liveCount} live now.`}
    >
      {listingOptions.length === 0 ? (
        <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">Add a published tour or property before selling a placement.</p>
      ) : (
        <DataForm fields={fields} item={initial} submitLabel="Start or update promotion" onSubmit={save} />
      )}
      <Notice error>{formError}</Notice>
      <div className="mt-6 overflow-x-auto">
        {promotions.length === 0 ? (
          <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No promotions yet. Sponsored slots stay hidden until one is started.</p>
        ) : (
          <table className="w-full min-w-[46rem] text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-[#735744]">
              <tr>
                <th className="pb-2 pr-3 font-semibold">Listing</th>
                <th className="pb-2 pr-3 font-semibold">Window</th>
                <th className="pb-2 pr-3 font-semibold">Status</th>
                <th className="pb-2 pr-3 font-semibold">Views · clicks · CTR</th>
                <th className="pb-2 text-right font-semibold">Action</th>
              </tr>
            </thead>
            <tbody>
              {promotions.map((promotion) => (
                <tr className="border-t border-[#efede7] align-top" key={promotion.id}>
                  <td className="py-3 pr-3">
                    <strong className="block text-[#203b35]">{promotion.listing_name || promotion.listing_slug}</strong>
                    <span className="text-xs text-[#52615b]">{promotion.listing_type === 'tour' ? 'Experience' : 'Stay'} · {promotion.tier_label}</span>
                    {promotion.headline && <span className="block text-xs text-[#8a5a25]">“{promotion.headline}”</span>}
                  </td>
                  <td className="py-3 pr-3 text-[#52615b]">
                    {formatDate(promotion.starts_on)}<br />{formatDate(promotion.ends_on)}
                  </td>
                  <td className="py-3 pr-3">
                    {promotion.live
                      ? <span className="rounded-full bg-[#e6f2ea] px-2.5 py-1 text-xs font-semibold text-[#177b5b]">Live</span>
                      : <span className="rounded-full bg-[#efeee7] px-2.5 py-1 text-xs font-semibold text-[#52615b]">Scheduled or ended</span>}
                  </td>
                  <td className="py-3 pr-3 text-[#52615b]">{promotion.impressions} · {promotion.clicks} · {promotion.click_rate}%</td>
                  <td className="py-3 text-right">
                    <button className="text-sm font-semibold text-red-700 hover:underline" type="button" onClick={() => end(promotion)}>End</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </SectionCard>
  );
}

function NewsletterSection({ newsletter }) {
  const count = newsletter?.count || 0;
  const recent = newsletter?.recent || [];

  return (
    <SectionCard
      title="Newsletter"
      description="Addresses collected by the footer and home page signup forms. One row per email, so nobody is added twice."
    >
      <div className="flex flex-wrap items-baseline gap-3 rounded-xl bg-[#f5f3ed] p-4">
        <p className="display-font text-3xl text-[#203b35]">{count}</p>
        <p className="text-sm text-[#52615b]">active subscriber{count === 1 ? '' : 's'}</p>
      </div>
      {recent.length === 0 ? (
        <p className="mt-4 rounded-xl border border-dashed border-[#d9d3c4] p-4 text-sm text-[#52615b]">No signups yet. The form is shown in the footer and on the home page.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[30rem] text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-[#735744]">
              <tr>
                <th className="pb-2 pr-3 font-semibold">Email</th>
                <th className="pb-2 pr-3 font-semibold">Source</th>
                <th className="pb-2 font-semibold">Joined</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((item) => (
                <tr className="border-t border-[#efede7]" key={item.id}>
                  <td className="py-2.5 pr-3 text-[#203b35]">{item.email}</td>
                  <td className="py-2.5 pr-3 text-[#52615b]">{item.source}</td>
                  <td className="py-2.5 text-[#52615b]">{formatDate(item.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

function VendorProfileSection({ vendor, onMutation, csrfToken }) {
  async function save(event) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const data = Object.fromEntries(formData);
    data.business_types = formData.getAll('business_types');
    await onMutation('/api/vendor/profile', 'PUT', data, 'Business profile updated.');
  }

  return (
    <SectionCard title="Business profile" description="Tell travellers who you are. This is the operator page every tour and service you publish links back to.">
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={save}>
        <label className="block"><span className="field-label">Business name</span><input className="field" name="name" defaultValue={vendor.name} required /></label>
        <label className="block"><span className="field-label">Base location</span><input className="field" name="location" defaultValue={vendor.location} placeholder="Lamu, Maasai Mara, Nairobi…" /></label>
        <label className="block"><span className="field-label">Phone or WhatsApp</span><input className="field" name="phone" type="tel" defaultValue={vendor.phone} placeholder="+254 7xx xxx xxx" /></label>
        <label className="block"><span className="field-label">Website</span><input className="field" name="website" type="url" defaultValue={vendor.website} placeholder="https://" /></label>
        <fieldset className="sm:col-span-2">
          <legend className="field-label">What do you offer?</legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {businessTypeOptions.map(([value, label]) => (
              <label className="flex items-center gap-3 rounded-xl border border-[#e9e5db] p-3 text-sm text-[#203b35]" key={value}>
                <input name="business_types" type="checkbox" value={value} defaultChecked={(vendor.business_types || []).includes(value)} />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <label className="block sm:col-span-2"><span className="field-label">About your business</span><textarea className="field min-h-28 resize-y" name="description" defaultValue={vendor.description} placeholder="Your guides, camps, vehicles and the trips you love to run." /></label>
        <label className="block"><span className="field-label">Logo URL or images/ path</span><input className="field" name="logo_url" defaultValue={vendor.logo_url || ''} /></label>
        <PhotoUpload endpoint="/api/vendor/uploads" csrfToken={csrfToken} fieldName="logo_url" />
        <div className="flex flex-wrap items-center gap-4 sm:col-span-2">
          <button className="rounded-full bg-[#203b35] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#31554b]" type="submit">Save profile</button>
          {vendor.slug && <a className="text-sm font-semibold text-[#9a5534] hover:underline" href={`/operators/${vendor.slug}`} target="_blank" rel="noreferrer">View public operator page →</a>}
        </div>
      </form>
    </SectionCard>
  );
}

const roomFields = [
  { name: 'name', label: 'Room name', required: true },
  { name: 'guests', label: 'Sleeps (guests)', type: 'number', min: 1, required: true },
  { name: 'base_rate', label: 'Nightly rate (KSh)', type: 'number', min: 1, required: true },
  { name: 'total_units', label: 'Units of this room', type: 'number', min: 1, required: true },
  { name: 'image_url', label: 'Image URL or images/ path' },
  { name: 'description', label: 'Room description', type: 'textarea', wide: true },
];

function RoomAvailability({ basePath, propertyId, room, csrfToken }) {
  const endpoint = `${basePath}/${propertyId}/rooms/${room.id}/availability`;
  const [calendar, setCalendar] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const result = await apiRequest(endpoint);
      setCalendar(result.calendar);
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [endpoint]);

  async function applyRange(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    setError('');
    setMessage('');
    const payload = { from: data.from, to: data.to || data.from };
    if (data.rate) payload.rate = data.rate;
    if (data.units_available) payload.units_available = data.units_available;
    if (data.is_closed === 'on') payload.is_closed = true;
    if (!payload.rate && !payload.units_available && !payload.is_closed) {
      setError('Set a nightly rate, unit count or closure for the range.');
      return;
    }
    try {
      await apiRequest(endpoint, { method: 'PUT', data: payload, csrfToken });
      await load();
      form.reset();
      setMessage('Availability updated.');
    } catch (updateError) {
      setError(messageFrom(updateError));
    }
  }

  async function clearDay(day) {
    setError('');
    setMessage('');
    try {
      await apiRequest(`${endpoint}?date=${encodeURIComponent(day)}`, { method: 'DELETE', csrfToken });
      await load();
      setMessage('Override cleared.');
    } catch (clearError) {
      setError(messageFrom(clearError));
    }
  }

  const overrides = calendar.filter((day) => day.has_override || day.reserved > 0);

  return (
    <div className="space-y-4">
      <Notice error>{error}</Notice><Notice>{message}</Notice>
      <form className="grid gap-3 sm:grid-cols-[1fr_1fr_8rem_8rem_auto]" onSubmit={applyRange}>
        <label><span className="field-label">From</span><input className="field" type="date" name="from" required /></label>
        <label><span className="field-label">To</span><input className="field" type="date" name="to" required /></label>
        <label><span className="field-label">Nightly rate</span><input className="field" type="number" min="1" name="rate" placeholder={String(room.base_rate)} /></label>
        <label><span className="field-label">Units open</span><input className="field" type="number" min="1" name="units_available" placeholder={String(room.total_units)} /></label>
        <label className="flex items-end gap-2 pb-3 text-sm text-[#52615b]"><input type="checkbox" name="is_closed" />Closed</label>
        <button className="rounded-full bg-[#203b35] px-5 py-2.5 text-sm font-semibold text-white sm:col-span-5 sm:justify-self-start" type="submit">Apply to these dates</button>
      </form>
      {loading && <p className="text-sm text-[#52615b]" role="status">Loading availability…</p>}
      {!loading && overrides.length === 0 && <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No rate overrides or bookings in the next 60 days.</p>}
      {!loading && overrides.length > 0 && <div className="overflow-x-auto">
        <table className="w-full min-w-[38rem] border-collapse text-left text-sm">
          <thead><tr className="border-b border-[#e9e5db] text-[#52615b]">
            {['Night', 'Rate', 'Units', 'Booked', 'Remaining', 'Status', ''].map((label, index) => <th className="px-3 py-2 font-semibold" key={`${label}-${index}`}>{label}</th>)}
          </tr></thead>
          <tbody>{overrides.map((day) => (
            <tr className="border-b border-[#f0ede6] text-[#52615b]" key={day.date}>
              <td className="px-3 py-2">{day.date}</td>
              <td className="px-3 py-2">KSh {formatNumber(day.rate)}</td>
              <td className="px-3 py-2">{day.units}</td>
              <td className="px-3 py-2">{day.reserved}</td>
              <td className="px-3 py-2">{day.remaining}</td>
              <td className="px-3 py-2">{day.is_closed ? 'Closed' : day.has_override ? 'Overridden' : 'Base rate'}</td>
              <td className="px-3 py-2">{day.has_override ? <button className="text-sm font-semibold text-[#9a5534]" type="button" onClick={() => clearDay(day.date)}>Clear</button> : ''}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>}
    </div>
  );
}

function PropertyInventorySection({ properties, basePath, csrfToken }) {
  const [propertyId, setPropertyId] = useState('');
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [openRoomId, setOpenRoomId] = useState('');
  const uploadEndpoint = basePath.startsWith('/api/vendor') ? '/api/vendor/uploads' : '/api/admin/uploads';

  useEffect(() => {
    if (!propertyId && properties.length > 0) setPropertyId(String(properties[0].id));
  }, [properties, propertyId]);

  const roomsEndpoint = propertyId ? `${basePath}/${propertyId}/rooms` : '';

  async function load() {
    if (!roomsEndpoint) return;
    setLoading(true);
    setError('');
    try {
      const result = await apiRequest(roomsEndpoint);
      setRooms(result.rooms);
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setRooms([]);
    setOpenRoomId('');
    load();
  }, [roomsEndpoint]);

  async function createRoom(data, form) {
    setError('');
    setMessage('');
    try {
      await apiRequest(roomsEndpoint, { method: 'POST', data, csrfToken });
      form.reset();
      await load();
      setMessage('Room type added.');
    } catch (createError) {
      setError(messageFrom(createError));
    }
  }

  async function updateRoom(room, data) {
    setError('');
    setMessage('');
    try {
      await apiRequest(`${roomsEndpoint}/${room.id}`, { method: 'PUT', data, csrfToken });
      await load();
      setMessage('Room updated.');
    } catch (updateError) {
      setError(messageFrom(updateError));
    }
  }

  async function removeRoom(room) {
    if (!window.confirm(`Delete ${room.name}? This cannot be undone.`)) return;
    setError('');
    setMessage('');
    try {
      await apiRequest(`${roomsEndpoint}/${room.id}`, { method: 'DELETE', csrfToken });
      await load();
      setMessage('Room removed.');
    } catch (removeError) {
      setError(messageFrom(removeError));
    }
  }

  return (
    <SectionCard title="Room inventory and availability" description="Set your room types, nightly rates and how many units stay open each night. Nights are held while an M-Pesa payment is confirmed and released if it fails.">
      <Notice error>{error}</Notice><Notice>{message}</Notice>
      {properties.length === 0
        ? <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">Add an accommodation property first, then publish its rooms here.</p>
        : <label className="block max-w-md"><span className="field-label">Accommodation</span><select className="field" value={propertyId} onChange={(event) => setPropertyId(event.target.value)}>{properties.map((property) => <option value={property.id} key={property.id}>{property.name}</option>)}</select></label>}
      {propertyId && <div className="mt-6"><DataForm fields={roomFields} submitLabel="Add room type" onSubmit={createRoom}><PhotoUpload endpoint={uploadEndpoint} csrfToken={csrfToken} /></DataForm></div>}
      {loading && <p className="mt-5 text-sm text-[#52615b]" role="status">Loading rooms…</p>}
      {!loading && propertyId && rooms.length === 0 && <p className="mt-5 rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No rooms published for this accommodation yet.</p>}
      <div className="mt-5 space-y-4">
        {rooms.map((room) => (
          <article className="rounded-xl border border-[#e9e5db] p-4 sm:p-5" key={`${room.id}-${JSON.stringify(room)}`}>
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold text-[#203b35]">{room.name}</h3>
                <p className="mt-1 text-xs text-[#52615b]">Sleeps {room.guests} · {room.total_units} unit{room.total_units === 1 ? '' : 's'} · KSh {formatNumber(room.base_rate)} / night{room.is_active ? '' : ' · Paused'}</p>
              </div>
              <button className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35]" type="button" onClick={() => setOpenRoomId(openRoomId === String(room.id) ? '' : String(room.id))}>{openRoomId === String(room.id) ? 'Hide availability' : 'Manage availability'}</button>
            </div>
            <DataForm fields={roomFields} item={room} submitLabel="Save changes" onSubmit={(data) => updateRoom(room, data)}>
              <PhotoUpload endpoint={uploadEndpoint} csrfToken={csrfToken} />
              <button className="rounded-full border border-red-200 px-5 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-50" type="button" onClick={() => removeRoom(room)}>Delete</button>
            </DataForm>
            {openRoomId === String(room.id) && <div className="mt-5 border-t border-[#e9e5db] pt-5"><RoomAvailability basePath={basePath} propertyId={propertyId} room={room} csrfToken={csrfToken} /></div>}
          </article>
        ))}
      </div>
    </SectionCard>
  );
}

function VendorBookingsSection({ csrfToken }) {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const tourTransitions = {
    requested: ['confirmed', 'cancelled'],
    confirmed: ['in_preparation', 'cancelled'],
    in_preparation: ['completed', 'cancelled'],
    completed: [],
    cancelled: [],
  };
  const stayTransitions = {
    requested: ['cancelled'],
    confirmed: ['completed', 'cancelled'],
    completed: [],
    cancelled: [],
  };

  async function load() {
    setLoading(true);
    setError('');
    try {
      const result = await apiRequest('/api/vendor/bookings');
      setBookings(result.bookings);
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function updateStatus(booking, status) {
    if (status === 'cancelled' && !window.confirm(`Cancel booking #${booking.id}? Availability will be released.`)) return;
    setError('');
    setMessage('');
    try {
      const result = await apiRequest(`/api/vendor/bookings/${booking.id}/status`, {
        method: 'POST',
        data: { status },
        csrfToken,
      });
      await load();
      setMessage(result.email_sent ? `Booking #${booking.id} updated and customer emailed.` : `Booking #${booking.id} updated; customer email could not be delivered.`);
    } catch (updateError) {
      setError(messageFrom(updateError));
    }
  }

  return (
    <SectionCard title="Bookings" description="View reservations for your tours and accommodations, and progress them through the service workflow.">
      <Notice error>{error}</Notice><Notice>{message}</Notice>
      {loading && <p className="text-sm text-[#52615b]" role="status">Loading bookings…</p>}
      {!loading && bookings.length === 0 && <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No tour or accommodation bookings yet.</p>}
      <div className="space-y-4">
        {bookings.map((booking) => {
          const isStay = booking.booking_type === 'property';
          const transitions = isStay ? stayTransitions : tourTransitions;
          return (
            <article className="rounded-xl border border-[#e9e5db] p-4 sm:p-5" key={booking.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold capitalize text-[#203b35]">{booking.property_name || booking.tour_name}</h3>
                  {isStay
                    ? <p className="mt-1 text-sm text-[#52615b]">Booking #{booking.id} · {booking.room_name || 'Room'} · {booking.check_in} to {booking.check_out} · {booking.nights} night{booking.nights === 1 ? '' : 's'} · {booking.guests} guest{booking.guests === 1 ? '' : 's'}</p>
                    : <p className="mt-1 text-sm text-[#52615b]">Booking #{booking.id} · {booking.date} at {booking.time} · {booking.guests} guest{booking.guests === 1 ? '' : 's'}</p>}
                  <p className="mt-1 text-sm text-[#52615b]">{booking.name} · {booking.email} · {booking.phone}</p>
                </div>
                <span className="rounded-full bg-[#efeee7] px-3 py-1 text-sm font-semibold capitalize text-[#52615b]">{booking.status.replaceAll('_', ' ')}</span>
              </div>
              <p className="mt-2 text-xs text-[#52615b]">KSh {formatNumber(booking.amount)} · Payment: {booking.payment_status}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {(transitions[booking.status] || []).map((status) => (
                  <button className={`rounded-full px-4 py-2 text-sm font-semibold ${status === 'cancelled' ? 'border border-red-200 text-red-700' : 'bg-[#203b35] text-white hover:bg-[#31554b]'}`} key={status} type="button" onClick={() => updateStatus(booking, status)}>
                    Mark {status.replaceAll('_', ' ')}
                  </button>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </SectionCard>
  );
}

function AdminAccounts({ admins, vendors, onMutation }) {
  const [error, setError] = useState('');

  async function addAdmin(data, form) {
    const success = await onMutation('/api/admin/admins', 'POST', data, 'Admin account created.');
    if (success) form.reset();
    else setError('Admin account could not be created.');
  }

  async function deleteAdmin(admin) {
    if (!window.confirm(`Remove the admin account for ${admin.email}?`)) return;
    const success = await onMutation(`/api/admin/admins/${admin.id}`, 'DELETE', undefined, 'Admin account removed.');
    if (!success) setError('Admin account could not be removed.');
  }

  async function deleteVendor(vendor) {
    if (!window.confirm(`Remove ${vendor.name} and all of their tours, services and properties?`)) return;
    const success = await onMutation(`/api/admin/vendors/${vendor.id}`, 'DELETE', undefined, 'Partner account and listings removed.');
    if (!success) setError('Partner account could not be removed.');
  }

  return (
    <SectionCard title="Accounts" description="Manage staff access and self-registered partner accounts.">
      <h3 className="mb-3 font-semibold text-[#203b35]">Create an admin account</h3>
      <DataForm
        fields={[
          { name: 'name', label: 'Name', required: true },
          { name: 'email', label: 'Email', type: 'email', required: true },
          { name: 'password', label: 'Password (at least 12 characters)', type: 'password', minLength: 12, required: true },
        ]}
        submitLabel="Create admin"
        onSubmit={addAdmin}
      />
      <Notice error>{error}</Notice>
      <div className="mt-7 grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-3 font-semibold text-[#203b35]">Admin accounts</h3>
          <div className="space-y-3">
            {admins.map((admin) => (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#f5f3ed] p-4" key={admin.id}>
                <span className="text-sm text-[#52615b]">{admin.name} · {admin.email}</span>
                <button className="action-danger text-sm" type="button" onClick={() => deleteAdmin(admin)}>Remove</button>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h3 className="mb-3 font-semibold text-[#203b35]">Partner accounts</h3>
          <div className="space-y-3">
            {vendors.length === 0 && <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No partners have registered yet.</p>}
            {vendors.map((vendor) => (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#f5f3ed] p-4" key={vendor.id}>
                <span className="text-sm text-[#52615b]">
                  <strong className="block text-[#203b35]">{vendor.name}</strong>
                  {vendor.email}<span className="mt-1 block text-xs">{vendor.tour_count} tours · {vendor.service_count} services · {vendor.property_count} properties</span>
                </span>
                <button className="action-danger text-sm" type="button" onClick={() => deleteVendor(vendor)}>Remove partner</button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

function usePortalData(path) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setData(await apiRequest(path));
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [path]);

  async function mutate(url, method, payload, successMessage) {
    if (!data?.csrf_token) {
      setError('Your session has expired. Sign in again to continue.');
      return false;
    }
    setError('');
    setMessage('');
    try {
      await apiRequest(url, { method, data: payload, csrfToken: data.csrf_token });
      setMessage(successMessage);
      await load();
      return true;
    } catch (mutationError) {
      setError(messageFrom(mutationError));
      return false;
    }
  }

  return { data, loading, error, message, load, mutate };
}

function makeSignOut({ endpoint, csrfToken, redirectTo, onError }) {
  async function signOut() {
    try {
      await apiRequest(endpoint, { method: 'POST', csrfToken });
      window.location.assign(redirectTo);
    } catch (error) {
      onError(messageFrom(error));
    }
  }
  return signOut;
}

function DashboardLayout({ role, actor, signOut, children }) {
  return (
    <div className="min-h-screen bg-[#f8f7f2]">
      <PortalHeader role={role} actor={actor} onSignOut={signOut} />
      <main className="mx-auto max-w-7xl space-y-6 px-5 py-8 sm:px-8 sm:py-10">{children}</main>
    </div>
  );
}

function DashboardStatus({ error, message }) {
  return <><Notice error>{error}</Notice><Notice>{message}</Notice></>;
}

function AvailabilitySection({ tours, endpoint, csrfToken }) {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const result = await apiRequest(endpoint);
      setSchedules(result.schedules);
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [endpoint]);

  async function save(event) {
    event.preventDefault();
    const form = event.currentTarget;
    setError('');
    setMessage('');
    const data = Object.fromEntries(new FormData(form));
    try {
      await apiRequest(endpoint, { method: 'POST', data, csrfToken });
      form.reset();
      await load();
      setMessage('Departure published.');
    } catch (saveError) {
      setError(messageFrom(saveError));
    }
  }

  async function remove(schedule) {
    if (!window.confirm('Remove this departure?')) return;
    setError('');
    try {
      await apiRequest(`${endpoint}/${schedule.id}`, { method: 'DELETE', csrfToken });
      await load();
      setMessage('Departure removed.');
    } catch (removeError) {
      setError(messageFrom(removeError));
    }
  }

  async function update(schedule, event) {
    event.preventDefault();
    const form = event.currentTarget;
    setError('');
    setMessage('');
    try {
      await apiRequest(`${endpoint}/${schedule.id}`, {
        method: 'PUT',
        data: Object.fromEntries(new FormData(form)),
        csrfToken,
      });
      await load();
      setMessage('Departure updated.');
    } catch (updateError) {
      setError(messageFrom(updateError));
    }
  }

  return (
    <SectionCard title="Tour availability" description="Publish departure dates and times with a guest capacity. Only future departures with remaining spaces can be booked.">
      <Notice error>{error}</Notice><Notice>{message}</Notice>
      <form className="grid gap-4 sm:grid-cols-3" onSubmit={save}>
        <label><span className="field-label">Tour</span><select className="field" name="tour_slug" required defaultValue=""><option value="" disabled>Choose a tour</option>{tours.map((tour) => <option value={tour.slug} key={tour.slug}>{tour.name}</option>)}</select></label>
        <label><span className="field-label">Departure date and time (Kenya time)</span><input className="field" type="datetime-local" name="starts_at" required /></label>
        <label><span className="field-label">Guest capacity</span><input className="field" type="number" min="1" name="capacity" required /></label>
        <button className="rounded-full bg-[#203b35] px-5 py-2.5 text-sm font-semibold text-white sm:col-span-3 sm:justify-self-start" type="submit" disabled={!tours.length}>Add departure</button>
      </form>
      {loading && <p className="mt-5 text-sm text-[#52615b]" role="status">Loading departures…</p>}
      {!loading && schedules.length === 0 && <p className="mt-5 rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No departures published yet.</p>}
      <div className="mt-5 space-y-3">
        {schedules.map((schedule) => (
          <div className="rounded-xl border border-[#e9e5db] p-4" key={schedule.id}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div><p className="font-semibold text-[#203b35]">{tours.find((tour) => tour.slug === schedule.tour_slug)?.name || schedule.tour_slug}</p><p className="mt-1 text-sm text-[#52615b]">{schedule.booked_count}/{schedule.capacity} guests booked</p></div>
              <button className="action-danger text-sm" type="button" onClick={() => remove(schedule)}>Remove</button>
            </div>
            <form className="grid gap-3 sm:grid-cols-[1fr_10rem_auto]" onSubmit={(event) => update(schedule, event)}>
              <label><span className="field-label">Departure (Kenya time)</span><input className="field" type="datetime-local" name="starts_at" defaultValue={schedule.starts_at} required /></label>
              <label><span className="field-label">Capacity</span><input className="field" type="number" name="capacity" min={schedule.booked_count} defaultValue={schedule.capacity} required /></label>
              <button className="self-end rounded-full border border-[#203b35] px-4 py-3 text-sm font-semibold text-[#203b35]" type="submit">Update</button>
            </form>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function DashboardLoadError({ role, error, onRetry }) {
  const loginUrl = role.toLowerCase() === 'admin' ? '/admin/login' : '/partner/login';
  return (
    <div className="min-h-screen bg-[#f8f7f2]">
      <PortalHeader role={role} actor="Dashboard unavailable" />
      <main className="mx-auto max-w-3xl px-5 py-12 sm:px-8">
        <div className="rounded-2xl border border-red-200 bg-white p-6">
          <Notice error>{error}</Notice>
          <div className="mt-5 flex gap-4">
            <button className="action-button" type="button" onClick={onRetry}>Try again</button>
            <a className="font-semibold text-[#9a5534] underline" href={loginUrl}>Sign in</a>
          </div>
        </div>
      </main>
    </div>
  );
}

function displayTimestamp(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(numberLocale());
}

function AdminUserManagement({ customers, vendors, onMutation }) {
  const accounts = [
    ...customers.map((user) => ({ ...user, role: 'customer' })),
    ...vendors.map((user) => ({ ...user, role: 'vendor' })),
  ];

  return (
    <SectionCard title="User management" description="Review customer and operator accounts, and suspend or restore access without deleting booking history.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-left text-sm">
          <thead><tr className="border-b border-[#e9e5db] text-[#52615b]">{['Name', 'Email', 'Role', 'Bookings', 'Access'].map((label) => <th className="px-3 py-3 font-semibold" key={label}>{label}</th>)}</tr></thead>
          <tbody>{accounts.map((account) => (
            <tr className="border-b border-[#f0ede6] text-[#52615b]" key={`${account.role}-${account.id}`}>
              <td className="px-3 py-3">{account.name}</td>
              <td className="px-3 py-3">{account.email}</td>
              <td className="px-3 py-3">{account.role === 'vendor' ? 'Partner' : 'Customer'}</td>
              <td className="px-3 py-3">{account.booking_count ?? '—'}</td>
              <td className="px-3 py-3">
                <button
                  className={`font-semibold hover:underline ${account.is_active ? 'text-red-700' : 'text-[#26734d]'}`}
                  type="button"
                  onClick={() => onMutation(
                    `/api/admin/users/${account.role}/${account.id}/status`,
                    'POST',
                    { active: !account.is_active },
                    `${account.role === 'vendor' ? 'Partner' : 'Customer'} access ${account.is_active ? 'suspended' : 'restored'}.`,
                  )}
                >
                  {account.is_active ? 'Suspend access' : 'Restore access'}
                </button>
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {accounts.length === 0 && <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No customer or partner accounts yet.</p>}
    </SectionCard>
  );
}

function AdminBookingCard({ booking, onMutation }) {
  const [reason, setReason] = useState('');
  const refundAmount = formatNumber(booking.refund_amount || booking.amount || 0);
  const refundLabel = {
    none: 'No refund',
    pending: 'Refund due',
    paid: 'Refund paid',
    rejected: 'Refund declined',
  }[booking.refund_status] || booking.refund_status;

  async function openDispute(event) {
    event.preventDefault();
    const success = await onMutation(
      `/api/admin/bookings/${booking.id}/disputes`,
      'POST',
      { reason },
      `Dispute opened for booking #${booking.id}.`,
    );
    if (success) setReason('');
  }

  async function updateRefund(status, confirmMessage) {
    if (confirmMessage && !window.confirm(confirmMessage)) return;
    await onMutation(
      `/api/admin/bookings/${booking.id}/refund`,
      'POST',
      { status },
      `Refund for booking #${booking.id} updated.`,
    );
  }

  return (
    <article className="rounded-xl border border-[#e9e5db] p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-[#203b35]">#{booking.id} · {booking.tour_name}</h3>
          <p className="mt-1 text-sm text-[#52615b]">{booking.name} · {booking.email} · {booking.phone}</p>
          <p className="mt-1 text-sm text-[#52615b]">{booking.booking_type === 'property' ? `${booking.room_name || 'Room'} · ${booking.check_in} to ${booking.check_out} · ${booking.nights} night${booking.nights === 1 ? '' : 's'}` : `${booking.date} at ${booking.time}`} · {booking.guests} guest{booking.guests === 1 ? '' : 's'}</p>
        </div>
        <span className="rounded-full bg-[#efeee7] px-3 py-1 text-sm font-semibold capitalize text-[#52615b]">{booking.status.replaceAll('_', ' ')}</span>
      </div>
      <p className="mt-3 text-sm text-[#52615b]">KSh {formatNumber(booking.amount)} · Payment: {booking.payment_status} · Refund: {refundLabel}{booking.refund_status !== 'none' ? ` (KSh ${refundAmount})` : ''}</p>
      {booking.refund_status !== 'none' && (booking.refund_reason || booking.refund_requested_at) && <p className="mt-1 text-xs text-[#52615b]">
        {booking.refund_reason}
        {booking.refund_requested_at ? ` · requested ${formatDate(booking.refund_requested_at)}` : ''}
        {booking.refund_paid_at ? ` · sent ${formatDate(booking.refund_paid_at)}` : ''}
      </p>}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {['requested', 'confirmed', 'in_preparation'].includes(booking.status) && (
          <button
            className="rounded-full border border-red-200 px-4 py-2 text-sm font-semibold text-red-700"
            type="button"
            onClick={() => {
              if (window.confirm(`Cancel booking #${booking.id}? Reserved availability will be released.`)) {
                onMutation(`/api/admin/bookings/${booking.id}/cancel`, 'POST', {}, `Booking #${booking.id} cancelled.`);
              }
            }}
          >Cancel booking</button>
        )}
        {booking.payment_status === 'paid' && booking.refund_status === 'none' && (
          <button
            className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35]"
            type="button"
            onClick={() => updateRefund('pending')}
          >Start refund</button>
        )}
        {booking.payment_status === 'paid' && booking.refund_status === 'pending' && (<>
          <button
            className="rounded-full bg-[#203b35] px-4 py-2 text-sm font-semibold text-white"
            type="button"
            onClick={() => updateRefund(
              'paid',
              `Confirm the KSh ${refundAmount} refund for booking #${booking.id} was sent to the customer?`,
            )}
          >Mark refund paid</button>
          <button
            className="rounded-full border border-red-200 px-4 py-2 text-sm font-semibold text-red-700"
            type="button"
            onClick={() => updateRefund('rejected')}
          >Reject refund</button>
        </>)}
        {booking.payment_status === 'paid' && booking.refund_status === 'rejected' && (
          <button
            className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35]"
            type="button"
            onClick={() => updateRefund('pending')}
          >Reopen refund</button>
        )}
      </div>
      <form className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto]" onSubmit={openDispute}>
        <label><span className="field-label">Open dispute / internal case</span><textarea className="field min-h-20" value={reason} onChange={(event) => setReason(event.target.value)} minLength={10} maxLength={3000} placeholder="Summarize the customer or partner concern…" required /></label>
        <button className="self-end rounded-full border border-[#203b35] px-4 py-3 text-sm font-semibold text-[#203b35]" type="submit">Open case</button>
      </form>
    </article>
  );
}

function AdminDisputes({ disputes, onMutation }) {
  const [resolutions, setResolutions] = useState({});
  return (
    <SectionCard title="Dispute handling" description="Create internal cases from a booking and record the resolution for the audit trail.">
      {disputes.length === 0 && <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No dispute cases have been recorded.</p>}
      <div className="space-y-3">
        {disputes.map((dispute) => (
          <article className="rounded-xl border border-[#e9e5db] p-4" key={dispute.id}>
            <div className="flex flex-wrap justify-between gap-2">
              <h3 className="font-semibold text-[#203b35]">Case #{dispute.id} · Booking #{dispute.booking_id} · {dispute.tour}</h3>
              <span className="text-sm font-semibold capitalize text-[#52615b]">{dispute.status}</span>
            </div>
            <p className="mt-2 text-sm text-[#52615b]">{dispute.booking_name} · {dispute.booking_email}</p>
            <p className="mt-2 whitespace-pre-wrap text-sm text-[#52615b]">{dispute.reason}</p>
            {dispute.status === 'open'
              ? <form className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto]" onSubmit={async (event) => {
                event.preventDefault();
                const resolution = resolutions[dispute.id] || '';
                const success = await onMutation(`/api/admin/disputes/${dispute.id}`, 'PUT', { resolution }, `Dispute #${dispute.id} resolved.`);
                if (success) setResolutions((current) => ({ ...current, [dispute.id]: '' }));
              }}>
                <label><span className="field-label">Resolution</span><textarea className="field min-h-20" minLength={10} maxLength={3000} required value={resolutions[dispute.id] || ''} onChange={(event) => setResolutions((current) => ({ ...current, [dispute.id]: event.target.value }))} /></label>
                <button className="self-end rounded-full bg-[#203b35] px-4 py-3 text-sm font-semibold text-white" type="submit">Resolve case</button>
              </form>
              : <p className="mt-3 whitespace-pre-wrap text-sm text-[#52615b]"><strong>Resolution:</strong> {dispute.resolution}</p>}
          </article>
        ))}
      </div>
    </SectionCard>
  );
}

function AnalyticsBar({ label, value, max }) {
  const numericValue = Number(value) || 0;
  const numericMax = Math.max(Number(max) || 0, 1);
  const width = Math.max(0, Math.min(100, numericValue / numericMax * 100));

  return (
    <div
      className="h-2 overflow-hidden rounded-full bg-[#efeee7]"
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={numericMax}
      aria-valuenow={numericValue}
    >
      <div className="h-full rounded-full bg-[#b96e45]" style={{ width: `${width}%` }} />
    </div>
  );
}

const PRICE_POSITION_LABELS = {
  below: 'Below average',
  above: 'Above average',
  typical: 'Around average',
  unknown: 'No price published',
};

function PriceInsights({ insights }) {
  const [filter, setFilter] = useState('all');
  if (!insights) return null;
  const rows = insights.listings.filter((row) => filter === 'all' || row.kind === filter);
  const summary = [
    ['Tours · median', `KSh ${formatNumber(insights.tours.median_price)}`],
    ['Stays · median', `KSh ${formatNumber(insights.stays.median_price)}`],
    ['Below area average', `${formatNumber(insights.tours.below_market + insights.stays.below_market)} listings`],
  ];

  return (
    <section className="mt-8 border-t border-[#e9e5db] pt-5" aria-labelledby="price-visibility-title">
      <h3 id="price-visibility-title" className="font-semibold text-[#203b35]">Price visibility</h3>
      <p className="mt-1 text-xs text-[#52615b]">Starting prices compared with comparable listings. Listings with no published rate are flagged so the team can complete them.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {summary.map(([label, value]) => (
          <div className="rounded-xl bg-[#f5f3ed] p-4" key={label}>
            <p className="text-xs text-[#52615b]">{label}</p>
            <p className="mt-1 font-semibold text-[#203b35]">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Filter price rows by listing type">
        {[['all', 'All listings'], ['tour', 'Tours'], ['stay', 'Stays']].map(([value, label]) => (
          <button
            aria-pressed={filter === value}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold ${filter === value ? 'bg-[#203b35] text-white' : 'border border-[#d9d7cd] text-[#52615b] hover:border-[#203b35]'}`}
            key={value}
            onClick={() => setFilter(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="border-b border-[#e9e5db] text-xs text-[#52615b]">
            <tr>
              <th className="py-2 font-medium">Listing</th>
              <th className="py-2 text-right font-medium">Starting price</th>
              <th className="py-2 text-right font-medium">vs market</th>
              <th className="py-2 text-right font-medium">Bookings</th>
              <th className="py-2 text-right font-medium">Paid revenue</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr className="border-b border-[#f0ede6]" key={`${row.kind}-${row.slug}`}>
                <th scope="row" className="py-2.5 font-medium text-[#203b35]">
                  {row.name}
                  <span className="ml-2 text-xs font-normal text-[#52615b]">{row.kind === 'stay' ? 'Stay' : 'Tour'}</span>
                </th>
                <td className="py-2.5 text-right tabular-nums">
                  {row.price_from > 0 ? `KSh ${formatNumber(row.price_from)}` : 'No price published'}
                </td>
                <td className="py-2.5 text-right">
                  <span className={row.position === 'below' ? 'text-[#177b5b]' : row.position === 'above' ? 'text-[#a75f3a]' : 'text-[#52615b]'}>
                    {PRICE_POSITION_LABELS[row.position] || PRICE_POSITION_LABELS.unknown}
                  </span>
                  {row.difference_percent ? <span className="ml-1 text-xs tabular-nums text-[#52615b]">{Math.abs(row.difference_percent)}%</span> : null}
                </td>
                <td className="py-2.5 text-right tabular-nums">{formatNumber(row.paid_bookings)}</td>
                <td className="py-2.5 text-right tabular-nums">KSh {formatNumber(row.paid_revenue)}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td className="py-4 text-sm text-[#52615b]" colSpan="5">No listings match this filter.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AnalyticsVisuals({ analytics }) {
  const visitorMax = analytics.funnel[0]?.count || 0;
  const revenueMax = Math.max(...analytics.property_revenue.map((row) => row.paid_revenue), 0);
  const locale = numberLocale();

  return (
    <div className="mt-7 grid gap-x-8 gap-y-8 lg:grid-cols-2">
      <section className="border-t border-[#e9e5db] pt-5" aria-labelledby="conversion-funnel-title">
        <h3 id="conversion-funnel-title" className="font-semibold text-[#203b35]">Conversion funnel</h3>
        <p className="mt-1 text-xs text-[#52615b]">Last {analytics.period_days} days · unique browser sessions</p>
        <div className="mt-4 space-y-3">
          {analytics.funnel.map((stage, index) => (
            <div key={stage.label}>
              <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                <span className="text-[#52615b]">{stage.label}</span>
                <span className="font-semibold tabular-nums text-[#203b35]">
                  {formatNumber(stage.count)} <span className="font-normal text-[#52615b]">{index ? `${stage.conversion_rate}%` : ''}</span>
                </span>
              </div>
              <AnalyticsBar label={`${stage.label}: ${stage.count}`} value={stage.count} max={visitorMax} />
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-[#e9e5db] pt-5" aria-labelledby="traffic-sources-title">
        <h3 id="traffic-sources-title" className="font-semibold text-[#203b35]">Traffic sources</h3>
        <p className="mt-1 text-xs text-[#52615b]">First-touch attribution · last {analytics.period_days} days</p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[30rem] text-left text-sm">
            <thead className="border-b border-[#e9e5db] text-xs text-[#52615b]">
              <tr><th className="py-2 font-medium">Source</th><th className="py-2 text-right font-medium">Visitors</th><th className="py-2 text-right font-medium">Bookings</th><th className="py-2 text-right font-medium">Paid</th></tr>
            </thead>
            <tbody>
              {analytics.traffic_sources.map((source) => (
                <tr className="border-b border-[#f0ede6]" key={source.source}>
                  <th scope="row" className="py-2.5 font-medium text-[#203b35]">{source.source}<span className="ml-2 text-xs font-normal text-[#52615b]">{source.conversion_rate}%</span></th>
                  <td className="py-2.5 text-right tabular-nums">{formatNumber(source.visitors)}</td>
                  <td className="py-2.5 text-right tabular-nums">{formatNumber(source.booking_requests)}</td>
                  <td className="py-2.5 text-right tabular-nums">KSh {formatNumber(source.paid_revenue)}</td>
                </tr>
              ))}
              {analytics.traffic_sources.length === 0 && <tr><td className="py-4 text-sm text-[#52615b]" colSpan="4">Traffic data will appear as visitors use the site.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border-t border-[#e9e5db] pt-5" aria-labelledby="occupancy-trends-title">
        <h3 id="occupancy-trends-title" className="font-semibold text-[#203b35]">Departure occupancy trends</h3>
        <p className="mt-1 text-xs text-[#52615b]">Booked seats ÷ published tour capacity · six months before and ahead</p>
        <div className="mt-4 grid grid-cols-6 gap-x-2 gap-y-4 sm:grid-cols-12">
          {analytics.occupancy_trends.map((month) => (
            <div className="min-w-0 text-center" key={month.month}>
              <p className="mb-1 text-xs font-semibold tabular-nums text-[#203b35]">{month.occupancy_rate}%</p>
              <div className="flex h-20 items-end overflow-hidden rounded-t bg-[#efeee7]" role="meter" aria-label={`${month.month} tour departure occupancy`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={month.occupancy_rate}>
                <div className="w-full bg-[#177b5b]" style={{ height: `${month.occupancy_rate}%` }} />
              </div>
              <p className="mt-1 truncate text-[10px] text-[#52615b]">{new Date(`${month.month}-01T12:00:00`).toLocaleDateString(locale, { month: 'short' })}</p>
              <p className="text-[10px] tabular-nums text-[#52615b]">{month.booked_seats}/{month.capacity}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-[#e9e5db] pt-5" aria-labelledby="property-revenue-title">
        <h3 id="property-revenue-title" className="font-semibold text-[#203b35]">Paid revenue by property</h3>
        <p className="mt-1 text-xs text-[#52615b]">All-time verified property bookings</p>
        <div className="mt-4 space-y-3">
          {analytics.property_revenue.map((property) => (
            <div key={property.slug}>
              <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate font-medium text-[#203b35]">{property.name}</span>
                <span className="shrink-0 text-right tabular-nums text-[#52615b]">KSh {formatNumber(property.paid_revenue)}</span>
              </div>
              <AnalyticsBar label={`${property.name}: KSh ${formatNumber(property.paid_revenue)}`} value={property.paid_revenue} max={revenueMax} />
              <p className="mt-1 text-xs text-[#52615b]">{formatNumber(property.paid_bookings)} paid booking{property.paid_bookings === 1 ? '' : 's'}</p>
            </div>
          ))}
          {analytics.property_revenue.length === 0 && <p className="text-sm text-[#52615b]">Property revenue will appear after a verified property booking.</p>}
        </div>
      </section>
    </div>
  );
}

function AdminOperationsSection() {
  const { data, loading, error, message, load, mutate } = usePortalData('/api/admin/operations');
  const [settingsError, setSettingsError] = useState('');

  async function updateSettings(event) {
    event.preventDefault();
    setSettingsError('');
    const form = new FormData(event.currentTarget);
    const success = await mutate('/api/admin/settings', 'PUT', {
      commission_rate: Number(form.get('commission_rate')),
      refund_policy: 'automatic',
    }, 'Admin settings saved.');
    if (!success) setSettingsError('Settings could not be saved.');
  }

  return (
    <>
      <SectionCard title="Commission & refund rules" description="Commission is captured on new bookings. Cancelling a paid booking at least 48 hours ahead refunds it in full; your team sends the money and marks it paid here.">
        <DashboardStatus error={error} message={message} />
        <Notice error>{settingsError}</Notice>
        {loading && !data && <p className="text-sm text-[#52615b]" role="status">Loading admin operations…</p>}
        {data && <form className="grid gap-4 sm:grid-cols-[12rem_1fr_auto] sm:items-end" onSubmit={updateSettings}>
          <label><span className="field-label">Commission rate (%)</span><input className="field" type="number" name="commission_rate" min="10" max="20" step="0.1" defaultValue={data.settings.commission_rate} required /></label>
          <div className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">
            <strong className="block text-[#203b35]">Cancellation & refund policy</strong>
            Customer cancellation cutoff: {data.settings.cancellation_window_hours} hours before departure. Cancellations inside the cutoff are blocked. Full refunds are queued automatically for your team to send and mark as paid.
          </div>
          <button className="rounded-full bg-[#203b35] px-5 py-3 text-sm font-semibold text-white" type="submit">Save settings</button>
        </form>}
        {!loading && !data && <button className="action-button" type="button" onClick={load}>Retry loading settings</button>}
      </SectionCard>
      {data && <AdminUserManagement customers={data.customers} vendors={data.vendors} onMutation={mutate} />}
      {data && <SectionCard title="Bookings oversight" description={`${data.bookings_truncated ? 'Showing the latest 200 bookings. ' : ''}Review bookings, cancel active reservations, send refunds, and open dispute cases.`}>
        <div className="mb-4 rounded-xl bg-[#fdf6ef] p-4 text-sm text-[#52615b]" role="status">
          <strong className="block text-[#203b35]">Refunds to pay</strong>
          {data.refunds_due.count === 0
            ? 'No refunds are waiting to be sent.'
            : `${data.refunds_due.count} refund${data.refunds_due.count === 1 ? '' : 's'} · KSh ${formatNumber(data.refunds_due.amount)} waiting to be sent to customers.`}
        </div>
        <div className="space-y-4">
          {data.bookings.length === 0 && <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">No bookings have been received.</p>}
          {data.bookings.map((booking) => <AdminBookingCard booking={booking} onMutation={mutate} key={booking.id} />)}
        </div>
      </SectionCard>}
      {data && <AdminDisputes disputes={data.disputes} onMutation={mutate} />}
      {data && <SectionCard title="Booking & revenue analytics" description="Conversion and traffic cover the last 30 days. Occupancy uses tour departure capacity; property revenue includes verified payments only.">
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            ['All bookings', data.analytics.total_bookings],
            ['Paid revenue', `KSh ${formatNumber(data.analytics.paid_revenue)}`],
            ['Commission earned', `KSh ${formatNumber(data.analytics.commission_earned)}`],
          ].map(([label, value]) => <div className="rounded-xl bg-[#f5f3ed] p-4" key={label}><p className="text-sm text-[#52615b]">{label}</p><p className="display-font mt-2 text-2xl text-[#203b35]">{value}</p></div>)}
        </div>
        <div className="mt-5 space-y-3">
          {data.analytics.by_tour.map((tour) => <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#f0ede6] py-3 text-sm" key={tour.tour}>
            <div><p className="font-semibold text-[#203b35]">{tour.tour_name}</p><p className="text-[#52615b]">{tour.bookings} booking{tour.bookings === 1 ? '' : 's'}</p></div>
            <div className="text-right text-[#52615b]"><p>KSh {formatNumber(tour.paid_revenue)} paid</p><p>KSh {formatNumber(tour.commission_earned)} commission</p></div>
          </div>)}
          {data.analytics.by_tour.length === 0 && <p className="text-sm text-[#52615b]">Analytics will appear when bookings are received.</p>}
        </div>
        <AnalyticsVisuals analytics={data.analytics} />
        <PriceInsights insights={data.analytics.price_insights} />
      </SectionCard>}
    </>
  );
}

function ActivityTable({ title, columns, rows, emptyMessage }) {
  return (
    <SectionCard title={title}>
      {rows.length === 0
        ? <p className="rounded-xl bg-[#f5f3ed] p-4 text-sm text-[#52615b]">{emptyMessage}</p>
        : <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead><tr className="border-b border-[#e9e5db] text-[#52615b]">{columns.map(([label]) => <th className="px-3 py-3 font-semibold" key={label}>{label}</th>)}</tr></thead>
            <tbody>{rows.map((row) => (
              <tr className="border-b border-[#f0ede6] align-top text-[#52615b]" key={row.id}>
                {columns.map(([label, render]) => <td className="px-3 py-3" key={label}>{render(row)}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>}
    </SectionCard>
  );
}

export function AdminActivityDashboardPage() {
  const { data, loading, error, load } = usePortalData('/api/admin/dashboard');
  const [signOutError, setSignOutError] = useState('');
  const signOut = makeSignOut({
    endpoint: '/admin/logout',
    csrfToken: data?.csrf_token,
    redirectTo: '/admin/login',
    onError: setSignOutError,
  });

  if (loading && !data) return <div className="min-h-screen bg-[#f8f7f2]"><PortalHeader role="Admin" actor="Loading your dashboard…" /><main className="mx-auto max-w-7xl px-5 py-10 text-[#52615b]">Loading bookings and messages…</main></div>;
  if (error && !data) return <DashboardLoadError role="Admin" error={error} onRetry={load} />;

  return (
    <DashboardLayout role="Admin" actor="Bookings and messages" signOut={signOut}>
      <DashboardStatus error={error || signOutError} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[#52615b]">A clear view of the latest guest enquiries and tour booking activity across Kenya.</p>
        <a className="font-semibold text-[#9a5534] hover:underline" href="/admin">Catalog and accounts →</a>
      </div>
      {data && <div className="grid gap-4 sm:grid-cols-2">
        {[
          ['Total contact messages', data.total_submissions],
          ['Total booking requests', data.total_bookings],
          ['Recent messages shown', data.recent_submissions.length],
          ['Recent bookings shown', data.recent_bookings.length],
        ].map(([label, count]) => <div className="rounded-2xl border border-[#e9e5db] bg-white p-5" key={label}><p className="text-sm text-[#52615b]">{label}</p><p className="display-font mt-2 text-3xl text-[#203b35]">{count}</p></div>)}
      </div>}
      {data && <ActivityTable
        title="Latest contact submissions"
        rows={data.recent_submissions}
        emptyMessage="No submissions have been received yet."
        columns={[
          ['#', (item) => item.id],
          ['Name', (item) => item.name],
          ['Email', (item) => item.email],
          ['Subject', (item) => item.subject],
          ['Received', (item) => displayTimestamp(item.timestamp)],
          ['Email sent', (item) => item.email_sent ? 'Yes' : 'No'],
        ]}
      />}
      {data && <ActivityTable
        title="Latest booking requests"
        rows={data.recent_bookings}
        emptyMessage="No booking requests have been received yet."
        columns={[
          ['#', (item) => item.id],
          ['Name', (item) => item.name],
          ['Email', (item) => item.email],
          ['Phone', (item) => item.phone],
          ['Tour', (item) => item.tour],
          ['Date', (item) => item.date],
          ['Time', (item) => item.time],
          ['Guests', (item) => item.guests],
        ]}
      />}
    </DashboardLayout>
  );
}

export function AdminDashboardPage() {
  const { data, loading, error, message, load, mutate } = usePortalData('/api/admin/catalogue');
  const [signOutError, setSignOutError] = useState('');
  const signOut = makeSignOut({
    endpoint: '/admin/logout',
    csrfToken: data?.csrf_token,
    redirectTo: '/admin/login',
    onError: setSignOutError,
  });

  if (loading && !data) return <div className="min-h-screen bg-[#f8f7f2]"><PortalHeader role="Admin" actor="Loading your dashboard…" /><main className="mx-auto max-w-7xl px-5 py-10 text-[#52615b]">Loading catalogue…</main></div>;
  if (error && !data) return <DashboardLoadError role="Admin" error={error} onRetry={load} />;

  const partnerName = (item) => data.vendors.find((vendor) => vendor.id === item.vendor_id)?.name || 'Partner';
  const vendorOwner = (item) => item.vendor_id
    ? `Partner listing · ${partnerName(item)}`
    : 'Managed by Kenya Tours';
  const hostOwner = (item) => item.vendor_id
    ? `Host · ${partnerName(item)}`
    : 'Managed by Kenya Tours';
  const serviceOwner = (item) => item.vendor_name ? `Partner listing · ${item.vendor_name}` : 'Managed by Kenya Tours';

  return (
    <DashboardLayout role="Admin" actor="Catalog management" signOut={signOut}>
      <DashboardStatus error={error || signOutError} message={message} />
      <p className="text-sm text-[#52615b]">Shape the experiences guests discover, support local operators, and keep an eye on how the marketplace is growing.</p>
      <AdminOperationsSection />
      {data && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ['Tours & safaris', data.tours.length],
          ['Properties', data.properties.length],
          ['Services', data.services.length],
          ['Partners', data.vendors.length],
        ].map(([label, count]) => <div className="rounded-2xl border border-[#e9e5db] bg-white p-5" key={label}><p className="text-sm text-[#52615b]">{label}</p><p className="display-font mt-2 text-3xl text-[#203b35]">{count}</p></div>)}
      </div>}
      {data && <PromotionSection promotions={data.promotions} tours={data.tours} properties={data.properties} tiers={data.promotion_tiers} maxActive={data.promotion_max_active} onMutation={mutate} />}
      {data && <NewsletterSection newsletter={data.newsletter} />}
      {data && <CatalogSection title="Tours" items={data.tours} fields={tourFields(data.destinations)} basePath="/api/admin/tours" onMutation={mutate} ownerLabel={vendorOwner} csrfToken={data.csrf_token} />}
      {data && <AvailabilitySection tours={data.tours} endpoint="/api/admin/availability" csrfToken={data.csrf_token} />}
      {data && <CatalogSection title="Services" items={data.services} fields={serviceFields(data)} basePath="/api/admin/services" onMutation={mutate} ownerLabel={serviceOwner} csrfToken={data.csrf_token} />}
      {data && <CatalogSection title="Properties" items={data.properties} fields={propertyFields} basePath="/api/admin/properties" onMutation={mutate} ownerLabel={hostOwner} csrfToken={data.csrf_token} />}
      {data && <PropertyInventorySection properties={data.properties} basePath="/api/admin/properties" csrfToken={data.csrf_token} />}
      {data && <CatalogSection title="Trending destinations" items={data.destinations} fields={destinationFields} basePath="/api/admin/destinations" onMutation={mutate} csrfToken={data.csrf_token} />}
      {data && <AdminAccounts admins={data.admins} vendors={data.vendors} onMutation={mutate} />}
      <a className="inline-flex font-semibold text-[#9a5534] hover:underline" href="/dashboard">Open bookings and messages →</a>
    </DashboardLayout>
  );
}

export function VendorDashboardPage() {
  const { data, loading, error, message, load, mutate } = usePortalData('/api/vendor/catalogue');
  const [signOutError, setSignOutError] = useState('');
  const signOut = makeSignOut({
    endpoint: '/partner/logout',
    csrfToken: data?.csrf_token,
    redirectTo: '/partner/login',
    onError: setSignOutError,
  });

  if (loading && !data) return <div className="min-h-screen bg-[#f8f7f2]"><PortalHeader role="Partner" actor="Loading your dashboard…" /><main className="mx-auto max-w-7xl px-5 py-10 text-[#52615b]">Loading your listings…</main></div>;
  if (error && !data) return <DashboardLoadError role="Partner" error={error} onRetry={load} />;

  return (
    <DashboardLayout role="Partner" actor={data?.vendor.name || 'Your listings'} signOut={signOut}>
      <DashboardStatus error={error || signOutError} message={message} />
      {data && <p className="text-sm text-[#52615b]">Welcome, {data.vendor.name}. Your tours, safaris, services, accommodations, departures, and guest bookings are gathered here. Signed in as {data.vendor.email}.</p>}
      {data && <div className="grid gap-4 sm:grid-cols-3">
        {[
          ['Your tours & safaris', data.tours.length],
          ['Your services', data.services.length],
          ['Your properties', data.properties.length],
        ].map(([label, count]) => <div className="rounded-2xl border border-[#e9e5db] bg-white p-5" key={label}><p className="text-sm text-[#52615b]">{label}</p><p className="display-font mt-2 text-3xl text-[#203b35]">{count}</p></div>)}
      </div>}
      {data && <VendorProfileSection vendor={data.vendor} onMutation={mutate} csrfToken={data.csrf_token} />}
      {data && <CatalogSection title="Tours" items={data.tours} fields={tourFields(data.destinations)} basePath="/api/vendor/tours" onMutation={mutate} csrfToken={data.csrf_token} />}
      {data && <AvailabilitySection tours={data.tours} endpoint="/api/vendor/availability" csrfToken={data.csrf_token} />}
      {data && <CatalogSection title="Services" items={data.services} fields={serviceFields(data)} basePath="/api/vendor/services" onMutation={mutate} csrfToken={data.csrf_token} />}
      {data && <CatalogSection title="Properties" items={data.properties} fields={propertyFields} basePath="/api/vendor/properties" onMutation={mutate} csrfToken={data.csrf_token} />}
      {data && <PropertyInventorySection properties={data.properties} basePath="/api/vendor/properties" csrfToken={data.csrf_token} />}
      {data && <VendorBookingsSection csrfToken={data.csrf_token} />}
    </DashboardLayout>
  );
}
