import { me } from './api.js';
const hd = document.getElementById('hd');
if (hd && !hd.children.length) {
  hd.innerHTML = `<div class="wrap nav"><a class="logo" href="/" aria-label="Lenslet home"><i></i>Lenslet</a>
    <nav class="links" aria-label="Primary"><a href="/gear.html">Gear</a><a href="/account.html">My bookings</a></nav>
    <div class="navr"><a class="btn" id="auth-link" href="/login.html">Sign in</a></div></div>`;
  hd.classList.add('s');
}
me().then(u => {
  const a = document.getElementById('auth-link'); if (!a || !u) return;
  a.textContent = u.role === 'admin' ? 'Owner dashboard' : u.name.split(' ')[0]; a.href = u.role === 'admin' ? '/admin.html' : '/account.html';
});
