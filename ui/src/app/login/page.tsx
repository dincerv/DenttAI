'use client';
import { useState } from 'react';
import { Stethoscope, CheckCircle, AlertCircle } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/Button';

type Status = 'idle' | 'loading' | 'success' | 'error';

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail]           = useState('');
  const [password, setPassword]     = useState('');
  const [clinicCode, setClinicCode] = useState('');
  const [status, setStatus]         = useState<Status>('idle');
  const [errorMsg, setErrorMsg]     = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('loading');
    setErrorMsg('');
    try {
      await login(email, password, clinicCode || undefined);
      setStatus('success');
      // router.push('/dashboard') zaten useAuth içinde çalışıyor
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string }; status?: number } };
      const code = e?.response?.status;
      const detail = e?.response?.data?.detail;

      let msg = 'Bir hata oluştu, tekrar deneyin.';
      if (code === 403 && detail?.toLowerCase().includes('csrf')) {
        msg = 'Güvenlik doğrulaması yenilenemedi. Sayfayı yenileyip tekrar deneyin.';
      } else if (code === 401 || code === 403) {
        msg = 'E-posta veya şifre yanlış.';
      } else if (code === 404) {
        msg = 'Bu e-posta adresine ait hesap bulunamadı.';
      } else if (code === 422 && detail?.includes('birden fazla')) {
        msg = detail; // Backend'in açıklayıcı mesajını göster (klinik kodu iste)
      } else if (code === 422) {
        msg = 'Lütfen tüm alanları doğru doldurun.';
      } else if (detail) {
        msg = detail;
      }
      setErrorMsg(msg);
      setStatus('error');
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-900 to-brand-700 px-4">
      <div className="w-full max-w-md">
        <div className="rounded-2xl bg-white p-8 shadow-2xl">
          {/* Logo */}
          <div className="mb-8 flex flex-col items-center gap-2">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 shadow-lg">
              <Stethoscope className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-slate-800">DentAI Flow</h1>
            <p className="text-sm text-slate-500">Klinik Yönetim Paneli</p>
          </div>

          {/* Durum banner'ları */}
          {status === 'success' && (
            <div className="mb-5 flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
              <CheckCircle className="h-5 w-5 shrink-0 text-green-600" />
              <p className="text-sm font-medium text-green-700">Giriş başarılı! Yönlendiriliyorsunuz…</p>
            </div>
          )}
          {status === 'error' && (
            <div className="mb-5 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
              <AlertCircle className="h-5 w-5 shrink-0 text-red-500" />
              <p className="text-sm font-medium text-red-600">{errorMsg}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5" autoComplete="off">
            <div>
              <label htmlFor="clinicCode" className="mb-1.5 block text-sm font-medium text-slate-700">
                Klinik Kodu <span className="text-xs font-normal text-slate-400">(superadmin için boş bırakılabilir)</span>
              </label>
              <input
                id="clinicCode"
                type="text"
                autoComplete="off"
                maxLength={6}
                value={clinicCode}
                onChange={(e) => setClinicCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                placeholder="A1B2C3"
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-800 tracking-widest font-mono outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
              />
            </div>

            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-slate-700">
                E-posta
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="off"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="hekim@klinik.com"
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-800 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
                Şifre
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-800 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
              />
            </div>

            <Button
              type="submit"
              className="w-full"
              size="lg"
              disabled={status === 'loading' || status === 'success'}
            >
              {status === 'loading' ? 'Giriş yapılıyor…' : status === 'success' ? '✓ Başarılı' : 'Giriş Yap'}
            </Button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-brand-200">
          © {new Date().getFullYear()} DentAI Flow — Tüm hakları saklıdır
        </p>
      </div>
    </main>
  );
}
