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

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

function calendarStats(p) {
  const c = p.calendar;
  if (!c && !p.calendarLive) return '';
  const r = c?.lastResult;
  const backfill = c?.backfillDone
    ? 'geçmiş tamamlandı'
    : c?.backfillCursor
      ? `geçmiş: ${new Date(c.backfillCursor).toLocaleDateString('tr-TR')} öncesi taranacak`
      : 'geçmiş tarama bekliyor';
  return `<br><b>Takvim</b> · Son: ${formatTime(c?.lastRunAt)}
    ${r ? ` · +${r.inserted} / güncelle ${r.updated} · yeni hasta ${r.patients_created} · yeni hekim ${r.doctors_created}` : ''}
    <br>${backfill}
    ${c?.lastError ? `<br>Takvim hata: ${escapeHtml(c.lastError)}` : ''}`;
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
        · Alınan: ${p.lastReceived ?? '—'}
        · Yeni: ${p.lastQueued ?? '—'}
        · Son alım: ${formatTime(p.lastIngestAt)}
        · Son gönderim: ${formatTime(p.lastFlushAt)}
        ${p.lastFlushResult ? `<br>DentAI: +${p.lastFlushResult.inserted ?? 0} / güncelle ${p.lastFlushResult.updated ?? 0}` : ''}
        ${p.lastSource ? `<br>Kaynak: ${p.lastSource}` : ''}
        ${p.lastError ? `<br>Hata: ${p.lastError}` : ''}
        ${p.lastPeriodicError ? `<br>Çekim: ${p.lastPeriodicError}` : ''}
        ${calendarStats(p)}
      </div>
      <button type="button" class="reset-btn" data-reset="${p.id}">Delta sıfırla</button>
      ${p.calendar ? `<button type="button" class="reset-btn" data-shape="${p.id}">Takvim alan yapısını kopyala</button>` : ''}
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

  list.querySelectorAll('[data-shape]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const res = await send('GET_CALENDAR_SHAPE', { providerId: btn.dataset.shape });
      if (!res?.shape) {
        btn.textContent = 'Henüz yapı yok — takvimi açıp sync edin';
        return;
      }
      await navigator.clipboard.writeText(JSON.stringify(res.shape, null, 2));
      btn.textContent = 'Kopyalandı (hasta verisi içermez)';
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
  msg.textContent = 'Senkron çalışıyor… hastalar + takvim randevuları okunuyor, 30–90 sn sürebilir.';
  try {
    const res = await send('SYNC_NOW');
    if (!res?.ok) throw new Error(res?.error || 'Sync başarısız');
    await refresh();
    const dentsoft = (await send('GET_STATUS'))?.providers?.find((p) => p.id === 'dentsoft');
    const received = dentsoft?.lastReceived ?? 0;
    const queued = dentsoft?.lastQueued ?? 0;
    msg.textContent =
      queued > 0
        ? `Tamamlandı: ${received} kişi okundu, ${queued} yeni kuyruğa alındı.`
        : `Tamamlandı: ${received} kişi okundu, yeni yok (hepsi daha önce eklenmiş).`;
  } catch (e) {
    msg.textContent = String(e.message || e);
  } finally {
    btn.disabled = false;
  }
});

refresh().catch(() => {});
