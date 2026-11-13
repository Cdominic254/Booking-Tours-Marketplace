// Curated photography from the destinations the marketplace sells. Every shot is
// bundled with the site so the gallery renders instantly; listing photographs are
// merged in from the catalogue at render time.
export const GALLERY_PHOTOS = [
  {
    src: '/images/img-12.webp',
    title: 'Palm-lined beach',
    alt: 'A palm-lined beach with a dhow on the Kenyan coast',
    place: 'Kenyan coast',
    region: 'coast',
  },
  {
    src: '/pictures/187168867.jpg',
    title: 'Turquoise lagoon',
    alt: 'Turquoise lagoon and dhow near Lamu',
    place: 'Lamu',
    region: 'coast',
  },
  {
    src: '/images/Lamu_coast.jpg',
    title: 'Lamu waterfront',
    alt: 'Aerial view of the Lamu waterfront',
    place: 'Lamu',
    region: 'coast',
  },
  {
    src: '/images/IMG_2026-03-23-17-36-36-712.jpg',
    title: 'Harbour evenings',
    alt: 'Boats moored in Lamu harbour at dusk',
    place: 'Lamu',
    region: 'coast',
  },
  {
    src: '/images/site_1055_0011-1000-748-20151105113637.jpg',
    title: 'Sail the channel',
    alt: 'A dhow sailing along the Lamu shoreline',
    place: 'Lamu',
    region: 'coast',
  },
  {
    src: '/images/Lamu_Fort_Museum\'s.jpg',
    title: 'Lamu Fort',
    alt: 'Lamu Fort, the coral-stone fortress in Lamu Old Town',
    place: 'Lamu Old Town',
    region: 'coast',
  },
  {
    src: '/images/Riadha_Mosque_in_Lamu.jpg',
    title: 'Riadha Mosque',
    alt: 'Riadha Mosque in Lamu Old Town',
    place: 'Lamu Old Town',
    region: 'coast',
  },
  {
    src: '/images/Lamu_Donkey_Sanctuary.jpg',
    title: 'Donkey sanctuary',
    alt: 'The donkey sanctuary on Lamu island',
    place: 'Lamu',
    region: 'coast',
  },
  {
    src: '/pictures/552015001.jpg',
    title: 'Dinner on the sand',
    alt: 'Dinner tables set on the sand beneath trees',
    place: 'Swahili coast',
    region: 'coast',
  },
  {
    src: '/pictures/426299433.jpg',
    title: 'Slow afternoons',
    alt: 'A plunge pool beside a whitewashed villa',
    place: 'Shela',
    region: 'coast',
  },
  {
    src: '/pictures/292080012.jpg',
    title: 'Mombasa',
    alt: 'Mombasa, the Indian Ocean port city',
    place: 'Mombasa',
    region: 'coast',
  },
  {
    src: '/pictures/497804782.jpg',
    title: 'Diani Beach',
    alt: 'Diani Beach on the south coast',
    place: 'Diani',
    region: 'coast',
  },
  {
    src: '/pictures/498623900.jpg',
    title: 'Watamu Marine Park',
    alt: 'Watamu Marine National Park on the north coast',
    place: 'Watamu',
    region: 'coast',
  },
  {
    src: '/pictures/295463166.jpg',
    title: 'Open savannah',
    alt: 'Open savannah plains in the Maasai Mara',
    place: 'Maasai Mara',
    region: 'maasai-mara',
  },
  {
    src: '/pictures/337169041.jpg',
    title: 'Below Kilimanjaro',
    alt: 'Elephant herd in Amboseli with Kilimanjaro in the distance',
    place: 'Amboseli',
    region: 'amboseli',
  },
  {
    src: '/images/tsavo-red-elephants.jpg',
    title: 'Red earth',
    alt: 'Red elephants walking across the dry Tsavo savannah',
    place: 'Tsavo',
    region: 'tsavo',
  },
  {
    src: '/pictures/772777099.jpg',
    title: 'Giraffes and skyline',
    alt: 'Giraffes grazing with the Nairobi skyline behind them',
    place: 'Nairobi',
    region: 'nairobi',
  },
  {
    src: '/pictures/772777040.jpg',
    title: 'Nairobi',
    alt: 'Nairobi, Kenya’s capital city',
    place: 'Nairobi',
    region: 'nairobi',
  },
  {
    src: '/pictures/882985623.jpg',
    title: 'Lake Naivasha',
    alt: 'Lake Naivasha in the Rift Valley',
    place: 'Naivasha',
    region: 'nairobi',
  },
  {
    src: '/images/mount-kenya-highlands.jpg',
    title: 'Mount Kenya peaks',
    alt: 'The snow-capped peaks of Mount Kenya above highland farmland',
    place: 'Mount Kenya',
    region: 'mount-kenya',
  },
];

// Photographs of listings come from the catalogue, where the listing name is
// already the honest caption. Destination is used to place them in a region.
export function cataloguePhotos(catalogue) {
  const listings = [
    ...(catalogue?.tours || []).map((tour) => ({ ...tour, listingType: 'tour' })),
    ...(catalogue?.properties || []).map((property) => ({ ...property, listingType: 'property' })),
  ];
  return listings
    .filter((listing) => listing.image_url)
    .map((listing) => ({
      src: listing.image_url,
      title: listing.name,
      alt: `${listing.name} in ${listing.destination || 'Kenya'}`,
      place: listing.location || listing.destination || 'Kenya',
      region: listing.destination || '',
      href: listing.listingType === 'tour'
        ? `/tour-details.html?id=${encodeURIComponent(listing.slug)}`
        : `/booking.html?stay=${encodeURIComponent(listing.slug)}`,
      listingType: listing.listingType,
    }));
}

export function galleryRegions(catalogue) {
  const slugs = new Set([
    ...GALLERY_PHOTOS.map((photo) => photo.region),
    ...cataloguePhotos(catalogue).map((photo) => photo.region),
  ]);
  return [...slugs].filter(Boolean);
}
