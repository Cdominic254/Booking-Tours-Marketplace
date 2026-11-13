export function getErrorMessage(error) {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}

export function whatsappUrl(message, phone = '') {
  const recipient = String(phone || '').replace(/\D/g, '');
  const path = recipient ? `/${recipient}` : '/';
  return `https://wa.me${path}?text=${encodeURIComponent(message)}`;
}

export function documentLanguage() {
  return document.documentElement.lang === 'sw' ? 'sw' : 'en';
}

export function todayInKenya() {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Africa/Nairobi',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function addDaysToIsoDate(date, days) {
  const result = new Date(`${date}T00:00:00Z`);
  result.setUTCDate(result.getUTCDate() + days);
  return result.toISOString().slice(0, 10);
}

export function numberLocale(language = documentLanguage()) {
  return language === 'sw' ? 'sw-KE' : 'en-KE';
}

export function formatNumber(value, language = documentLanguage()) {
  return Number(value).toLocaleString(numberLocale(language));
}

export function formatMoney(amount, currency, language = documentLanguage()) {
  const code = currency.code in currency.rates ? currency.code : 'KES';
  return new Intl.NumberFormat(numberLocale(language), {
    style: 'currency',
    currency: code,
    maximumFractionDigits: code === 'KES' ? 0 : 2,
  }).format(amount * currency.rates[code]);
}

export function formatShillings(amount, language = documentLanguage()) {
  return new Intl.NumberFormat(numberLocale(language), {
    style: 'currency',
    currency: 'KES',
    maximumFractionDigits: 0,
  }).format(amount);
}
