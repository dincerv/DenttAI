/**
 * SmartCalendar Component
 *
 * Interactive calendar with AI-filled appointment detection
 * - AI-filled appointments show animated pulse effect
 * - Color-coded by status
 * - Click to view details
 * - Month/week/day navigation
 *
 * Features:
 * - Tailwind animate-pulse for AI appointments
 * - Status badges (scheduled, confirmed, completed, cancelled)
 * - Responsive grid layout
 * - Doctor info + patient name
 */

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { getAccessToken } from '@/lib/auth';
import { ChevronLeft, ChevronRight, Loader2, Sparkles } from 'lucide-react';

interface Appointment {
  id: string;
  appointment_date: string;
  doctor_name: string;
  patient_name: string;
  treatment_name: string;
  status: 'scheduled' | 'confirmed' | 'completed' | 'cancelled';
  is_auto_filled_by_ai: boolean;
  ai_mutation_score?: number;
}

interface DayAppointments {
  date: Date;
  appointments: Appointment[];
}

const MONTHS = [
  'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
  'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'
];

const WEEKDAYS = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'];

const STATUS_COLORS = {
  scheduled: 'bg-blue-50 border-blue-200 text-blue-900',
  confirmed: 'bg-green-50 border-green-200 text-green-900',
  completed: 'bg-gray-50 border-gray-200 text-gray-900',
  cancelled: 'bg-red-50 border-red-200 text-red-900 line-through',
};

const STATUS_LABELS = {
  scheduled: 'Planlandı',
  confirmed: 'Onaylı',
  completed: 'Tamamlandı',
  cancelled: 'İptal',
};

