/**
 * PMS sağlayıcı tanımları.
 *
 * Alanlar:
 *   hosts, matchPatterns, interceptUrlPatterns, deltaStrategy
 *   periodicFetch (self-contained), enrichItems (opsiyonel), extractItems, toRecord
 */

// ── Dentsoft kart HTML parse ──────────────────────────────────────────────

function parseDentsoftCardHtml(html) {
  const field = (name) => {
    const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    let m = html.match(new RegExp(`name=["']${esc}["'][^>]*value=["']([^"']*)["']`, 'i'));
    if (m?.[1]?.trim()) return m[1].trim();
    m = html.match(new RegExp(`value=["']([^"']*)["'][^>]*name=["']${esc}["']`, 'i'));
    if (m?.[1]?.trim()) return m[1].trim();
    m = html.match(
      new RegExp(`input\\[name=["']${esc}["']\\][\\s\\S]{0,160}?\\.data\\(['"]value['"],\\s*[\\\`]([^\\\`]*)[\\\`]`, 'i'),
    );
    if (m?.[1]?.trim()) return m[1].trim();
    return null;
  };

  const selectVal = (name) => {
    const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const block = html.match(new RegExp(`<select[^>]*name=["']${esc}["'][^>]*>([\\s\\S]*?)<\\/select>`, 'i'));
    if (!block) return null;
    let m = block[1].match(/<option[^>]*selected[^>]*value=["']([^"']*)["']/i);
    if (m?.[1]?.trim()) return m[1].trim();
    m = block[1].match(/<option[^>]*value=["']([^"']*)["'][^>]*selected/i);
    if (m?.[1]?.trim()) return m[1].trim();
    return null;
  };

  const prop = (key) => {
    const m = html.match(new RegExp(`PatientIndex\\.${key}\\s*=\\s*['"]([^'"]*)['"]`, 'i'));
    return m?.[1]?.trim() || null;
  };

  const first = (...vals) => {
    for (const v of vals) {
      if (v !== null && v !== undefined && String(v).trim() !== '') return String(v).trim();
    }
    return null;
  };

  return {
    PatientFirstName: field('PatientFirstName'),
    PatientLastName: field('PatientLastName'),
    PatientNumber: field('PatientNumber'),
    ContactMobile: first(field('ContactMobile'), prop('ContactMobile'), field('ContactPhone')),
    ContactEmail: first(field('ContactEmail'), field('Email'), field('PatientEmail')),
    PatientBirthDate: first(field('PatientBirthDate'), field('BirthDate'), field('DogumTarihi')),
    PatientSex: first(field('PatientSex'), selectVal('PatientSex'), selectVal('Sex')),
    Address: first(field('Address'), field('PatientAddress'), field('Adres')),
    City: first(field('City'), field('PatientCity'), field('Il'), selectVal('City'), selectVal('Il')),
    District: first(field('District'), field('PatientDistrict'), field('Ilce'), selectVal('District'), selectVal('Ilce')),
    Country: first(field('Country'), field('PatientCountry'), field('Ulke'), selectVal('Country'), selectVal('Ulke')),
    Job: first(field('PatientJob'), field('Job'), field('Occupation'), field('Meslek')),
    Nationality: first(field('PatientNationality'), field('Nationality'), field('Uyruk'), selectVal('PatientNationality')),
    BloodGroup: first(field('BloodGroup'), field('PatientBloodGroup'), selectVal('BloodGroup'), selectVal('PatientBloodGroup')),
    FileNo: first(field('FileNo'), field('PatientFileNo'), prop('FileNo')),
    ArchiveID: first(field('ArchiveID'), field('ArchiveNo'), prop('ArchiveID')),
    InsuranceType: first(field('InsuranceType'), selectVal('InsuranceType'), field('PatientInsurance')),
    InsuranceProvider: first(field('InsuranceProvider'), field('CompanyName'), field('AnlasmaliKurum')),
  };
}

// ── Periyodik fetch ───────────────────────────────────────────────────────

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

