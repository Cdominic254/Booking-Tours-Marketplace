// Travel regions used to browse the catalogue. Each region groups the
// destinations already published in the catalogue, so a listing shows up in
// whichever region its destination belongs to without extra bookkeeping.
export const REGIONS = [
  {
    slug: 'nairobi',
    name: 'Nairobi & surroundings',
    tagline: 'Capital & Rift Valley lakes',
    description:
      'A national park against the city skyline, giraffe sanctuaries, coffee farms and the Rift Valley lakes that make an easy day out: Naivasha boat safaris and the cliffs of Hell’s Gate.',
    image: 'pictures/772777099.jpg',
    imageAlt: 'Giraffes grazing with the Nairobi skyline behind them',
    destinationSlugs: ['nairobi', 'naivasha'],
  },
  {
    slug: 'maasai-mara',
    name: 'Maasai Mara',
    tagline: 'Big-cat plains',
    description:
      'Open savannah, the great migration and the highest concentration of big cats in the country. Come for game drives by day and balloon flights at dawn.',
    image: 'pictures/295463166.jpg',
    imageAlt: 'Open savannah plains in the Maasai Mara',
    destinationSlugs: ['maasai-mara'],
  },
  {
    slug: 'amboseli',
    name: 'Amboseli',
    tagline: 'Elephants below Kilimanjaro',
    description:
      'Elephant herds crossing the swamps with Kilimanjaro filling the horizon. A compact park that rewards early mornings and slow evenings.',
    image: 'pictures/337169041.jpg',
    imageAlt: 'Elephant herd in Amboseli with Kilimanjaro in the distance',
    destinationSlugs: ['amboseli'],
  },
  {
    slug: 'tsavo',
    name: 'Tsavo',
    tagline: 'Red earth & waterholes',
    description:
      'Kenya’s largest park, split into Tsavo East and West: red-dusted elephants, lava flows, baobabs and the road that links Nairobi with the coast.',
    image: 'images/tsavo-red-elephants.jpg',
    imageAlt: 'Red elephants walking across the dry Tsavo savannah',
    destinationSlugs: ['tsavo'],
  },
  {
    slug: 'coast',
    name: 'Coastal Kenya',
    tagline: 'Mombasa · Diani · Lamu',
    description:
      'The Indian Ocean: Swahili old towns, dhow sails, reef snorkelling and long white beaches from Mombasa and Diani up to Lamu and Watamu.',
    image: 'images/img-12.webp',
    imageAlt: 'A palm-lined beach with a dhow on the Kenyan coast',
    destinationSlugs: ['mombasa', 'diani', 'lamu', 'watamu'],
  },
  {
    slug: 'mount-kenya',
    name: 'Mount Kenya region',
    tagline: 'Peaks, forest & highland farms',
    description:
      'Africa’s second-highest mountain and the green country around it: montane forest walks, trout streams, coffee farms and cool highland lodges around Nanyuki and Naro Moru.',
    image: 'images/mount-kenya-highlands.jpg',
    imageAlt: 'The snow-capped peaks of Mount Kenya above highland farmland',
    destinationSlugs: ['mount-kenya'],
  },
];

export function findRegion(slug) {
  if (!slug) return null;
  return REGIONS.find((region) => region.slug === slug) || null;
}

export function regionDestinations(region, destinations) {
  if (!region) return destinations || [];
  return (destinations || []).filter((item) => region.destinationSlugs.includes(item.slug));
}

export function inRegion(region, listing) {
  return Boolean(region) && region.destinationSlugs.includes(listing.destination);
}

export function regionListingCounts(region, catalogue) {
  const tours = (catalogue.tours || []).filter((item) => inRegion(region, item)).length;
  const stays = (catalogue.properties || []).filter((item) => inRegion(region, item)).length;
  return { tours, stays };
}

export function regionHref(region, kind) {
  const page = kind === 'stays' ? '/properties.html' : '/tours.html';
  return `${page}?region=${encodeURIComponent(region.slug)}`;
}
