// Server-backed wishlist shared by every page. One fetch per page load keeps
// the heart icons and the header count in sync without prop drilling.
import { getErrorMessage } from './utils.js';

const EMPTY_STATE = { status: 'idle', signedIn: false, items: [], csrfToken: '', error: '' };

let snapshot = EMPTY_STATE;
let inflight = null;
const listeners = new Set();

function publish(update) {
  snapshot = { ...snapshot, ...update };
  listeners.forEach((listener) => listener());
}

export function subscribeWishlist(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getWishlistSnapshot() {
  return snapshot;
}

function requestHeaders(csrfToken, withBody = false) {
  const headers = { Accept: 'application/json' };
  if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
  if (withBody) headers['Content-Type'] = 'application/json';
  return headers;
}

export function loadWishlist({ force = false } = {}) {
  if (inflight && !force) return inflight;
  inflight = (async () => {
    if (snapshot.status !== 'ready') publish({ status: 'loading', error: '' });
    try {
      const response = await fetch('/api/customer/saved', {
        credentials: 'same-origin',
        headers: requestHeaders(snapshot.csrfToken),
      });
      if (response.status === 401) {
        publish({ status: 'guest', signedIn: false, items: [], csrfToken: '', error: '' });
        return snapshot;
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Your wishlist could not be loaded.');
      publish({
        status: 'ready',
        signedIn: true,
        items: Array.isArray(data.items) ? data.items : [],
        csrfToken: data.csrf_token || '',
        error: '',
      });
    } catch (error) {
      publish({ status: 'error', error: getErrorMessage(error) });
    } finally {
      inflight = null;
    }
    return snapshot;
  })();
  return inflight;
}

export function isSaved(listingType, listingSlug) {
  return snapshot.items.some(
    (item) => item.listing_type === listingType && item.listing_slug === listingSlug,
  );
}

export async function toggleSaved(listingType, listingSlug) {
  if (snapshot.status !== 'ready') await loadWishlist();
  if (snapshot.status === 'error') {
    throw new Error(snapshot.error || 'Your wishlist could not be loaded.');
  }
  if (!snapshot.signedIn) return { saved: false, needsSignIn: true };

  const existing = snapshot.items.find(
    (item) => item.listing_type === listingType && item.listing_slug === listingSlug,
  );
  if (existing) {
    await removeSaved(existing);
    return { saved: false, needsSignIn: false };
  }

  const response = await fetch('/api/customer/saved', {
    method: 'POST',
    credentials: 'same-origin',
    headers: requestHeaders(snapshot.csrfToken, true),
    body: JSON.stringify({ listing_type: listingType, listing_slug: listingSlug }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'This listing could not be saved.');
  if (data.item) {
    publish({
      items: [data.item, ...snapshot.items.filter((item) => item.id !== data.item.id)],
    });
  }
  return { saved: true, needsSignIn: false, alreadySaved: Boolean(data.already_saved) };
}

export async function removeSaved(item) {
  const response = await fetch(`/api/customer/saved/${item.id}`, {
    method: 'DELETE',
    credentials: 'same-origin',
    headers: requestHeaders(snapshot.csrfToken),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'That listing could not be removed.');
  publish({ items: snapshot.items.filter((entry) => entry.id !== item.id) });
}

export async function clearSaved() {
  const response = await fetch('/api/customer/saved', {
    method: 'DELETE',
    credentials: 'same-origin',
    headers: requestHeaders(snapshot.csrfToken),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Your wishlist could not be cleared.');
  publish({ items: [] });
}
