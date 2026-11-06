import { useEffect, useMemo, useState } from 'react';
import { whatsappUrl } from './utils.js';

const HISTORY_KEY = 'lamu-trip-search-history';
const AREA_TERMS = {
  beach: ['beach', 'coast', 'shore', 'sea', 'sand', 'shela', 'manda', 'kipungani'],
  heritage: ['old town', 'heritage', 'cultural', 'history', 'museum', 'swahili', 'lamu town'],
};
const ACTIVITY_TERMS = {
  beach: ['beach', 'coast', 'shore', 'sea', 'sand', 'swim'],
  boat: ['dhow', 'boat', 'sail', 'sailing', 'island hopping'],
  heritage: ['old town', 'heritage', 'cultural', 'history', 'museum', 'swahili'],
  snorkeling: ['snorkel', 'reef', 'swim'],
};

function todayInLamu() {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Nairobi',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function readHistory() {
  try {
    const history = JSON.parse(window.localStorage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(history) ? history : [];
  } catch {
    return [];
  }
}

function listingText(listing) {
  return [
    listing.name,
    listing.category,
    listing.location,
    listing.pickup_point,
    listing.description,
    ...(listing.amenities || []),
    ...(listing.itinerary || []),
    ...(listing.inclusions || []),
  ].filter(Boolean).join(' ').toLowerCase();
}

function hasTerm(text, terms) {
  return terms.some((term) => text.includes(term));
}

function hasCoordinates(item) {
  return Number.isFinite(item.latitude) && Number.isFinite(item.longitude);
}

function distanceKm(first, second) {
  const radians = (degrees) => degrees * Math.PI / 180;
  const latitudeDelta = radians(second.latitude - first.latitude);
  const longitudeDelta = radians(second.longitude - first.longitude);
  const latitude1 = radians(first.latitude);
  const latitude2 = radians(second.latitude);
  const arc = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(latitude1) * Math.cos(latitude2) * Math.sin(longitudeDelta / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(arc), Math.sqrt(1 - arc));
}

function formatPrice(amount, language) {
  return new Intl.NumberFormat(language === 'sw' ? 'sw-KE' : 'en-KE', {
    style: 'currency',
    currency: 'KES',
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(date, language) {
  return new Date(`${date}T12:00:00`).toLocaleDateString(language === 'sw' ? 'sw-KE' : 'en-KE', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
}

function addDays(date, days) {
  const result = new Date(`${date}T00:00:00Z`);
  result.setUTCDate(result.getUTCDate() + days);
  return result.toISOString().slice(0, 10);
}

function departureOptions(availability, tour, filters) {
  const guests = Number(filters.guests) || 1;
  return (availability[tour.slug] || []).filter((schedule) => {
    const date = schedule.starts_at.slice(0, 10);
    return schedule.remaining >= guests
      && (!filters.startDate || date >= filters.startDate)
      && (!filters.endDate || date <= filters.endDate);
  });
}

function recommendationScore(tour, search) {
  const text = listingText(tour);
  let score = 0;
  if (search.area !== 'any' && hasTerm(text, AREA_TERMS[search.area] || [])) score += 2;
  if (search.activity !== 'any' && hasTerm(text, ACTIVITY_TERMS[search.activity] || [])) score += 3;
  if (search.feature && text.includes(search.feature.toLowerCase())) score += 4;
  return score;
}

export default function SmartTripPlanner({ tours, properties, destinations = [], whatsappPhone = '', guests: initialGuests = 1 }) {
  const today = useMemo(todayInLamu, []);
  const [language, setLanguage] = useState(document.documentElement.lang === 'sw' ? 'sw' : 'en');
  const [filters, setFilters] = useState({
    startDate: today,
    endDate: '',
    guests: String(initialGuests),
    budget: '',
    stayBudget: '',
    maxDistance: '5',
    area: 'any',
    activity: 'any',
    feature: '',
  });
  const [availability, setAvailability] = useState({});
  const [availabilityLoading, setAvailabilityLoading] = useState(true);
  const [availabilityError, setAvailabilityError] = useState('');
  const [scheduleChoices, setScheduleChoices] = useState({});
  const [itinerary, setItinerary] = useState([]);
  const [history, setHistory] = useState(readHistory);
  const [planMessage, setPlanMessage] = useState('');

  useEffect(() => {
    function syncLanguage(event) {
      setLanguage(event.detail.language);
    }
    document.addEventListener('lamu-language-changed', syncLanguage);
    return () => document.removeEventListener('lamu-language-changed', syncLanguage);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    if (!tours.length) {
      setAvailability({});
      setAvailabilityLoading(false);
      return () => controller.abort();
    }

    setAvailabilityLoading(true);
    setAvailabilityError('');
    Promise.all(tours.map(async (tour) => {
      try {
        const response = await fetch(`/api/tours/${encodeURIComponent(tour.slug)}/availability`, {
          signal: controller.signal,
          headers: { Accept: 'application/json' },
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Availability could not be loaded.');
        return [tour.slug, result.schedules || [], false];
      } catch (error) {
        if (error.name === 'AbortError') throw error;
        return [tour.slug, [], true];
      }
    }))
      .then((results) => {
        if (controller.signal.aborted) return;
        setAvailability(Object.fromEntries(results.map(([slug, schedules]) => [slug, schedules])));
        if (results.some(([, , failed]) => failed)) {
          setAvailabilityError('Some departure times could not be checked. Try refreshing the page.');
        }
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setAvailabilityError('Departure availability could not be checked.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setAvailabilityLoading(false);
      });

    return () => controller.abort();
  }, [tours]);

  const eligibleTours = useMemo(() => tours.filter((tour) => (
    departureOptions(availability, tour, filters).length > 0
  )), [availability, filters, tours]);

  const matchingTours = useMemo(() => eligibleTours.filter((tour) => {
    const text = listingText(tour);
    const guests = Number(filters.guests) || 1;
    const withinBudget = !filters.budget || tour.price <= Number(filters.budget);
    const withinGroupLimits = guests >= tour.min_group_size && guests <= tour.max_group_size;
    const withinArea = filters.area === 'any' || hasTerm(text, AREA_TERMS[filters.area] || []);
    const withinActivity = filters.activity === 'any' || hasTerm(text, ACTIVITY_TERMS[filters.activity] || []);
    const withinFeature = !filters.feature || text.includes(filters.feature.trim().toLowerCase());
    return withinBudget && withinGroupLimits && withinArea && withinActivity && withinFeature;
  }), [eligibleTours, filters]);

  const recommendations = useMemo(() => {
    const previousSearch = history[0];
    if (!previousSearch) return [];
    return eligibleTours
      .map((tour) => ({ tour, score: recommendationScore(tour, previousSearch) }))
      .filter(({ score, tour }) => score > 0 && !matchingTours.includes(tour))
      .sort((left, right) => right.score - left.score)
      .slice(0, 3)
      .map(({ tour }) => tour);
  }, [eligibleTours, history, matchingTours]);

  const matchingProperties = useMemo(() => properties.filter((property) => {
    const text = listingText(property);
    const guests = Number(filters.guests) || 1;
    const withinBudget = !filters.stayBudget || property.price_per_night <= Number(filters.stayBudget);
    const withinGuests = property.guests >= guests;
    const targets = destinations.filter((destination) => (
      destination.site_type === filters.area && hasCoordinates(destination)
    ));
    const nearestDistance = hasCoordinates(property) && targets.length
      ? Math.min(...targets.map((destination) => distanceKm(property, destination)))
      : null;
    const withinArea = filters.area === 'any'
      || (targets.length
        ? nearestDistance !== null && nearestDistance <= Number(filters.maxDistance || 5)
        : hasTerm(text, AREA_TERMS[filters.area] || []));
    const withinFeature = !filters.feature || text.includes(filters.feature.trim().toLowerCase());
    return withinBudget && withinGuests && withinArea && withinFeature;
  }), [destinations, filters, properties]);

  function updateFilter(event) {
    const { name, value } = event.target;
    setFilters((current) => ({ ...current, [name]: value }));
  }

  function saveSearch(event) {
    event.preventDefault();
    const search = {
      area: filters.area,
      activity: filters.activity,
      feature: filters.feature.trim(),
    };
    const nextHistory = [search, ...history].slice(0, 8);
    setHistory(nextHistory);
    setPlanMessage('Search updated. Recommendations will reflect this trip.');
    try {
      window.localStorage.setItem(HISTORY_KEY, JSON.stringify(nextHistory));
    } catch {
      setPlanMessage('Search updated for this visit.');
    }
  }

  function addToItinerary(tour) {
    const options = departureOptions(availability, tour, filters);
    const requestedId = scheduleChoices[tour.slug];
    const schedule = options.find((item) => String(item.id) === requestedId) || options[0];
    if (!schedule) return;
    if (itinerary.some((item) => item.schedule.id === schedule.id)) {
      setPlanMessage('That departure is already in your itinerary.');
      return;
    }
    if (itinerary.some((item) => item.schedule.starts_at === schedule.starts_at)) {
      setPlanMessage('Choose a different time for activities on the same day.');
      return;
    }
    setItinerary((current) => [...current, {
      tour,
      schedule,
      guests: Number(filters.guests) || 1,
    }].sort((left, right) => left.schedule.starts_at.localeCompare(right.schedule.starts_at)));
    setPlanMessage('Activity added to your itinerary.');
  }

  function quoteUrl() {
    const isSwahili = language === 'sw';
    const lines = itinerary.map(({ tour, schedule, guests }) => (
      `${formatDate(schedule.starts_at.slice(0, 10), language)} ${isSwahili ? 'saa' : 'at'} ${schedule.starts_at.slice(11, 16)}: ${tour.name} (${guests} ${isSwahili ? guests === 1 ? 'mgeni' : 'wageni' : guests === 1 ? 'guest' : 'guests'}, ${formatPrice(tour.price * guests, language)})`
    ));
    const total = itinerary.reduce((sum, item) => sum + item.tour.price * item.guests, 0);
    const message = isSwahili
      ? ['Habari Lamu Tours, tafadhali thibitisheni mpango huu wa safari:', ...lines, `Jumla ya makadirio ya shughuli: ${formatPrice(total, language)}.`, 'Tafadhali thibitisheni nafasi na mtumie hatua salama za malipo ya M-Pesa.'].join('\n')
      : ['Hello Lamu Tours, please help confirm this trip plan:', ...lines, `Estimated activities total: ${formatPrice(total, language)}.`, 'Please confirm availability and share the secure M-Pesa checkout steps.'].join('\n');
    return whatsappUrl(message, whatsappPhone);
  }

  function dateEnquiryUrl() {
    const message = `Hello Lamu Tours, please help arrange an experience for ${filters.guests} guests between ${filters.startDate}${filters.endDate ? ` and ${filters.endDate}` : ''}.`;
    return whatsappUrl(message, whatsappPhone);
  }

  function renderTour(tour, recommendation = false) {
    const options = departureOptions(availability, tour, filters);
    const requestedId = scheduleChoices[tour.slug];
    const selectedSchedule = options.find((item) => String(item.id) === requestedId) || options[0];
    return (
      <article className="grid gap-4 border-b border-[#e9e5db] py-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center" key={`${recommendation ? 'recommended-' : ''}${tour.slug}`}>
        <div>
          <p className="text-xs font-bold uppercase text-[#a75f3a]">{tour.category || 'Island experience'}</p>
          <h3 className="display-font mt-1 text-xl text-[#203b35]">{tour.name}</h3>
          <p className="mt-1 text-sm text-[#52615b]">{formatPrice(tour.price, language)} per guest · {tour.duration} · {tour.pickup_point}</p>
          <p className="mt-2 line-clamp-2 text-sm text-[#52615b]">{tour.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          <label className="sr-only" htmlFor={`departure-${recommendation ? 'recommended-' : ''}${tour.slug}`}>Select a departure</label>
          <select
            className="field min-w-48"
            id={`departure-${recommendation ? 'recommended-' : ''}${tour.slug}`}
            value={selectedSchedule ? String(selectedSchedule.id) : ''}
            onChange={(event) => setScheduleChoices((current) => ({ ...current, [tour.slug]: event.target.value }))}
          >
            {options.map((schedule) => (
              <option value={schedule.id} key={schedule.id}>
                {formatDate(schedule.starts_at.slice(0, 10), language)}, {schedule.starts_at.slice(11, 16)} · {schedule.remaining} {language === 'sw' ? 'nafasi' : 'spaces'}
              </option>
            ))}
          </select>
          <button
            className="min-h-11 rounded-full bg-[#203b35] px-4 text-sm font-semibold text-white hover:bg-[#31554b] disabled:opacity-50"
            type="button"
            onClick={() => addToItinerary(tour)}
            disabled={!selectedSchedule}
          >
            Add to plan
          </button>
        </div>
      </article>
    );
  }

  const itineraryTotal = itinerary.reduce((sum, item) => sum + item.tour.price * item.guests, 0);
  const dates = [...new Set(itinerary.map((item) => item.schedule.starts_at.slice(0, 10)))];

  return (
    <section aria-labelledby="smart-plan-heading" className="border-y border-[#e9e5db] py-8 sm:py-10">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#a75f3a]">Smart trip planner</p>
          <h2 id="smart-plan-heading" className="display-font mt-2 text-3xl text-[#203b35]">Build a Lamu plan that fits.</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#52615b]">Search real tour departures by date and group size, then shape a day-by-day itinerary.</p>

          <form className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" onSubmit={saveSearch}>
            <label><span className="field-label">From</span><input className="field" name="startDate" type="date" min={today} value={filters.startDate} onChange={updateFilter} required /></label>
            <label><span className="field-label">Through</span><input className="field" name="endDate" type="date" min={filters.startDate || today} value={filters.endDate} onChange={updateFilter} /></label>
            <label><span className="field-label">Group size</span><input className="field" name="guests" type="number" min="1" max="30" value={filters.guests} onChange={updateFilter} required /></label>
            <label><span className="field-label">Max tour price per guest (KES)</span><input className="field" name="budget" type="number" min="0" step="500" placeholder="Any budget" value={filters.budget} onChange={updateFilter} /></label>
            <label><span className="field-label">Area</span><select className="field" name="area" value={filters.area} onChange={updateFilter}><option value="any">Any area</option><option value="beach">Beach & coast</option><option value="heritage">Old Town & heritage</option></select></label>
            <label><span className="field-label">Activity</span><select className="field" name="activity" value={filters.activity} onChange={updateFilter}><option value="any">Any activity</option><option value="beach">Beach time</option><option value="boat">Boat trips</option><option value="heritage">Old Town tours</option><option value="snorkeling">Snorkeling</option></select></label>
            <label><span className="field-label">Feature or amenity</span><input className="field" name="feature" value={filters.feature} onChange={updateFilter} placeholder="For example: guide" /></label>
            <label><span className="field-label">Max stay rate per night (KES)</span><input className="field" name="stayBudget" type="number" min="0" step="500" placeholder="Any rate" value={filters.stayBudget} onChange={updateFilter} /></label>
            <label><span className="field-label">Max distance from site (km)</span><input className="field" name="maxDistance" type="number" min="0" max="100" step="0.5" value={filters.maxDistance} onChange={updateFilter} /></label>
            <button className="min-h-12 rounded-full bg-[#b96e45] px-5 font-semibold text-white hover:bg-[#a45d38] sm:col-span-2 xl:col-span-4" type="submit">Find matching experiences</button>
          </form>
          <p className="mt-3 text-xs text-[#52615b]">Distance uses coordinates saved for a stay and its beach or heritage landmark. Listings without coordinates are excluded from measured-distance results.</p>

          {availabilityError && <p className="mt-5 rounded-lg bg-amber-50 p-3 text-sm text-amber-900" role="status">{availabilityError}</p>}
          <div className="mt-8">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h3 className="display-font text-2xl text-[#203b35]">Available experiences</h3>
              {availabilityLoading && <span className="text-sm text-[#52615b]" role="status">Checking live departures…</span>}
            </div>
            {!availabilityLoading && !availabilityError && eligibleTours.length === 0 && (
              <div className="mt-4 rounded-lg bg-[#f5f3ed] p-4">
                <p className="text-sm text-[#52615b]">No departures match those dates and group size.</p>
                <a className="mt-3 inline-flex rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" href={dateEnquiryUrl()} target="_blank" rel="noreferrer">Ask about dates on WhatsApp</a>
              </div>
            )}
            {!availabilityLoading && matchingTours.length === 0 && eligibleTours.length > 0 && <p className="mt-4 text-sm text-[#52615b]">No departures match these filters. Change your area, activity, budget, or feature.</p>}
            {matchingTours.map((tour) => renderTour(tour))}
          </div>

          {recommendations.length > 0 && (
            <div className="mt-10">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#a75f3a]">Based on your recent searches</p>
              {recommendations.map((tour) => renderTour(tour, true))}
            </div>
          )}

          {matchingProperties.length > 0 && (
            <div className="mt-10 border-t border-[#e9e5db] pt-8">
              <h3 className="display-font text-2xl text-[#203b35]">Stay ideas</h3>
              <p className="mt-1 text-sm text-[#52615b]">Guest capacity and rates match; the host confirms stay dates.</p>
              <div className="mt-2">
                {matchingProperties.map((property) => (
                  <article className="flex flex-wrap items-center justify-between gap-3 border-b border-[#e9e5db] py-4" key={property.slug}>
                    <div><h4 className="font-semibold text-[#203b35]">{property.name}</h4><p className="text-sm text-[#52615b]">{property.location} · {language === 'sw' ? `hadi ${property.guests} wageni · ${formatPrice(property.price_per_night, language)} / usiku` : `up to ${property.guests} guests · ${formatPrice(property.price_per_night, language)} / night`}</p></div>
                    <a className="rounded-full border border-[#203b35] px-4 py-2 text-sm font-semibold text-[#203b35] hover:bg-[#203b35] hover:text-white" href={`/booking.html?stay=${encodeURIComponent(property.slug)}&guests=${encodeURIComponent(filters.guests)}&check_in=${filters.startDate}&check_out=${filters.endDate > filters.startDate ? filters.endDate : addDays(filters.startDate, 1)}#booking-checkout`}>Ask about this stay</a>
                  </article>
                ))}
              </div>
            </div>
          )}
        </div>

        <aside className="h-fit border-l border-[#e9e5db] pl-0 lg:sticky lg:top-6 lg:pl-7">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="display-font text-2xl text-[#203b35]">Your itinerary</h3>
            <span className="text-sm text-[#52615b]">{dates.length} {dates.length === 1 ? 'day' : 'days'}</span>
          </div>
          {planMessage && <p className="mt-3 text-sm text-[#52615b]" role="status">{planMessage}</p>}
          {itinerary.length === 0 ? <p className="mt-4 text-sm leading-6 text-[#52615b]">Add available activities to see your plan and quote.</p> : (
            <>
              <div className="mt-4 divide-y divide-[#e9e5db]">
                {itinerary.map((item, index) => {
                  const date = item.schedule.starts_at.slice(0, 10);
                  const bookingHref = `/booking.html?tour=${encodeURIComponent(item.tour.slug)}&schedule_id=${item.schedule.id}&date=${date}&guests=${item.guests}#booking-checkout`;
                  return (
                    <article className="py-4" key={item.schedule.id}>
                      <p className="text-xs font-bold uppercase text-[#a75f3a]">{language === 'sw' ? 'Siku' : 'Day'} {dates.indexOf(date) + 1} · {formatDate(date, language)} · {item.schedule.starts_at.slice(11, 16)}</p>
                      <h4 className="mt-1 font-semibold text-[#203b35]">{item.tour.name}</h4>
                      <p className="mt-1 text-sm text-[#52615b]">{item.guests} {language === 'sw' ? item.guests === 1 ? 'mgeni' : 'wageni' : item.guests === 1 ? 'guest' : 'guests'} · {formatPrice(item.tour.price * item.guests, language)}</p>
                      <div className="mt-2 flex items-center gap-4 text-sm">
                        <a className="font-semibold text-[#9a5534] underline" href={bookingHref}>Book this activity</a>
                        <button className="text-[#52615b] underline" type="button" onClick={() => setItinerary((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</button>
                      </div>
                    </article>
                  );
                })}
              </div>
              <div className="border-t border-[#e9e5db] pt-4">
                <p className="flex justify-between gap-3 text-sm text-[#52615b]"><span>Estimated activities total</span><strong className="text-[#203b35]">{formatPrice(itineraryTotal, language)}</strong></p>
                <p className="mt-1 text-xs text-[#52615b]">Stay, transport, and final availability are not included.</p>
                <a className="mt-4 inline-flex min-h-12 w-full items-center justify-center rounded-full bg-[#177b5b] px-5 text-sm font-semibold text-white hover:bg-[#126448]" href={quoteUrl()} target="_blank" rel="noreferrer">{whatsappPhone ? 'Message Lamu Tours on WhatsApp' : 'Share quote on WhatsApp'}</a>
              </div>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}