export default function SmartCalendar() {
  const { user } = useAuth();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  useEffect(() => {
    fetchAppointments();
  }, [user?.id, year, month]);

  async function fetchAppointments() {
    try {
      setLoading(true);
      const token = getAccessToken();
      if (!token) {
        setLoading(false);
        return;
      }
      const startDate = new Date(year, month, 1);
      const endDate = new Date(year, month + 1, 0);

      const response = await fetch(
        `/api/appointments?start_date=${startDate.toISOString()}&end_date=${endDate.toISOString()}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setAppointments(Array.isArray(data) ? data : data.data || []);
      }
    } catch (error) {
      console.error('Failed to fetch appointments:', error);
    } finally {
      setLoading(false);
    }
  }

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDayOfMonth = new Date(year, month, 1).getDay();

  const calendarDays = useMemo(() => {
    const days: (Date | null)[] = [];

    // Empty cells before first day
    for (let i = 0; i < firstDayOfMonth; i++) {
      days.push(null);
    }

    // Days of month
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(new Date(year, month, i));
    }

    return days;
  }, [year, month, daysInMonth, firstDayOfMonth]);

  const getAppointmentsForDay = (date: Date | null): Appointment[] => {
    if (!date) return [];
    return appointments.filter((appt) => {
      const apptDate = new Date(appt.appointment_date);
      return (
        apptDate.getDate() === date.getDate() &&
        apptDate.getMonth() === date.getMonth() &&
        apptDate.getFullYear() === date.getFullYear()
      );
    });
  };

  const previousMonth = () => {
    setCurrentDate(new Date(year, month - 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1));
  };

  const today = new Date();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Randevu Takvimi</h1>
        <p className="text-gray-600 mt-2">Tüm randevuları görüntüle ve yönet</p>
      </div>

      <div className="grid grid-cols-3 gap-8">
        {/* Calendar */}
        <div className="col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          {/* Month Header */}
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
            <button
              onClick={previousMonth}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ChevronLeft className="w-5 h-5 text-gray-700" />
            </button>

            <h2 className="text-xl font-bold text-gray-900">
              {MONTHS[month]} {year}
            </h2>

            <button
              onClick={nextMonth}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ChevronRight className="w-5 h-5 text-gray-700" />
            </button>
          </div>

          {/* Weekday Headers */}
          <div className="grid grid-cols-7 gap-2 mb-2">
            {WEEKDAYS.map((day) => (
              <div key={day} className="text-center font-semibold text-gray-600 py-2 text-sm">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Grid */}
          <div className="grid grid-cols-7 gap-2">
            {calendarDays.map((date, idx) => {
              const dayAppointments = getAppointmentsForDay(date);
              const isToday =
                date &&
                date.getDate() === today.getDate() &&
                date.getMonth() === today.getMonth() &&
                date.getFullYear() === today.getFullYear();
              const isSelected =
                selectedDay &&
                date &&
                date.getDate() === selectedDay.getDate() &&
                date.getMonth() === selectedDay.getMonth();

              if (!date) {
                return <div key={`empty-${idx}`} className="p-2" />;
              }

              return (
                <button
                  key={date.toISOString()}
                  onClick={() => setSelectedDay(date)}
                  className={`relative p-2 rounded-lg border-2 text-sm font-medium transition-all ${
                    isToday
                      ? 'border-blue-500 bg-blue-50'
                      : isSelected
                      ? 'border-blue-600 bg-blue-100'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="text-gray-900">{date.getDate()}</div>

                  {/* Appointment Indicators */}
                  {dayAppointments.length > 0 && (
                    <div className="mt-1 flex gap-1 flex-wrap">
                      {dayAppointments.map((appt) => (
                        <div
                          key={appt.id}
                          className={`
                            w-1.5 h-1.5 rounded-full
                            ${appt.is_auto_filled_by_ai
                              ? 'bg-yellow-400 animate-pulse'
                              : appt.status === 'completed'
                              ? 'bg-gray-400'
                              : appt.status === 'confirmed'
                              ? 'bg-green-500'
                              : 'bg-blue-500'
                            }
                          `}
                          title={appt.is_auto_filled_by_ai ? 'AI tarafından doldurulan' : ''}
                        />
                      ))}
                      {dayAppointments.length > 2 && (
                        <span className="text-xs text-gray-600">
                          +{dayAppointments.length - 2}
                        </span>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <p className="text-xs font-semibold text-gray-600 mb-3">GÖSTERGELER</p>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                <span className="text-gray-700">Planlandı</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500"></div>
                <span className="text-gray-700">Onaylı</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-gray-400"></div>
                <span className="text-gray-700">Tamamlandı</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse"></div>
                <span className="text-gray-700">AI Doldurulmuş</span>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar: Day Details */}
        <div className="col-span-1">
          {selectedDay ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 sticky top-6">
              <h3 className="font-bold text-gray-900 mb-2">
                {selectedDay.toLocaleDateString('tr-TR', {
                  weekday: 'long',
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                })}
              </h3>

              {getAppointmentsForDay(selectedDay).length > 0 ? (
                <div className="space-y-3">
                  {getAppointmentsForDay(selectedDay).map((appt) => {
                    const apptTime = new Date(appt.appointment_date).toLocaleTimeString('tr-TR', {
                      hour: '2-digit',
                      minute: '2-digit',
                    });

                    return (
                      <div
                        key={appt.id}
                        className={`border-l-4 p-3 rounded ${
                          appt.is_auto_filled_by_ai
                            ? 'border-l-yellow-400 bg-yellow-50'
                            : STATUS_COLORS[appt.status].split('bg-')[1].split(' ')[0].includes('blue')
                            ? 'border-l-blue-400 bg-blue-50'
                            : STATUS_COLORS[appt.status].split('bg-')[1].split(' ')[0].includes('green')
                            ? 'border-l-green-400 bg-green-50'
                            : 'border-l-gray-400 bg-gray-50'
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          {appt.is_auto_filled_by_ai && (
                            <Sparkles className="w-4 h-4 text-yellow-600 flex-shrink-0 mt-0.5" />
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <p className="font-semibold text-gray-900 text-sm truncate">
                                {appt.patient_name}
                              </p>
                              <span className="text-xs font-medium text-gray-600 flex-shrink-0">
                                {apptTime}
                              </span>
                            </div>
                            <p className="text-xs text-gray-700 mt-0.5">{appt.doctor_name}</p>
                            <p className="text-xs text-gray-600 mt-0.5">{appt.treatment_name}</p>

                            {/* Status Badge */}
                            <div className="mt-2 inline-block">
                              <span className="text-xs font-medium px-2 py-1 rounded bg-opacity-20 bg-gray-600 text-gray-700">
                                {STATUS_LABELS[appt.status]}
                              </span>
                            </div>

                            {/* AI Info */}
                            {appt.is_auto_filled_by_ai && (
                              <div className="mt-2 p-1.5 bg-yellow-100 rounded text-xs text-yellow-800 font-medium">
                                ✓ AI Randevu
                                {appt.ai_mutation_score && (
                                  <span className="ml-1">
                                    (Uyum: {Math.round(appt.ai_mutation_score)}%)
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-500 text-sm">Bu gün için randevu yok</p>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex items-center justify-center h-full min-h-[300px]">
              <p className="text-gray-500 text-center text-sm">
                Detayları görmek için bir gün seç
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
