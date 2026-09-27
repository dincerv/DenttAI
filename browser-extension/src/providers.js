/**
 * PMS sağlayıcı tanımları.
 *
 * Alanlar:
 *   hosts                 → hostname eşleşmesi (tam veya alt alan adı)
 *   matchPatterns         → chrome.tabs.query için; manifest host_permissions ile aynı olmalı
 *   interceptUrlPatterns  → gerçek zamanlı yakalamada dikkate alınan URL regex kaynakları
 *   deltaStrategy         → 'auto' (sayısal id > tarih > görüldü seti) | 'seen' (sadece görüldü seti)
 *   periodicFetch         → (baseUrl, options, page) => { ok, data } | { ok:false, reason, status }
 *                           Kendi kendine yeterli olmalı (closure yok): hem sayfanın MAIN
 *                           world'ünde (chrome.scripting) hem service worker'da çalıştırılır.
 *                           options JSON-serileştirilebilir olmalı (RegExp/fonksiyon yok).
 *   extractItems(json)    → ham yanıttan kayıt dizisi
 *   toRecord(raw)         → { externalId, createdAt, patient } | null
 *                           patient = backend ExternalPatient şeması
 */

// ── Periyodik fetch fonksiyonları (self-contained) ────────────────────────

async function fetchPagedJson(baseUrl, options, page) {
  const headers = { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' };
  if (options.tokenStorageKey && typeof localStorage !== 'undefined') {
    const raw = localStorage.getItem(options.tokenStorageKey);
    if (raw) headers.Authorization = `Bearer ${raw.replace(/^"|"$/g, '')}`;
  }
  const url = new URL(options.path.replace('{page}', String(page)), baseUrl).toString();
  const res = await fetch(url, { credentials: 'include', headers, redirect: 'follow' });
  const contentType = res.headers.get('content-type') || '';
  const finalPath = new URL(res.url).pathname;
  if (res.status === 401 || res.status === 403 || new RegExp(options.loginPathRegex, 'i').test(finalPath)) {
    return { ok: false, reason: 'SESSION_EXPIRED', status: res.status };
  }
  if (!res.ok) return { ok: false, reason: 'HTTP_ERROR', status: res.status };
  if (!contentType.includes('json')) return { ok: false, reason: 'NOT_JSON', status: res.status };
  return { ok: true, data: await res.json() };
}

async function fetchDrDentesAppointments(baseUrl, options, page) {
  if (page > 1) return { ok: true, data: [] };

  const pageRes = await fetch(new URL('/index.php?menu=Randevu', baseUrl), { credentials: 'include' });
  const html = await pageRes.text();
  if (/\/giris/i.test(pageRes.url) || html.includes('frmGiris')) {
    return { ok: false, reason: 'SESSION_EXPIRED', status: pageRes.status };
  }

  let doctorIds = [];
  const infoMatch = html.match(/hekimBilgiArr\s*=\s*(\{[\s\S]*?\}),yetkiRandevu/);
  if (infoMatch) {
    try {
      doctorIds = Object.keys(JSON.parse(infoMatch[1]));
    } catch {
      doctorIds = [];
    }
  }
  if (!doctorIds.length) {
    const listMatch = html.match(/hekimArr\s*=\s*\[([\s\S]*?)\]/);
    if (listMatch) {
      doctorIds = listMatch[1]
        .split(',')
        .map((part) => part.trim().replace(/^["']|["']$/g, ''))
        .filter(Boolean);
    }
  }
  if (!doctorIds.length) return { ok: false, reason: 'NO_DOCTORS', status: pageRes.status };

  const localDate = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const now = new Date();
  const start = localDate(new Date(now.getTime() - options.daysBack * 86400000));
  const end = localDate(new Date(now.getTime() + options.daysAhead * 86400000));

  const byId = {};
  for (const doctorId of doctorIds) {
    const body = new URLSearchParams({
      islem: '1',
      id_dishekimi: doctorId,
      'tarih[baslangic]': start,
      'tarih[bitis]': end,
    });
    const res = await fetch(new URL('/ajax.php?randevuSayfasi=1', baseUrl), {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body,
    });
    if (!res.ok) continue;
    let items;
    try {
      items = await res.json();
    } catch {
      continue;
    }
    if (!Array.isArray(items)) continue;
    for (const item of items) {
      if (item && item.id != null) byId[String(item.id)] = item;
    }
  }
  return { ok: true, data: Object.values(byId) };
}

// ── Normalizasyon yardımcıları ────────────────────────────────────────────

function pick(obj, keys) {
  for (const key of keys) {
    const value = obj?.[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return null;
}

function pickArray(json, keys, depth = 0) {
  if (Array.isArray(json)) return json;
  if (!json || typeof json !== 'object' || depth > 3) return [];
  for (const key of keys) {
    const value = json[key];
    if (Array.isArray(value)) return value;
    if (value && typeof value === 'object') {
      const nested = pickArray(value, keys, depth + 1);
      if (nested.length) return nested;
    }
  }
  return [];
}

function clean(value, max) {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text ? text.slice(0, max) : null;
}

function cleanPhone(value) {
  const text = clean(value, 64);
  if (!text) return null;
  if (text.length <= 20) return text;
  const compact = text.replace(/[^\d+]/g, '');
  return compact ? compact.slice(0, 20) : null;
}

/** Backend `ExternalPatient` şemasına uygun, 422 üretmeyecek şekilde temizlenmiş kayıt. */
export function toExternalPatient({ fullName, phone, email, nationalId, birthDate, insuranceType, notes }) {
  const full_name = clean(fullName, 255);
  if (!full_name || full_name.length < 2) return null;
  const tc = nationalId ? String(nationalId).replace(/\D/g, '') : '';
  return {
    full_name,
    phone: cleanPhone(phone),
    email: clean(email, 255)?.toLowerCase() ?? null,
    national_id: tc.length === 11 ? tc : null,
    birth_date: clean(birthDate, 16),
    insurance_type: clean(insuranceType, 20),
    notes: clean(notes, 2000),
  };
}

// ── Kayıt eşleyicileri ────────────────────────────────────────────────────

function dentsoftRecord(raw) {
  if (!raw || typeof raw !== 'object') return null;

  // SearchList: PatientFirstName / PatientLastName / ContactMobile / PatientNumber (TC) / TransferID
  const first = pick(raw, ['PatientFirstName', 'ad', 'adi', 'Adi', 'firstName', 'FirstName', 'first_name']);
  const last = pick(raw, ['PatientLastName', 'soyad', 'soyadi', 'Soyadi', 'lastName', 'LastName', 'last_name']);
  const fullName =
    pick(raw, ['ad_soyad', 'adSoyad', 'AdSoyad', 'adiSoyadi', 'AdiSoyadi', 'hastaAdi', 'HastaAdi', 'full_name', 'fullName', 'FullName', 'name', 'Name']) ??
    [first, last].filter(Boolean).join(' ');

  const patient = toExternalPatient({
    fullName,
    phone: pick(raw, ['ContactMobile', 'telefon', 'Telefon', 'cep', 'Cep', 'gsm', 'Gsm', 'phone', 'Phone', 'mobile']),
    email: pick(raw, ['email', 'Email', 'eposta', 'EPosta', 'e_posta', 'ContactEmail']),
    nationalId: pick(raw, ['PatientNumber', 'tc', 'TC', 'tckn', 'TCKN', 'tcKimlikNo', 'national_id']),
    birthDate: pick(raw, ['PatientBirthDate', 'dogumTarihi', 'DogumTarihi', 'birth_date', 'birthDate']),
  });
  if (!patient) return null;

  // ID şifreli string; TransferID (örn. 279_5567) klinik içi sabit anahtar.
  const externalId = pick(raw, ['TransferID', 'ID', 'Id', 'id']);
  return {
    externalId: externalId !== null ? String(externalId) : null,
    createdAt: null,
    patient,
  };
}

function drdentesRecord(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const name = String(raw.title || '').trim();
  const normalized = name.toLowerCase();
  if (normalized.startsWith('kapalı') || normalized.startsWith('kapali')) return null;

  const patient = toExternalPatient({
    fullName: name,
    phone: pick(raw, ['cep1', 'telefon']),
  });
  if (!patient) return null;
  return { externalId: null, createdAt: null, patient };
}

// ── Sağlayıcı kayıt defteri ───────────────────────────────────────────────

export const PROVIDERS = {
  dentsoft: {
    id: 'dentsoft',
    label: 'Dentsoft',
    hosts: ['dentsoft.com.tr'],
    matchPatterns: ['https://*.dentsoft.com.tr/*', 'https://clinic.dentsoft.com.tr/*'],
    // Bilinen GET uçları (read-only):
    //   /Patient/SearchList                          → hasta arama JSON dizisi
    //   /Calendar/AppointmentInfo/{EventID}          → tek randevu HTML (PatientID, dosya no)
    //   /Calendar/DoctorList/resourceDayGridMonth/…  → hekim/klinik kaynağı (hasta yok)
    //   /Calendar/NoteList/{date}                    → notlar (çoğu zaman [])
    interceptUrlPatterns: [
      '/Patient/SearchList',
      '/Patient/Index/',
      '/Calendar/AppointmentInfo/',
      '/Patient/.*(Save|Kaydet|Create|Update|Insert|Get|List|Search)',
      '/Calendar/.*(Appointment|Event|List)',
    ],
    // ID sayısal değil; mükerrer önleme TransferID/hash (seen) ile.
    deltaStrategy: 'seen',
    maxPages: 1,
    periodicFetch: fetchPagedJson,
    periodicOptions: {
      path: '/Patient/SearchList',
      tokenStorageKey: null,
      loginPathRegex: '/(login|giris|auth)',
    },
    extractItems: (json) =>
      pickArray(json, [
        'data',
        'Data',
        'items',
        'Items',
        'result',
        'Result',
        'rows',
        'Rows',
        'patients',
        'Patients',
        'hastalar',
        'list',
        'List',
        'aaData',
      ]),
    toRecord: dentsoftRecord,
  },

  drdentes: {
    id: 'drdentes',
    label: 'Dr.DENTES',
    hosts: ['drdentes.com'],
    matchPatterns: ['https://drdentes.com/*', 'https://*.drdentes.com/*'],
    interceptUrlPatterns: ['/ajax\\.php\\?.*randevuSayfasi=1'],
    // Randevu id'leri hasta id'si değildir; geçmiş haftalar gezildiğinde de yeni hasta çıkabilir.
    deltaStrategy: 'seen',
    maxPages: 1,
    periodicFetch: fetchDrDentesAppointments,
    periodicOptions: { daysBack: 1, daysAhead: 14 },
    extractItems: (json) => (Array.isArray(json) ? json : []),
    toRecord: drdentesRecord,
  },
};

export function providerForUrl(url) {
  let hostname;
  try {
    hostname = new URL(url).hostname;
  } catch {
    return null;
  }
  return (
    Object.values(PROVIDERS).find((p) =>
      p.hosts.some((host) => hostname === host || hostname.endsWith(`.${host}`)),
    ) ?? null
  );
}