/** HTML hücre metnini temizle. */
function stripHtmlCell(raw) {
  return String(raw || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

function cellAt(row, index) {
  if (!row || typeof row !== 'object') return '';
  const v = row[String(index)] ?? row[index];
  return stripHtmlCell(v);
}

/** DataTables server-side JSON → özet satırlar + yapılandırılmış ziyaretler. */
function parseDentsoftDataTableJson(json, { kind = 'generic', maxRows = 15 } = {}) {
  const list = Array.isArray(json?.data) ? json.data : Array.isArray(json) ? json : [];
  const rows = [];
  const visits = [];
  for (const row of list) {
    if (rows.length >= maxRows) break;
    if (!row || typeof row !== 'object') continue;

    if (kind === 'appointments') {
      const when = cellAt(row, 2);
      const doctor = cellAt(row, 3);
      const tooth = cellAt(row, 4);
      const procedure = cellAt(row, 5);
      const status = cellAt(row, 6);
      const note = cellAt(row, 9);
      const rawId = String(row['0'] ?? row[0] ?? '').replace(/\D/g, '') || null;
      const parts = [when, doctor, tooth ? `diş ${tooth}` : null, procedure, status, note].filter(Boolean);
      if (parts.length) rows.push(parts.join(' · ').slice(0, 220));
      if (when || procedure) {
        visits.push({
          external_ref: rawId,
          when_text: when || null,
          doctor: doctor || null,
          tooth_hint: tooth || null,
          procedure_raw: procedure || null,
          status_raw: status || null,
          note: note || null,
        });
      }
      continue;
    }

    const parts = [];
    for (let i = 0; i <= 20; i++) {
      const t = cellAt(row, i);
      if (!t) continue;
      if (/^(row_\d+|\d+|0\.00)$/i.test(t)) continue;
      if (/fa-ellipsis|Swal\(|javascript:/i.test(String(row[String(i)] ?? row[i] ?? ''))) continue;
      parts.push(t);
    }
    if (parts.length) rows.push(parts.slice(0, 6).join(' · ').slice(0, 220));
  }
  return { rows, visits };
}

/** Tablo satırlarını özet satırlarına çevir (HTML fallback). */
function parseDentsoftTableRows(html, { maxRows = 12 } = {}) {
  const rows = [];
  const re = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
  let m;
  while ((m = re.exec(html)) !== null && rows.length < maxRows + 4) {
    const cells = [];
    const cellRe = /<t[hd][^>]*>([\s\S]*?)<\/t[hd]>/gi;
    let c;
    while ((c = cellRe.exec(m[1])) !== null) {
      const text = stripHtmlCell(c[1]);
      if (text) cells.push(text);
    }
    if (cells.length < 1) continue;
    const line = cells.join(' · ');
    if (line.length < 2) continue;
    if (/^(tl|tarih|işlem|islem|açıklama|aciklama|tutar|durum|hekim|diş|dis)(\s·\s|$)/i.test(line) && cells.length <= 4) {
      continue;
    }
    rows.push(line.slice(0, 180));
  }
  return rows.slice(0, maxRows);
}

/** Index üst bilgisinden tedavi/ödeme/kalan. */
function parseDentsoftFinanceHeader(html) {
  const pickAmount = (label) => {
    const re = new RegExp(
      `${label}[\\s\\S]{0,120}?<th[^>]*>\\s*([\\d.,\\-]+)\\s*<`,
      'i',
    );
    const m = html.match(re);
    return m?.[1]?.trim() || null;
  };
  return {
    treatmentTotal: pickAmount('Tedavi'),
    paymentTotal: pickAmount('Ödeme'),
    remainingTotal: pickAmount('Kalan'),
  };
}

/** Sayfa HTML içinden DataTable ajax URL çıkar. */
function extractDataTableAjaxUrl(html, baseUrl) {
  if (!html) return null;
  const patterns = [
    /App\.DataTable\(\s*['"]([^'"]+)['"]/i,
    /["']ajax["']\s*:\s*\{\s*["']url["']\s*:\s*['"]([^'"]+)['"]/i,
    /ajax\s*:\s*\{\s*url\s*:\s*['"]([^'"]+)['"]/i,
    /\.dataTable\(\s*\{[\s\S]{0,400}?["']?url["']?\s*:\s*['"]([^'"]+)['"]/i,
  ];
  for (const re of patterns) {
    const m = html.match(re);
    if (m?.[1] && !m[1].includes('{')) {
      try {
        return new URL(m[1], baseUrl).toString();
      } catch {
        /* ignore */
      }
    }
  }
  return null;
}

const DENTSOFT_CLINICAL_TABS = [
  { key: 'appointments', label: 'Randevular', path: (id) => `/Patient/Appointment/${id}`, kind: 'appointments' },
  { key: 'diagnosis', label: 'Teşhis', path: (id) => `/Patient/Dentis/Diagnoz/${id}`, kind: 'generic' },
  { key: 'treatments', label: 'Yapılan tedaviler', path: (id) => `/Patient/Dentis/Treatment/${id}/Done`, kind: 'generic' },
  { key: 'finance', label: 'Finans', path: (id) => `/Patient/Finance/${id}`, kind: 'generic' },
];

async function fetchDentsoftHtml(baseUrl, path, loginRe) {
  const url = new URL(path, baseUrl).toString();
  const res = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'text/html', 'X-Requested-With': 'XMLHttpRequest' },
    redirect: 'follow',
  });
  const finalPath = new URL(res.url).pathname;
  if (res.status === 401 || res.status === 403 || loginRe.test(finalPath)) {
    return { ok: false, reason: 'SESSION_EXPIRED' };
  }
  if (!res.ok) return { ok: false, reason: 'HTTP_ERROR', status: res.status };
  const html = await res.text();
  if (/frmGiris/i.test(html) && /type=["']password["']/i.test(html)) {
    return { ok: false, reason: 'SESSION_EXPIRED' };
  }
  return { ok: true, html };
}

/** DataTables server-side liste (GET, salt okuma). */
async function fetchDentsoftDataTable(baseUrl, ajaxUrlOrPath, loginRe) {
  const candidates = [];
  try {
    const u = new URL(ajaxUrlOrPath, baseUrl);
    if (!u.searchParams.has('draw')) u.searchParams.set('draw', '1');
    if (!u.searchParams.has('start')) u.searchParams.set('start', '0');
    if (!u.searchParams.has('length')) u.searchParams.set('length', '100');
    candidates.push(u.toString());
  } catch {
    return { ok: false, reason: 'BAD_URL' };
  }

  // Aynı path altında sık görülen List türevi
  try {
    const u2 = new URL(ajaxUrlOrPath, baseUrl);
    if (!/\/List\/?$/i.test(u2.pathname)) {
      u2.pathname = `${u2.pathname.replace(/\/$/, '')}/List`;
      u2.searchParams.set('draw', '1');
      u2.searchParams.set('start', '0');
      u2.searchParams.set('length', '100');
      candidates.push(u2.toString());
    }
  } catch {
    /* ignore */
  }

  for (const url of candidates) {
    try {
      const res = await fetch(url, {
        credentials: 'include',
        headers: {
          Accept: 'application/json, text/javascript, */*; q=0.01',
          'X-Requested-With': 'XMLHttpRequest',
        },
        redirect: 'follow',
      });
      const finalPath = new URL(res.url).pathname;
      if (res.status === 401 || res.status === 403 || loginRe.test(finalPath)) {
        return { ok: false, reason: 'SESSION_EXPIRED' };
      }
      if (!res.ok) continue;
      const text = await res.text();
      if (/frmGiris/i.test(text) && /type=["']password["']/i.test(text)) {
        return { ok: false, reason: 'SESSION_EXPIRED' };
      }
      let json;
      try {
        json = JSON.parse(text);
      } catch {
        continue;
      }
      if (json && (Array.isArray(json.data) || Array.isArray(json))) {
        return { ok: true, json, url };
      }
    } catch {
      /* next candidate */
    }
  }
  return { ok: false, reason: 'NOT_JSON' };
}

async function fetchTabRows(baseUrl, tab, patientId, loginRe) {
  const path = tab.path(patientId);
  const pageRes = await fetchDentsoftHtml(baseUrl, path, loginRe);
  if (!pageRes.ok) return pageRes;

  const ajaxFromHtml = extractDataTableAjaxUrl(pageRes.html, baseUrl);
  const ajaxCandidates = [ajaxFromHtml, path].filter(Boolean);

  for (const candidate of ajaxCandidates) {
    const dt = await fetchDentsoftDataTable(baseUrl, candidate, loginRe);
    if (dt.reason === 'SESSION_EXPIRED') return dt;
    if (dt.ok) {
      const parsed = parseDentsoftDataTableJson(dt.json, {
        kind: tab.kind,
        maxRows: tab.key === 'finance' ? 20 : 15,
      });
      if (parsed.rows.length || parsed.visits.length) {
        return { ok: true, rows: parsed.rows, visits: parsed.visits, source: 'datatable' };
      }
    }
  }

  const rows = parseDentsoftTableRows(pageRes.html, { maxRows: tab.key === 'finance' ? 20 : 12 });
  return { ok: true, rows, visits: [], source: rows.length ? 'html' : 'empty' };
}

function mapDentsoftProcedure(raw) {
  const t = String(raw || '').toLowerCase();
  if (/kanal/.test(t)) return 'kanal';
  if (/dolgu/.test(t)) return 'dolgu';
  if (/muayene/.test(t)) return 'muayene';
  if (/kontrol/.test(t)) return 'muayene';
  if (/kron|crown/.test(t)) return 'kron';
  if (/implant/.test(t)) return 'implant';
  if (/k[oö]pr[uü]|bridge/.test(t)) return 'kopru';
  if (/[cç]ekim|extraction/.test(t)) return 'cekim';
  if (/protez/.test(t)) return 'protez';
  if (/veneer|laminate/.test(t)) return 'veneer';
  if (/ortodont/.test(t)) return 'ortodonti';
  if (/temizlik|detertraj|scaling/.test(t)) return 'temizlik';
  if (t.trim()) return 'diger';
  return null;
}

function mapDentsoftVisitStatus(raw) {
  const t = String(raw || '').toLowerCase();
  if (/iptal/.test(t)) return 'cancelled';
  if (/ertelendi|verildi|bekliyor/.test(t)) return 'planned';
  if (/[cç][ıi]kt[ıi]|tamam|geldi|klinikten/.test(t)) return 'completed';
  return 'completed';
}

function normalizeClinicalVisits(visits) {
  if (!Array.isArray(visits)) return [];
  return visits.slice(0, 30).map((v) => ({
    external_ref: v.external_ref ? String(v.external_ref).slice(0, 64) : null,
    when_text: v.when_text ? String(v.when_text).slice(0, 120) : null,
    doctor: v.doctor ? String(v.doctor).slice(0, 120) : null,
    tooth_hint: v.tooth_hint ? String(v.tooth_hint).slice(0, 20) : null,
    procedure_raw: v.procedure_raw ? String(v.procedure_raw).slice(0, 120) : null,
    procedure: mapDentsoftProcedure(v.procedure_raw),
    status: mapDentsoftVisitStatus(v.status_raw),
    note: v.note ? String(v.note).slice(0, 500) : null,
  })).filter((v) => v.when_text || v.procedure_raw || v.note);
}

function buildClinicalNotes({ financeHeader, tabSections }) {
  const parts = ['[Dentsoft]'];
  if (financeHeader?.treatmentTotal || financeHeader?.paymentTotal || financeHeader?.remainingTotal) {
    parts.push(
      `Özet: Tedavi ${financeHeader.treatmentTotal ?? '—'} · Ödeme ${financeHeader.paymentTotal ?? '—'} · Kalan ${financeHeader.remainingTotal ?? '—'}`,
    );
  }
  for (const section of tabSections || []) {
    if (!section.rows?.length) continue;
    parts.push(`--- ${section.label} ---`);
    for (const row of section.rows) parts.push(`• ${row}`);
  }
  if (parts.length <= 1) return null;
  return parts.join('\n').slice(0, 1900);
}

/** SearchList → Index + klinik sekmeleri (randevu/teşhis/tedavi/finans), salt okuma. */
async function enrichDentsoftItems(baseUrl, items, options) {
  if (!Array.isArray(items) || !items.length) return items;

  const loginRe = new RegExp(options.loginPathRegex || '/(login|giris|auth)', 'i');
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const delayMs = Number(options.enrichDelayMs) || 200;
  const max = Math.min(items.length, Number(options.enrichMax) || 25);
  const onlyMissingTc = options.enrichOnlyMissingTc === true;
  const enrichTabs = options.enrichTabs !== false;

  const out = items.slice();
  let enriched = 0;
  for (let i = 0; i < out.length && enriched < max; i++) {
    const item = out[i];
    if (!item?.ID) continue;
    const tcDigits = String(item.PatientNumber || '').replace(/\D/g, '');
    if (onlyMissingTc && tcDigits.length === 11 && item._enrichedFromCard) continue;

    const patientId = encodeURIComponent(String(item.ID));
    try {
      const cardRes = await fetchDentsoftHtml(baseUrl, `/Patient/Index/${patientId}`, loginRe);
      if (!cardRes.ok) {
        if (cardRes.reason === 'SESSION_EXPIRED') break;
        continue;
      }

      const card = parseDentsoftCardHtml(cardRes.html);
      const financeHeader = parseDentsoftFinanceHeader(cardRes.html);
      const tabSections = [];
      let clinicalVisits = [];

      if (enrichTabs) {
        for (const tab of DENTSOFT_CLINICAL_TABS) {
          await sleep(Math.max(80, Math.floor(delayMs / 2)));
          const tabRes = await fetchTabRows(baseUrl, tab, patientId, loginRe);
          if (!tabRes.ok) {
            if (tabRes.reason === 'SESSION_EXPIRED') return out;
            continue;
          }
          if (tabRes.rows?.length) {
            tabSections.push({ key: tab.key, label: tab.label, rows: tabRes.rows });
          }
          if (tab.key === 'appointments' && tabRes.visits?.length) {
            clinicalVisits = normalizeClinicalVisits(tabRes.visits);
          }
        }
      }

      const clinicalNotes = buildClinicalNotes({ financeHeader, tabSections });

      out[i] = {
        ...item,
        PatientFirstName: card.PatientFirstName || item.PatientFirstName,
        PatientLastName: card.PatientLastName || item.PatientLastName,
        PatientNumber: card.PatientNumber || item.PatientNumber,
        ContactMobile: card.ContactMobile || item.ContactMobile,
        ContactEmail: card.ContactEmail || item.ContactEmail,
        PatientBirthDate: card.PatientBirthDate || item.PatientBirthDate,
        PatientSex: card.PatientSex || item.PatientSex,
        Address: card.Address || item.Address,
        City: card.City || item.City,
        District: card.District || item.District,
        Country: card.Country || item.Country,
        PatientJob: card.Job || item.PatientJob,
        PatientNationality: card.Nationality || item.PatientNationality,
        BloodGroup: card.BloodGroup || item.BloodGroup,
        FileNo: card.FileNo || item.FileNo,
        ArchiveID: card.ArchiveID || item.ArchiveID,
        InsuranceType: card.InsuranceType || item.InsuranceType,
        CompanyName: card.InsuranceProvider || item.CompanyName,
        TreatmentTotal: financeHeader.treatmentTotal || item.TreatmentTotal,
        PaymentTotal: financeHeader.paymentTotal || item.PaymentTotal,
        RemainingTotal: financeHeader.remainingTotal || item.RemainingTotal,
        _clinicalNotes: clinicalNotes || item._clinicalNotes,
        _clinicalVisits: clinicalVisits.length ? clinicalVisits : item._clinicalVisits,
        _enrichedFromCard: true,
        _enrichedTabs: tabSections.map((s) => s.key),
      };
      enriched += 1;
    } catch {
      /* ignore */
    }
    if (enriched < max) await sleep(delayMs);
  }
  return out;
}

// ── Normalizasyon ─────────────────────────────────────────────────────────

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

export function toExternalPatient({
  fullName,
  phone,
  email,
  nationalId,
  birthDate,
  insuranceType,
  insuranceProvider,
  notes,
  sex,
  address,
  city,
  district,
  country,
  externalId,
  avatarUrl,
  fileNumber,
  archiveNumber,
  occupation,
  nationality,
  bloodType,
  clinicalVisits,
}) {
  const full_name = clean(fullName, 255);
  if (!full_name || full_name.length < 2) return null;
  const tc = nationalId ? String(nationalId).replace(/\D/g, '') : '';
  const out = {
    full_name,
    phone: cleanPhone(phone),
    email: clean(email, 255)?.toLowerCase() ?? null,
    national_id: tc.length === 11 ? tc : null,
    birth_date: clean(birthDate, 16),
    insurance_type: clean(insuranceType, 20),
    insurance_provider: clean(insuranceProvider, 100),
    notes: clean(notes, 2000),
    sex: clean(sex, 20),
    address: clean(address, 500),
    city: clean(city, 100),
    district: clean(district, 100),
    country: clean(country, 100),
    external_id: clean(externalId, 128),
    avatar_url: clean(avatarUrl, 500),
    file_number: clean(fileNumber, 64),
    archive_number: clean(archiveNumber, 64),
    occupation: clean(occupation, 100),
    nationality: clean(nationality, 100),
    blood_type: clean(bloodType, 20),
  };
  if (Array.isArray(clinicalVisits) && clinicalVisits.length) {
    out.clinical_visits = clinicalVisits.slice(0, 30);
  }
  return out;
}

function mapDentsoftSex(raw) {
  const v = String(raw ?? '').trim().toLowerCase();
  if (!v) return null;
  if (['1', 'f', 'female', 'kadin', 'kadın', 'k'].includes(v)) return 'female';
  if (['0', '2', 'm', 'male', 'erkek', 'e'].includes(v)) return 'male';
  return 'unknown';
}

function mapInsurance(raw) {
  const v = String(raw ?? '').trim().toLowerCase();
  if (!v) return null;
  if (/(sgk|bagkur|ba[gğ]kur|emekli)/i.test(v)) return 'sgk';
  if (/(ozel|özel|private)/i.test(v)) return 'private';
  if (/(karma|mixed)/i.test(v)) return 'mixed';
  if (/(yok|none)/i.test(v)) return 'none';
  return null;
}

function dentsoftRecord(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const first = pick(raw, ['PatientFirstName', 'ad', 'adi', 'Adi', 'firstName', 'FirstName', 'first_name']);
  const last = pick(raw, ['PatientLastName', 'soyad', 'soyadi', 'Soyadi', 'lastName', 'LastName', 'last_name']);
  const fullName =
    pick(raw, ['ad_soyad', 'adSoyad', 'AdSoyad', 'hastaAdi', 'HastaAdi', 'full_name', 'fullName', 'name', 'Name']) ??
    [first, last].filter(Boolean).join(' ');

  const externalId = pick(raw, ['TransferID', 'ID', 'Id', 'id']);
  const age = pick(raw, ['Age', 'age']);
  const company = pick(raw, ['CompanyName', 'companyName', 'InsuranceProvider']);
  const clinical = pick(raw, ['_clinicalNotes', 'ClinicalNotes', 'clinical_notes']);
  const noteParts = [];
  if (age !== null && String(age).trim()) noteParts.push(`Yaş: ${String(age).trim()}`);
  if (company) noteParts.push(`Kurum: ${company}`);
  const treat = pick(raw, ['TreatmentTotal', 'treatment_total']);
  const pay = pick(raw, ['PaymentTotal', 'payment_total']);
  const rem = pick(raw, ['RemainingTotal', 'remaining_total']);
  if (treat || pay || rem) {
    noteParts.push(`Tedavi ${treat ?? '—'} · Ödeme ${pay ?? '—'} · Kalan ${rem ?? '—'}`);
  }
  const baseNotes = noteParts.length ? noteParts.join(' · ') : null;
  const notes = clinical
    ? [baseNotes, clinical].filter(Boolean).join('\n').slice(0, 2000)
    : baseNotes;

  const patient = toExternalPatient({
    fullName,
    phone: pick(raw, ['ContactMobile', 'telefon', 'Telefon', 'cep', 'gsm', 'phone', 'Phone', 'mobile']),
    email: pick(raw, ['ContactEmail', 'email', 'Email', 'eposta', 'EPosta']),
    nationalId: pick(raw, ['PatientNumber', 'tc', 'TC', 'tckn', 'TCKN', 'national_id']),
    birthDate: pick(raw, ['PatientBirthDate', 'dogumTarihi', 'DogumTarihi', 'birth_date', 'birthDate']),
    insuranceType: mapInsurance(pick(raw, ['InsuranceType', 'insurance_type'])),
    insuranceProvider: company,
    notes: notes,
    sex: mapDentsoftSex(pick(raw, ['PatientSex', 'sex', 'Sex', 'cinsiyet'])),
    address: pick(raw, ['Address', 'address', 'Adres', 'adres', 'PatientAddress']),
    city: pick(raw, ['City', 'city', 'Il', 'il', 'PatientCity']),
    district: pick(raw, ['District', 'district', 'Ilce', 'ilce']),
    country: pick(raw, ['Country', 'country', 'Ulke', 'ulke']),
    externalId: externalId !== null ? String(externalId) : null,
    avatarUrl: pick(raw, ['PatientAvatar', 'avatar', 'Avatar', 'avatar_url']),
    fileNumber: pick(raw, ['FileNo', 'file_number', 'DosyaNo']),
    archiveNumber: pick(raw, ['ArchiveID', 'ArchiveNo', 'archive_number']),
    occupation: pick(raw, ['PatientJob', 'Job', 'Occupation', 'Meslek']),
    nationality: pick(raw, ['PatientNationality', 'Nationality', 'Uyruk']),
    bloodType: pick(raw, ['BloodGroup', 'PatientBloodGroup', 'blood_type']),
    clinicalVisits: Array.isArray(raw._clinicalVisits) ? raw._clinicalVisits : null,
  });
  if (!patient) return null;

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
    interceptUrlPatterns: [
      '/Patient/SearchList',
      '/Patient/Index/',
      '/Patient/Appointment/',
      '/Patient/Dentis/Diagnoz/',
      '/Patient/Dentis/Treatment/',
      '/Patient/Finance/',
      '/Calendar/AppointmentInfo/',
      '/Patient/.*(Save|Kaydet|Create|Update|Insert|Get|List|Search)',
      '/Calendar/.*(Appointment|Event|List)',
    ],
    deltaStrategy: 'seen',
    maxPages: 1,
    periodicFetch: fetchPagedJson,
    enrichItems: enrichDentsoftItems,
    periodicOptions: {
      path: '/Patient/SearchList',
      tokenStorageKey: null,
      loginPathRegex: '/(login|giris|auth)',
      enrich: true,
      enrichTabs: true,
      enrichMax: 20,
      enrichDelayMs: 180,
      enrichOnlyMissingTc: false,
    },
    extractItems: (json) =>
      pickArray(json, [
        'data', 'Data', 'items', 'Items', 'result', 'Result', 'rows', 'Rows',
        'patients', 'Patients', 'hastalar', 'list', 'List', 'aaData',
      ]),
    toRecord: dentsoftRecord,
  },

  drdentes: {
    id: 'drdentes',
    label: 'Dr.DENTES',
    hosts: ['drdentes.com'],
    matchPatterns: ['https://drdentes.com/*', 'https://*.drdentes.com/*'],
    interceptUrlPatterns: ['/ajax\\.php\\?.*randevuSayfasi=1'],
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
