'use client';
import { useEffect, useState } from 'react';
import { usersApi, tenantsApi } from '@/lib/api-client';
import { ClinicUser } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';
import {
  ShieldCheck, UserPlus, Pencil, Trash2, X, Check, Eye, EyeOff, KeyRound, Settings2,
} from 'lucide-react';

const ROLE_OPTIONS = ['owner', 'doctor', 'assistant'];
const ROLE_LABELS: Record<string, string> = {
  owner: 'Klinik Sahibi',
  doctor: 'Doktor',
  assistant: 'Asistan',
};
const ROLE_COLORS: Record<string, string> = {
  owner:        'bg-purple-100 text-purple-700',
  doctor:       'bg-blue-100 text-blue-700',
  assistant:    'bg-green-100 text-green-700',
};

// ── Module/page definitions for permission editor ──
const ALL_PAGES = [
  { key: 'dashboard',    label: 'Dashboard',    icon: '📊' },
  { key: 'appointments', label: 'Randevular',   icon: '📅' },
  { key: 'appointments_write', label: 'Randevu Değişiklikleri', icon: '✍️' },
  { key: 'waitlist',     label: 'Bekleme Listesi', icon: '⏳' },
  { key: 'inventory',    label: 'Depo',         icon: '📦' },
  { key: 'permissions',  label: 'Yetkiler',     icon: '🔒' },
];

