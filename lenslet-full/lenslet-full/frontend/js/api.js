export async function api(path, opt = {}) {
  const r = await fetch('/api' + path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    ...opt, body: opt.body ? JSON.stringify(opt.body) : undefined });
  const d = r.status === 204 ? null : await r.json().catch(() => ({}));
  if (!r.ok) {
    const det = d && d.detail;
    const msg = typeof det === 'string' ? det : det && det.message ? det.message
      : Array.isArray(det) ? 'Please check the highlighted details and try again.' : 'Something went wrong. Please try again.';
    throw Object.assign(new Error(msg), { status: r.status, data: det });
  }
  return d;
}
export const inr = p => '₹' + (p / 100).toLocaleString('en-IN', { maximumFractionDigits: 0 });
export const me = () => api('/auth/me').then(d => d.user).catch(() => null);
export const fdt = s => new Date(s).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const label = s => s.replace(/_/g, ' ').toLowerCase().replace(/^./, c => c.toUpperCase());

export function toast(msg, bad) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; t.setAttribute('role', 'status'); document.body.append(t); }
  t.textContent = msg; t.className = 'show' + (bad ? ' bad' : '');
  clearTimeout(t._t); t._t = setTimeout(() => t.className = '', 4200);
}

let rzp;
const loadRzp = () => rzp ||= new Promise((ok, no) => { const s = document.createElement('script'); s.src = 'https://checkout.razorpay.com/v1/checkout.js'; s.onload = ok; s.onerror = () => no(new Error('Could not load the payment window. Check your connection.')); document.head.append(s); });

/** Opens Razorpay checkout for a booking. Success is only ever shown after the server verifies the signature. */
export async function payBooking(id, user, onPaid, onNote) {
  let o;
  try { o = await api(`/bookings/${id}/pay`, { method: 'POST' }); }
  catch (e) { onNote(e.status === 503 ? 'Online payments are not switched on yet. Your gear is held for 15 minutes; the owner can take payment at the counter.' : e.message, true); return; }
  try { await loadRzp(); } catch (e) { onNote(e.message, true); return; }
  new Razorpay({ key: o.key_id, order_id: o.order_id, amount: o.amount, currency: 'INR', name: 'Lenslet', description: 'Booking ' + o.code,
    prefill: { name: user.name, email: user.email }, theme: { color: '#ffa77a' },
    handler: async r => { try { await api(`/bookings/${id}/verify`, { method: 'POST', body: r }); onPaid(); } catch (e) { onNote(e.message, true); } },
    modal: { ondismiss: () => onNote('Payment was not completed. Your gear stays held for 15 minutes.', true) } }).open();
}
