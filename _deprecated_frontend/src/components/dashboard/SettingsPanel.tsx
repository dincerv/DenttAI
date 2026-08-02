/**
 * SettingsPanel Component
 *
 * Klinik ayarları: Post-Op Follow-Up intervals, Doctor Emergency Alerts toggle
 * 
 * Features:
 * - Post-op followup interval configuration (days)
 * - Doctor WhatsApp alert toggle
 * - Form validation
 * - Loading/error states
 * - Toast notifications
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { getAccessToken } from '@/lib/auth';
import { Bell, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

interface ClinicSettings {
  id: string;
  clinic_id: string;
  is_whatsapp_enabled: boolean;
  whatsapp_business_account_id?: string | null;
  whatsapp_phone_number_id?: string | null;
  post_op_followup_intervals: {
    enabled: boolean;
    interval_days: number;
    reminder_message_template: string;
  };
}

interface DoctorSettings {
  id: string;
  doctor_id: string;
  receive_emergency_alerts: boolean;
  preferred_notification_channel: 'whatsapp' | 'sms' | 'email';
  timezone: string;
}

interface Toast {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
}

export default function SettingsPanel() {
  const { user } = useAuth();
  const [clinicSettings, setClinicSettings] = useState<ClinicSettings | null>(null);
  const [doctorSettings, setDoctorSettings] = useState<DoctorSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Form state
  const [followupDays, setFollowupDays] = useState(1);
  const [followupEnabled, setFollowupEnabled] = useState(true);
  const [whatsappBusinessAccountId, setWhatsappBusinessAccountId] = useState('');
  const [whatsappPhoneNumberId, setWhatsappPhoneNumberId] = useState('');
  const [emergencyAlerts, setEmergencyAlerts] = useState(false);
  const [notificationChannel, setNotificationChannel] = useState<'whatsapp' | 'sms' | 'email'>('whatsapp');

  useEffect(() => {
    fetchSettings();
  }, [user?.id]);

  const addToast = (type: Toast['type'], message: string) => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  };

  async function fetchSettings() {
    try {
      setLoading(true);
      const token = getAccessToken();

      if (!token) {
        setLoading(false);
        return;
      }

      // Fetch clinic settings
      const clinicRes = await fetch('/api/clinic-settings', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (clinicRes.ok) {
        const clinic = await clinicRes.json();
        setClinicSettings(clinic);
        setFollowupEnabled(clinic.post_op_followup_intervals?.enabled ?? true);
        setFollowupDays(clinic.post_op_followup_intervals?.interval_days ?? 1);
        setWhatsappBusinessAccountId(clinic.whatsapp_business_account_id ?? '');
        setWhatsappPhoneNumberId(clinic.whatsapp_phone_number_id ?? '');
      }

      // Fetch doctor settings
      const doctorRes = await fetch('/api/doctor-settings', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (doctorRes.ok) {
        const doctor = await doctorRes.json();
        setDoctorSettings(doctor);
        setEmergencyAlerts(doctor.receive_emergency_alerts ?? false);
        setNotificationChannel(doctor.preferred_notification_channel ?? 'whatsapp');
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error);
      addToast('error', 'Ayarlar yüklenemedi');
    } finally {
      setLoading(false);
    }
  }

  async function saveClinicSettings() {
    try {
      setSaving(true);
      const token = getAccessToken();
      if (!token) return;
      const response = await fetch('/api/clinic-settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          is_whatsapp_enabled: true,
          whatsapp_business_account_id: whatsappBusinessAccountId.trim() || null,
          whatsapp_phone_number_id: whatsappPhoneNumberId.trim() || null,
          post_op_followup_intervals: {
            enabled: followupEnabled,
            interval_days: followupDays,
            reminder_message_template: 'default',
          },
        }),
      });

      if (response.ok) {
        const updated = await response.json();
        setClinicSettings(updated);
        addToast('success', 'Klinik ayarları kaydedildi');
      } else {
        addToast('error', 'Klinik ayarları kaydedilemedi');
      }
    } catch (error) {
      console.error('Failed to save clinic settings:', error);
      addToast('error', 'Bir hata oluştu');
    } finally {
      setSaving(false);
    }
  }

  async function saveDoctorSettings() {
    try {
      setSaving(true);
      const token = getAccessToken();
      if (!token) return;
      const response = await fetch('/api/doctor-settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          receive_emergency_alerts: emergencyAlerts,
          preferred_notification_channel: notificationChannel,
        }),
      });

      if (response.ok) {
        const updated = await response.json();
        setDoctorSettings(updated);
        addToast('success', 'Hekim ayarları kaydedildi');
      } else {
        addToast('error', 'Hekim ayarları kaydedilemedi');
      }
    } catch (error) {
      console.error('Failed to save doctor settings:', error);
      addToast('error', 'Bir hata oluştu');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Ayarlar</h1>
        <p className="text-gray-600 mt-2">Klinik ve hekim ayarlarını yönet</p>
      </div>

      {/* Toasts */}
      <div className="fixed top-4 right-4 space-y-2 z-50">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg animate-in fade-in slide-in-from-right-4 ${
              toast.type === 'success'
                ? 'bg-green-50 text-green-800 border border-green-200'
                : toast.type === 'error'
                ? 'bg-red-50 text-red-800 border border-red-200'
                : 'bg-blue-50 text-blue-800 border border-blue-200'
            }`}
          >
            {toast.type === 'success' && <CheckCircle2 className="w-5 h-5" />}
            {toast.type === 'error' && <AlertCircle className="w-5 h-5" />}
            {toast.message}
          </div>
        ))}
      </div>

      {/* Clinic Settings Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Klinik Ayarları</h2>
          <p className="text-gray-600 text-sm mt-1">Tedavi sonrası takip ve klinik WhatsApp gönderici konfigürasyonu</p>
        </div>

        <div className="space-y-6">
          {/* Followup Enable Toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div>
              <label className="block text-sm font-semibold text-gray-900">
                Tedavi Sonrası Takip
              </label>
              <p className="text-xs text-gray-600 mt-1">
                Hastalar otomatik takip mesajı alacak (WhatsApp)
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={followupEnabled}
                onChange={(e) => setFollowupEnabled(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {/* Followup Days Input */}
          {followupEnabled && (
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Takip Süresi (Gün)
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min="1"
                  max="30"
                  value={followupDays}
                  onChange={(e) => setFollowupDays(parseInt(e.target.value))}
                  className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                />
                <div className="bg-blue-100 text-blue-900 px-4 py-2 rounded-lg font-semibold min-w-[60px] text-center">
                  {followupDays} gün
                </div>
              </div>
              <p className="text-xs text-gray-600 mt-2">
                Tedavi gününden {followupDays} gün sonra hastaya takip mesajı gönderilir
              </p>
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                WhatsApp Business Account ID
              </label>
              <input
                type="text"
                value={whatsappBusinessAccountId}
                onChange={(e) => setWhatsappBusinessAccountId(e.target.value)}
                placeholder="Örn. 123456789012345"
                className="block w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              />
              <p className="text-xs text-gray-600 mt-2">
                Bu kliniğin Meta Business hesabı. Boş bırakılırsa sistem global ayarı kullanır.
              </p>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                WhatsApp Phone Number ID
              </label>
              <input
                type="text"
                value={whatsappPhoneNumberId}
                onChange={(e) => setWhatsappPhoneNumberId(e.target.value)}
                placeholder="Örn. 987654321098765"
                className="block w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              />
              <p className="text-xs text-gray-600 mt-2">
                Hastalara gidecek mesajların çıkacağı klinik numarasının Meta Phone Number ID değeri.
              </p>
            </div>
          </div>

          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex gap-3">
              <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium">Gönderici Mantığı</p>
                <p className="mt-1 text-xs">
                  Klinik numarası girilirse bu klinik kendi WhatsApp Business sender'ını kullanır. Boş bırakılırsa sistem env içindeki ortak sender'a geri düşer.
                </p>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="pt-4 border-t border-gray-200">
            <button
              onClick={saveClinicSettings}
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Kaydet
            </button>
          </div>
        </div>
      </div>

      {/* Doctor Settings Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Bell className="w-6 h-6 text-orange-500" />
            Hekim Uyarıları
          </h2>
          <p className="text-gray-600 text-sm mt-1">Acil durum bildirimlerini yönet</p>
        </div>

        <div className="space-y-6">
          {/* Emergency Alerts Toggle */}
          <div className="flex items-center justify-between p-4 bg-orange-50 rounded-lg border border-orange-200">
            <div>
              <label className="block text-sm font-semibold text-gray-900">
                Acil Durum Bildirimleri
              </label>
              <p className="text-xs text-gray-600 mt-1">
                Hastadan gelen acil şikayetler için WhatsApp bildirimi al
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={emergencyAlerts}
                onChange={(e) => setEmergencyAlerts(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-orange-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-600"></div>
            </label>
          </div>

          {/* Notification Channel Select */}
          {emergencyAlerts && (
            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Bildirim Kanalı
              </label>
              <select
                value={notificationChannel}
                onChange={(e) => setNotificationChannel(e.target.value as any)}
                className="block w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none"
              >
                <option value="whatsapp">WhatsApp (Önerilen)</option>
                <option value="sms">SMS</option>
                <option value="email">E-posta</option>
              </select>
              <p className="text-xs text-gray-600 mt-2">
                Acil bildirimler seçilen kanal üzerinden iletilir
              </p>
            </div>
          )}

          {/* Info Box */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex gap-3">
              <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium">Acil Durum Tanımı:</p>
                <ul className="mt-2 space-y-1 text-xs">
                  <li>• Aşırı kanama</li>
                  <li>• Şiddetli ağrı</li>
                  <li>• Alerji belirtileri</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="pt-4 border-t border-gray-200">
            <button
              onClick={saveDoctorSettings}
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-orange-600 text-white font-medium rounded-lg hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Kaydet
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