/* ─── Edit Permissions Modal ──────────────────────────── */
function EditPermissionsModal({
  user,
  onClose,
  onSaved,
}: {
  user: ClinicUser;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [pages, setPages] = useState<string[]>(user.allowed_pages ?? []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function togglePage(key: string) {
    setPages((prev) =>
      prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key],
    );
  }

  function selectAll() {
    setPages(ALL_PAGES.map((p) => p.key));
  }

  function clearAll() {
    setPages([]);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await usersApi.updatePermissions(user.id, pages);
      onSaved();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Yetkiler güncellenemedi.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings2 className="h-5 w-5 text-brand-600" />
            <h2 className="text-lg font-semibold text-gray-900">Yetki Düzenle</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-4 rounded-lg bg-gray-50 px-3 py-2">
          <p className="text-sm text-gray-600">
            <span className="font-medium">{user.full_name}</span>
            <span className="ml-2 inline-flex rounded-full px-2 py-0.5 text-xs font-medium">
              {ROLE_LABELS[user.role] ?? user.role}
            </span>
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Kullanıcının erişebileceği sayfaları seçin.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          {/* Quick actions */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={selectAll}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
            >
              Tümünü Seç
            </button>
            <button
              type="button"
              onClick={clearAll}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
            >
              Tümünü Kaldır
            </button>
          </div>

          {/* Page toggles */}
          <div className="space-y-2">
            {ALL_PAGES.map((page) => {
              const isChecked = pages.includes(page.key);
              return (
                <label
                  key={page.key}
                  className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 transition-colors ${
                    isChecked
                      ? 'border-brand-300 bg-brand-50'
                      : 'border-gray-200 bg-white hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => togglePage(page.key)}
                    className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                  />
                  <span className="text-lg">{page.icon}</span>
                  <span className="text-sm font-medium text-gray-900">{page.label}</span>
                  {page.key === 'permissions' && (
                    <span className="ml-auto rounded bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                      YÖNETİCİ
                    </span>
                  )}
                </label>
              );
            })}
          </div>

          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >
              İptal
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {loading ? 'Kaydediliyor…' : 'Yetkileri Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── Change Password Modal ─────────────────────────────── */
function ChangePasswordModal({
  user,
  onClose,
}: {
  user: ClinicUser;
  onClose: () => void;
}) {
  // Şifreler ayrı state'lerde, hiçbir zaman URL / log'a düşmüyor
  const [pwd, setPwd]         = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPwd, setShowPwd]         = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [done, setDone]       = useState(false);

  // Modal kapanırken state'leri temizle
  function handleClose() {
    setPwd(''); setConfirm('');
    onClose();
  }

  function validate(): string | null {
    if (pwd.length < 8)          return 'Şifre en az 8 karakter olmalıdır.';
    if (!/[A-Z]/.test(pwd))      return 'Şifre en az bir büyük harf içermelidir.';
    if (!/[a-z]/.test(pwd))      return 'Şifre en az bir küçük harf içermelidir.';
    if (!/[0-9]/.test(pwd))      return 'Şifre en az bir rakam içermelidir.';
    if (pwd !== confirm)         return 'Şifreler eşleşmiyor.';
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }
    setLoading(true);
    setError('');
    try {
      await usersApi.changePassword(user.id, pwd);
      // Plain-text Şifreyi state'ten hemen temizle
      setPwd(''); setConfirm('');
      setDone(true);
    } catch (ex: unknown) {
      // Sunucu hatasını göster ama içeriği şifre hakkında detay vermez
      const msg = (ex as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Şifre değiştirilemedi.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-brand-600" />
            <h2 className="text-lg font-semibold text-gray-900">Şifre Sıfırla</h2>
          </div>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>

        <p className="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600">
          <span className="font-medium">{user.full_name}</span> adlı kullanıcının şifresi sıfırlanıyor.
        </p>

        {done ? (
          <div className="space-y-4">
            <div className="rounded-lg bg-green-50 px-4 py-3 text-sm font-medium text-green-700">
              ✓ Şifre başarıyla güncellendi.
            </div>
            <button onClick={handleClose} className="w-full rounded-lg bg-brand-600 py-2 text-sm font-medium text-white hover:bg-brand-700">
              Kapat
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4" autoComplete="off">
            {/* autoComplete=off → tarayıcı şifre öneri/kaydini engeller */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Yeni Şifre</label>
              <div className="relative">
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={pwd}
                  onChange={(e) => setPwd(e.target.value)}
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Min. 8 karakter, büyük+küçük+rakam"
                />
                <button type="button" onClick={() => setShowPwd(v => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Şifre Tekrar</label>
              <div className="relative">
                <input
                  type={showConfirm ? 'text' : 'password'}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Yeni şifreyi tekrar girin"
                />
                <button type="button" onClick={() => setShowConfirm(v => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Güç göstergesi */}
            <PasswordStrengthBar password={pwd} />

            {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={handleClose}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
                İptal
              </button>
              <button type="submit" disabled={loading}
                className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
                {loading ? 'Kaydediliyor…' : 'Şifreyi Kaydet'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

/** Görsel şifre güç göstergesi — değeri hiçbir yere iletmez */
function PasswordStrengthBar({ password }: { password: string }) {
  const score = [
    password.length >= 8,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /[0-9]/.test(password),
    /[^A-Za-z0-9]/.test(password), // özel karakter bonus
  ].filter(Boolean).length;

  const colors = ['bg-red-400', 'bg-red-400', 'bg-orange-400', 'bg-yellow-400', 'bg-green-500'];
  const labels = ['', 'Zayıf', 'Zayıf', 'Orta', 'Güçlü', 'Çok Güçlü'];

  if (!password) return null;
  return (
    <div className="space-y-1">
      <div className="flex gap-1">
        {[1,2,3,4,5].map(i => (
          <div key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${
            i <= score ? colors[score - 1] : 'bg-gray-200'
          }`} />
        ))}
      </div>
      <p className={`text-xs ${score <= 2 ? 'text-red-500' : score === 3 ? 'text-yellow-600' : 'text-green-600'}`}>
        {labels[score]}
      </p>
    </div>
  );
}
/* ─── Create User Modal ─────────────────────────────── */
function CreateUserModal({
  onClose,
  onCreated,
  clinicSlug,
}: {
  onClose: () => void;
  onCreated: () => void;
  clinicSlug: string;
}) {
  const [emailPrefix, setEmailPrefix] = useState('');
  const [form, setForm] = useState({ full_name: '', password: '', role: 'doctor' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPwd, setShowPwd] = useState(false);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!emailPrefix || !form.full_name || !form.password) {
      setError('Tüm alanlar zorunludur.');
      return;
    }
    if (form.password.length < 8) {
      setError('Şifre en az 8 karakter olmalıdır.');
      return;
    }
    const email = `${emailPrefix}@${clinicSlug}`;
    setLoading(true);
    setError('');
    try {
      await usersApi.create({ ...form, email });
      onCreated();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Kullanıcı oluşturulamadı.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Yeni Kullanıcı Ekle</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submit} autoComplete="off" className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Ad Soyad</label>
            <input
              type="text"
              autoComplete="off"
              value={form.full_name}
              onChange={(e) => set('full_name', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Doktor Adı"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">E-posta</label>
            <div className="flex items-center overflow-hidden rounded-lg border border-gray-300 focus-within:ring-2 focus-within:ring-brand-500">
              <input
                type="text"
                autoComplete="off"
                name={`ep_${Date.now()}`}
                value={emailPrefix}
                onChange={(e) => setEmailPrefix(e.target.value.replace(/[@\s]/g, '').toLowerCase())}
                onFocus={(e) => { if (e.target.value && !emailPrefix) { setEmailPrefix(''); } }}
                className="flex-1 px-3 py-2 text-sm focus:outline-none"
                placeholder="kullanici.adi"
              />
              <span className="bg-gray-50 border-l border-gray-300 px-3 py-2 text-sm text-gray-500 select-none whitespace-nowrap">
                @{clinicSlug || '...'}
              </span>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Şifre</label>
            <div className="relative">
              <input
                type={showPwd ? 'text' : 'password'}
                value={form.password}
                onChange={(e) => set('password', e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Min. 8 karakter"
              />
              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Rol</label>
            <select
              value={form.role}
              onChange={(e) => set('role', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>{ROLE_LABELS[r]}</option>
              ))}
            </select>
          </div>

          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
              İptal
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {loading ? 'Kaydediliyor…' : 'Kullanıcı Oluştur'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── Edit Role Modal ───────────────────────────────── */
function EditRoleModal({
  user,
  onClose,
  onSaved,
}: {
  user: ClinicUser;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [role, setRole] = useState(user.role);
  const [fullName, setFullName] = useState(user.full_name);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await usersApi.update(user.id, { role, full_name: fullName });
      onSaved();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Güncelleme başarısız.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Kullanıcıyı Düzenle</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Ad Soyad</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Rol</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>{ROLE_LABELS[r]}</option>
              ))}
            </select>
          </div>
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
              İptal
            </button>
            <button type="submit" disabled={loading} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60">
              {loading ? 'Kaydediliyor…' : 'Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────────── */
export default function PermissionsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<ClinicUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState<ClinicUser | null>(null);
  const [pwdUser, setPwdUser]   = useState<ClinicUser | null>(null);
  const [permUser, setPermUser] = useState<ClinicUser | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [clinicSlug, setClinicSlug] = useState('');

  // Guard: only users with permissions access
  const hasPermAccess = user?.role === 'owner' || user?.role === 'super_admin' ||
    (user?.allowed_pages ?? []).includes('permissions');
  useEffect(() => {
    if (user && !hasPermAccess) {
      router.replace('/dashboard');
    }
  }, [user, hasPermAccess, router]);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const res = await usersApi.list();
      const data = res.data;
      const all: ClinicUser[] = Array.isArray(data) ? (data as ClinicUser[]) : ((data as { items: ClinicUser[] }).items ?? []);
      setUsers(all.filter((u) => u.role !== 'super_admin'));
    } catch {
      setError('Kullanıcılar yüklenemedi.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (user?.clinic_email_domain) {
      setClinicSlug(user.clinic_email_domain);
    } else {
      tenantsApi.getMyClinic().then(r => setClinicSlug(r.data.email_domain || r.data.slug || '')).catch(() => {});
    }
  }, [user]);

  async function toggleActive(u: ClinicUser) {
    if (u.id === user?.id) return; // cannot deactivate self
    setTogglingId(u.id);
    try {
      await usersApi.update(u.id, { is_active: !u.is_active });
      await load();
    } catch {
      setError('Durum güncellenemedi.');
    } finally {
      setTogglingId(null);
    }
  }

  async function deleteUser(u: ClinicUser) {
    if (u.id === user?.id) return;
    if (!confirm(`"${u.full_name}" kullanıcısını silmek istediğinize emin misiniz?`)) return;
    setDeletingId(u.id);
    try {
      await usersApi.remove(u.id);
      await load();
    } catch {
      setError('Kullanıcı silinemedi.');
    } finally {
      setDeletingId(null);
    }
  }

  if (!hasPermAccess) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100">
            <ShieldCheck className="h-5 w-5 text-purple-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Yetkiler</h1>
            <p className="text-sm text-gray-500">Klinik kullanıcılarını ve erişim yetkilerini yönetin</p>
          </div>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          <UserPlus className="h-4 w-4" />
          Yeni Kullanıcı Ekle
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Kullanıcı</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">E-posta</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Rol</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Erişim</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Durum</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Kayıt Tarihi</th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">İşlem</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="py-10 text-center text-sm text-gray-500">Yükleniyor…</td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-10 text-center text-sm text-gray-400">Henüz kullanıcı yok.</td>
              </tr>
            ) : (
              users.map((u) => {
                const isSelf = u.id === user?.id;
                const roleBadge = ROLE_COLORS[u.role] ?? 'bg-gray-100 text-gray-700';
                return (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-brand-700 text-xs font-bold">
                          {u.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)}
                        </div>
                        <span className="text-sm font-medium text-gray-900">
                          {u.full_name}
                          {isSelf && <span className="ml-1 text-xs text-gray-400">(siz)</span>}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${roleBadge}`}>
                        {ROLE_LABELS[u.role] ?? u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(u.allowed_pages ?? []).map((p) => {
                          const pageDef = ALL_PAGES.find((ap) => ap.key === p);
                          return (
                            <span
                              key={p}
                              className="inline-flex items-center gap-0.5 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600"
                              title={pageDef?.label ?? p}
                            >
                              {pageDef?.icon ?? '📄'} {pageDef?.label ?? p}
                            </span>
                          );
                        })}
                        {(!u.allowed_pages || u.allowed_pages.length === 0) && (
                          <span className="text-xs text-gray-300">—</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        disabled={isSelf || togglingId === u.id}
                        onClick={() => toggleActive(u)}
                        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                          u.is_active
                            ? 'bg-green-100 text-green-700 hover:bg-green-200'
                            : 'bg-red-100 text-red-700 hover:bg-red-200'
                        }`}
                        title={isSelf ? 'Kendi hesabınızı devre dışı bırakamazsınız' : undefined}
                      >
                        {u.is_active
                          ? <><Check className="h-3 w-3" /> Aktif</>
                          : <><X className="h-3 w-3" /> Pasif</>}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(u.created_at).toLocaleDateString('tr-TR')}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          disabled={isSelf || u.role === 'owner'}
                          onClick={() => setPermUser(u)}
                          className="rounded p-1.5 text-gray-400 hover:bg-purple-50 hover:text-purple-600 disabled:opacity-30"
                          title="Yetkileri Düzenle"
                        >
                          <Settings2 className="h-4 w-4" />
                        </button>
                        <button
                          disabled={isSelf}
                          onClick={() => setPwdUser(u)}
                          className="rounded p-1.5 text-gray-400 hover:bg-blue-50 hover:text-blue-600 disabled:opacity-30"
                          title="Şifre Sıfırla"
                        >
                          <KeyRound className="h-4 w-4" />
                        </button>
                        <button
                          disabled={isSelf}
                          onClick={() => setEditUser(u)}
                          className="rounded p-1.5 text-gray-400 hover:bg-amber-50 hover:text-amber-600 disabled:opacity-30"
                          title="Düzenle"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          disabled={isSelf || deletingId === u.id}
                          onClick={() => deleteUser(u)}
                          className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-30"
                          title="Sil"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Summary cards */}
      {!loading && users.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {ROLE_OPTIONS.map((r) => {
            const count = users.filter((u) => u.role === r && u.is_active).length;
            return (
              <div key={r} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{ROLE_LABELS[r]}</p>
                <p className="mt-1 text-2xl font-bold text-gray-900">{count}</p>
                <p className="text-xs text-gray-400">aktif kullanıcı</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Modals */}
      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={load}
          clinicSlug={clinicSlug}
        />
      )}
      {editUser && (
        <EditRoleModal
          user={editUser}
          onClose={() => setEditUser(null)}
          onSaved={load}
        />
      )}
      {pwdUser && (
        <ChangePasswordModal
          user={pwdUser}
          onClose={() => setPwdUser(null)}
        />
      )}
      {permUser && (
        <EditPermissionsModal
          user={permUser}
          onClose={() => setPermUser(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}
