// Curated collections that cut across the catalogue. A stay can be a luxury
// lodge or a budget room; a tour can be a day out, an overnight safari or an
// adventure activity. Every collection is derived from published listing data,
// so a new listing joins the right collections as soon as it is published.
const LUXURY_TYPES = new Set(['lodge', 'resort']);
const LUXURY_PRICE_FLOOR = 15000;
const BUDGET_PRICE_CEILING = 7000;
const ADVENTURE_CATEGORIES = new Set(['Adventure & Nature', 'Water & Marine']);
const ADVENTURE_WORDS = /(adventure|snorkel|scuba|dive|kayak|cycle|cycling|hike|hiking|climb|raft|balloon|surf|jet ?ski|windsurf|paddle|quad|bungee|zipline)/i;

function nightlyRate(property) {
  return Number(property.price_per_night) || Number(property.price_from) || 0;
}

function tourDays(tour) {
  return Number(tour.duration_days) || 1;
}

export const CATEGORIES = [
  {
    slug: 'luxury-stays',
    label: 'Luxury lodges',
    kind: 'stays',
    tagline: 'Premium stays',
    description: 'Lodges, resorts and premium villas with the space and service to slow down — from river-front camps in the Mara to ocean villas on Manda Island.',
    image: 'pictures/295463173.jpg',
    imageAlt: 'A river-front safari lodge in the Maasai Mara',
    href: '/properties.html?collection=luxury-stays',
    cta: 'Browse luxury stays',
    matches: (property) => LUXURY_TYPES.has(property.property_type) || nightlyRate(property) >= LUXURY_PRICE_FLOOR,
  },
  {
    slug: 'budget-stays',
    label: 'Budget accommodations',
    kind: 'stays',
    tagline: 'Good value',
    description: 'Guest houses, budget hotels and simple homes under KSh 7,000 a night, chosen for where they put you rather than the size of the lobby.',
    image: 'pictures/292079957.jpg',
    imageAlt: 'A simple guest house room in Lamu town',
    href: '/properties.html?collection=budget-stays',
    cta: 'Browse budget stays',
    matches: (property) => {
      const rate = nightlyRate(property);
      return rate > 0 && rate <= BUDGET_PRICE_CEILING;
    },
  },
  {
    slug: 'day-tours',
    label: 'Day tours',
    kind: 'experiences',
    tagline: 'One day, back by dark',
    description: 'Single-day experiences: a morning on the reef, a walk through the old town, a game drive before dinner. You are back at your bed by nightfall.',
    image: 'images/shela-lamu-kenya-09.jpg',
    imageAlt: 'A dhow sailing off the Lamu coast',
    href: '/tours.html?collection=day-tours',
    cta: 'Browse day tours',
    matches: (tour) => tourDays(tour) <= 1,
  },
  {
    slug: 'multi-day-safaris',
    label: 'Multi-day safaris',
    kind: 'experiences',
    tagline: 'Overnight packages',
    description: 'Overnight packages with park fees, game drives and full board included — three, four or six days between the parks and the coast.',
    image: 'pictures/295463166.jpg',
    imageAlt: 'Open savannah in the Maasai Mara',
    href: '/tours.html?collection=multi-day-safaris',
    cta: 'Browse multi-day safaris',
    matches: (tour) => tour.tour_type === 'multi-day-safari' || tourDays(tour) >= 2,
  },
  {
    slug: 'adventure-activities',
    label: 'Adventure activities',
    kind: 'experiences',
    tagline: 'Water, wheels and altitude',
    description: 'Snorkelling and dhow sailing, cycling the Rift Valley cliffs, sunrise balloon flights and the occasional adrenaline detour.',
    image: 'pictures/873059687.jpg',
    imageAlt: 'Cyclists on the trails below the Rift Valley cliffs',
    href: '/tours.html?collection=adventure-activities',
    cta: 'Browse adventure activities',
    matches: (tour) => ADVENTURE_CATEGORIES.has(tour.category)
      || ADVENTURE_WORDS.test(`${tour.name} ${tour.category} ${tour.description}`),
  },
];

export function findCategory(slug) {
  if (!slug) return null;
  return CATEGORIES.find((category) => category.slug === slug) || null;
}

export function categoriesFor(kind) {
  return CATEGORIES.filter((category) => category.kind === kind);
}

export function categoryItems(category, catalogue) {
  if (!category) return [];
  const source = category.kind === 'stays' ? catalogue.properties : catalogue.tours;
  return (source || []).filter(category.matches);
}
