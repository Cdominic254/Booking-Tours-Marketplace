export function getErrorMessage(error) {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}

export function whatsappUrl(message, phone = '') {
  const recipient = String(phone || '').replace(/\D/g, '');
  const path = recipient ? `/${recipient}` : '/';
  return `https://wa.me${path}?text=${encodeURIComponent(message)}`;
}
