/**
 * PatientDetailCard Component
 *
 * Patient profile dengan PatientFeedback Timeline
 * - Hasta bilgileri
 * - Tedavi geçmişi
 * - Post-op feedback timeline (AI şikayetleri)
 * - Severity badges (low/medium/high/critical)
 * - Doctor assignments
 *
 * Features:
 * - Responsive grid layout
 * - Color-coded severity levels
 * - Timeline with dates
 * - Filter by resolved/unresolved
 * - Expand/collapse feedback details
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { getAccessToken } from '@/lib/auth';
import {
  Loader2,
  ChevronDown,
  AlertCircle,
  CheckCircle2,
  Clock,
  User,
  Phone,
  Mail,
  FileText,
} from 'lucide-react';

interface Patient {
  id: string;
  full_name: string;
  phone_number: string;
  email: string;
  date_of_birth?: string;
  gender?: 'male' | 'female' | 'other';
  address?: string;
}

interface PatientFeedback {
  id: string;
  patient_id: string;
  feedback_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  requires_action: boolean;
  channel: string;
  is_resolved: boolean;
  created_at: string;
  resolved_at?: string;
  resolution_notes?: string;
  assigned_to_user_id?: string;
  assigned_doctor_name?: string;
}

interface PatientDetailCardProps {
  patientId: string;
}

const SEVERITY_COLORS = {
  low: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', dot: 'bg-blue-400' },
  medium: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-800', dot: 'bg-yellow-400' },
  high: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-800', dot: 'bg-orange-500' },
  critical: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', dot: 'bg-red-600' },
};

const SEVERITY_LABELS = {
  low: 'Düşük',
  medium: 'Orta',
  high: 'Yüksek',
  critical: 'Kritik',
};

export default function PatientDetailCard({ patientId }: PatientDetailCardProps) {
  const { user } = useAuth();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [feedbacks, setFeedbacks] = useState<PatientFeedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedFeedback, setExpandedFeedback] = useState<string | null>(null);
  const [filterResolved, setFilterResolved] = useState<'all' | 'resolved' | 'unresolved'>('all');

  useEffect(() => {
    fetchData();
  }, [patientId, user?.id]);

  async function fetchData() {
    try {
      setLoading(true);
      const token = getAccessToken();

      if (!token) {
        setLoading(false);
        return;
      }

      // Fetch patient details
      const patientRes = await fetch(`/api/patients/${patientId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (patientRes.ok) {
        const data = await patientRes.json();
        setPatient(data);
      }

      // Fetch patient feedbacks
      const feedbackRes = await fetch(`/api/patient-feedback?patient_id=${patientId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (feedbackRes.ok) {
        const data = await feedbackRes.json();
        const feedbackList: PatientFeedback[] = Array.isArray(data) ? data : data.data || [];
        // Sort by date descending
        setFeedbacks(
          feedbackList.sort(
            (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          )
        );
      }
    } catch (error) {
      console.error('Failed to fetch patient data:', error);
    } finally {
      setLoading(false);
    }
  }

  const filteredFeedbacks = feedbacks.filter((fb) => {
    if (filterResolved === 'resolved') return fb.is_resolved;
    if (filterResolved === 'unresolved') return !fb.is_resolved;
    return true;
  });

  const unresolvedCount = feedbacks.filter((fb) => !fb.is_resolved).length;
  const criticalCount = feedbacks.filter((fb) => fb.severity === 'critical' && !fb.is_resolved).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-900">
        <p>Hasta bilgileri yüklenemedi</p>
      </div>
    );
  }

  const age = patient.date_of_birth
    ? Math.floor((new Date().getTime() - new Date(patient.date_of_birth).getTime()) / (365.25 * 24 * 60 * 60 * 1000))
    : null;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Patient Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-8 py-6">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white">{patient.full_name}</h1>
              <p className="text-blue-100 mt-1">
                {age && `${age} yaşında`}
                {patient.gender && ` • ${patient.gender === 'male' ? 'Erkek' : 'Kadın'}`}
              </p>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-blue-100">Beklemede Geri Bildirim</div>
              <div className="text-2xl font-bold text-white mt-1">{unresolvedCount}</div>
            </div>
          </div>
        </div>

        {/* Contact Info Grid */}
        <div className="grid grid-cols-3 gap-6 p-8 border-b border-gray-200">
          <div className="flex items-start gap-3">
            <Phone className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-gray-600 uppercase">Telefon</p>
              <p className="text-sm text-gray-900 font-medium">{patient.phone_number}</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Mail className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-gray-600 uppercase">E-posta</p>
              <p className="text-sm text-gray-900 font-medium">{patient.email || 'N/A'}</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <User className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-gray-600 uppercase">Adres</p>
              <p className="text-sm text-gray-900 font-medium">{patient.address || 'N/A'}</p>
            </div>
          </div>
        </div>

        {/* Critical Alert */}
        {criticalCount > 0 && (
          <div className="bg-red-50 border-l-4 border-red-600 px-8 py-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <div>
              <p className="font-semibold text-red-900">
                {criticalCount} kritik geri bildirim çözüm bekliyor!
              </p>
              <p className="text-xs text-red-800">Lütfen derhal doktora başvurun</p>
            </div>
          </div>
        )}
      </div>

      {/* Feedback Timeline */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Geri Bildirim Tarihi</h2>
            <p className="text-gray-600 text-sm mt-1">Hastanın tedavi sonrası yaşadığı şikayetler</p>
          </div>

          {/* Filter Tabs */}
          <div className="flex gap-2">
            {(['all', 'resolved', 'unresolved'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setFilterResolved(tab)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  filterResolved === tab
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {tab === 'all' ? 'Tüm' : tab === 'resolved' ? 'Çözüldü' : 'Beklemede'}
              </button>
            ))}
          </div>
        </div>

        {filteredFeedbacks.length > 0 ? (
          <div className="space-y-4">
            {filteredFeedbacks.map((feedback, idx) => {
              const isExpanded = expandedFeedback === feedback.id;
              const colors = SEVERITY_COLORS[feedback.severity];
              const created = new Date(feedback.created_at);

              return (
                <div key={feedback.id} className={`border-l-4 rounded-r-lg overflow-hidden ${colors.border}`}>
                  <button
                    onClick={() =>
                      setExpandedFeedback(isExpanded ? null : feedback.id)
                    }
                    className={`w-full text-left p-4 transition-colors ${colors.bg} hover:opacity-80`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        {/* Timeline Dot */}
                        <div className="flex flex-col items-center">
                          <div className={`w-3 h-3 rounded-full -ml-6 ${colors.dot}`}></div>
                          {idx !== filteredFeedbacks.length - 1 && (
                            <div className="w-0.5 h-8 bg-gray-300 mt-2"></div>
                          )}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`font-bold text-sm ${colors.text}`}>
                              {SEVERITY_LABELS[feedback.severity]}
                            </span>
                            <span className="text-xs text-gray-600">
                              {created.toLocaleDateString('tr-TR', {
                                day: '2-digit',
                                month: 'short',
                                year: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </span>
                            {feedback.is_resolved && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-medium">
                                <CheckCircle2 className="w-3 h-3" />
                                Çözüldü
                              </span>
                            )}
                          </div>

                          <p className={`text-sm mt-2 line-clamp-2 ${colors.text}`}>
                            {feedback.message}
                          </p>

                          {feedback.requires_action && !feedback.is_resolved && (
                            <div className="mt-2 inline-flex items-center gap-1 text-xs text-red-700 font-medium">
                              <AlertCircle className="w-3 h-3" />
                              İşlem gerekli
                            </div>
                          )}
                        </div>
                      </div>

                      <ChevronDown
                        className={`w-5 h-5 flex-shrink-0 transition-transform text-gray-600 ${
                          isExpanded ? 'rotate-180' : ''
                        }`}
                      />
                    </div>
                  </button>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className={`p-4 border-t ${colors.border} bg-white`}>
                      <div className="space-y-3">
                        <div>
                          <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                            Tam Mesaj
                          </p>
                          <p className="text-sm text-gray-900">{feedback.message}</p>
                        </div>

                        {feedback.assigned_doctor_name && (
                          <div>
                            <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                              Atanan Doktor
                            </p>
                            <p className="text-sm text-gray-900">{feedback.assigned_doctor_name}</p>
                          </div>
                        )}

                        {feedback.resolution_notes && (
                          <div>
                            <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                              Çözüm Notları
                            </p>
                            <p className="text-sm text-gray-900 bg-gray-50 p-2 rounded">
                              {feedback.resolution_notes}
                            </p>
                          </div>
                        )}

                        <div className="grid grid-cols-2 gap-3 text-xs">
                          <div>
                            <p className="font-semibold text-gray-600">Kanal</p>
                            <p className="text-gray-900 capitalize">{feedback.channel}</p>
                          </div>
                          <div>
                            <p className="font-semibold text-gray-600">Tür</p>
                            <p className="text-gray-900 capitalize">{feedback.feedback_type}</p>
                          </div>
                          {feedback.resolved_at && (
                            <div>
                              <p className="font-semibold text-gray-600">Çözüm Tarihi</p>
                              <p className="text-gray-900">
                                {new Date(feedback.resolved_at).toLocaleDateString('tr-TR')}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-600 font-medium">Geri bildirim yok</p>
            <p className="text-gray-500 text-sm mt-1">
              {filterResolved === 'unresolved'
                ? 'Tüm geri bildirimler çözüldü'
                : 'Bu hastadan henüz geri bildirim alınmamış'}
            </p>
          </div>
        )}
      </div>

      {/* Stats Summary */}
      {feedbacks.length > 0 && (
        <div className="grid grid-cols-4 gap-4">
          {([
            { label: 'Toplam Geri Bildirim', value: feedbacks.length, color: 'blue' },
            { label: 'Çözült', value: feedbacks.filter((f) => f.is_resolved).length, color: 'green' },
            { label: 'Beklemede', value: unresolvedCount, color: 'yellow' },
            { label: 'Kritik', value: criticalCount, color: 'red' },
          ] as const).map(({ label, value, color }) => (
            <div
              key={label}
              className={`bg-${color}-50 border border-${color}-200 rounded-lg p-4 text-center`}
            >
              <p className={`text-2xl font-bold text-${color}-900`}>{value}</p>
              <p className={`text-xs font-medium text-${color}-700 mt-1`}>{label}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
