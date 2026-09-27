/**
 * Popup — DentAI oturumu + manuel sync + sağlayıcı durumu.
 */

const $ = (id) => document.getElementById(id);

async function send(type, extra = {}) {
  return chrome.runtime.sendMessage({ type, ...extra });
}

function show(el, visible) {
  el.classList.toggle('hidden', !visible);
}

function formatTime(isoOrMs) {
  if (!isoOrMs) return '—';
  const d = typeof isoOrMs === 'number' ? new Date(isoOrMs) : new Date(isoOrMs);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' });
}

function sessionBadge(status) {
  const s = status?.pmsSession;
  if (s === 'OK') return '<span class="badge ok">PMS OK</span>';
  if (s === 'EXPIRED') return '<span class="badge err">Oturum yok</span>';
  if (s === 'ERROR' || status?.lastError) return '<span class="badge err">Hata</span>';
  if (s === 'UNKNOWN_ORIGIN') return '<span class="badge warn">Sekme yok</span>';
  return '<span class="badge warn">Bekliyor</span>';
}

function renderProviders(providers) {
  const list = $('provider-list');
  list.innerHTML = '';
  for (const p of providers || []) {
    const li = document.createElement('li');
    li.innerHTML = `
      <div class="name">${p.label} ${sessionBadge(p)}</div>
      <div class="stats">
        Kuyruk: ${p.queued ?? 0}
        · Son alım: ${formatTime(p.lastIngestAt)}
        · Son gönderim: ${formatTime(p.lastFlushAt)}
        ${p.lastError ? `<br>Hata: ${p.lastError}` : ''}
        ${p.lastPeriodicError ? `<br>Çekim: ${p.lastPeriodicError}` : ''}
      </div>
      <button type="button" class="reset-btn" data-reset="${p.id}">Delta sıfırla</button>
    `;
    list.appendChild(li);
  }

  list.querySelectorAll('[data-reset]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!confirm(`${btn.dataset.reset} delta/kuyruk sıfırlansın mı?`)) return;
      btn.disabled = true;
      await send('RESET_PROVIDER', { providerId: btn.dataset.reset });
      await refresh();
    });
  });
}

async function refresh() {
  const res = await send('GET_STATUS');
  if (!res?.ok) return;

  const loggedIn = Boolean(res.session);
  show($('login-panel'), !loggedIn);
  show($('session-panel'), loggedIn);

  if (loggedIn) {
    $('session-email').textContent = res.session.email || 'Bağlı';
    $('session-meta').textContent = [
      res.session.role,
      res.session.clinicId ? `klinik ${res.session.clinicId}` : null,
      res.session.apiBaseUrl,
    ]
      .filter(Boolean)
      .join(' · ');
    renderProviders(res.providers);
    $('next-run').textContent = res.nextRunAt
      ? `Sonraki otomatik sync: ${formatTime(res.nextRunAt)}`
      : 'Alarm henüz ayarlanmadı';
  }
}

$('login-btn').addEventListener('click', async () => {
  const btn = $('login-btn');
  const err = $('login-error');
  err.hidden = true;
  btn.disabled = true;
  try {
    const res = await send('LOGIN', {
      payload: {
        apiBaseUrl: $('api-base').value,
        email: $('email').value.trim(),
        password: $('password').value,
        clinicCode: $('clinic-code').value.trim() || null,
      },
    });
    if (!res?.ok) throw new Error(res?.error || 'Giriş başarısız');
    $('password').value = '';
    await refresh();
  } catch (e) {
    err.textContent = String(e.message || e);
    err.hidden = false;
  } finally {
    btn.disabled = false;
  }
});

$('logout-btn').addEventListener('click', async () => {
  await send('LOGOUT');
  await refresh();
});

$('sync-btn').addEventListener('click', async () => {
  const btn = $('sync-btn');
  const msg = $('sync-msg');
  btn.disabled = true;
  msg.hidden = false;
  msg.textContent = 'Senkron çalışıyor… (Dentsoft sekmesi açık olmalı)';
  try {
    const res = await send('SYNC_NOW');
    if (!res?.ok) throw new Error(res?.error || 'Sync başarısız');
    msg.textContent = 'Tamamlandı';
    await refresh();
  } catch (e) {
    msg.textContent = String(e.message || e);
  } finally {
    btn.disabled = false;
  }
});

refresh().catch(() => {});
