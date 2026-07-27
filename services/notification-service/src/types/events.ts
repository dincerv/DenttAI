/**
 * RabbitMQ event payload tipleri.
 * Bu tipler shared/events/README.md'deki sözleşmeyle eşleşir.
 */

export interface MatchFoundEvent {
  event: 'waitlist.match_found';
  clinic_id: string;
  cancelled_appointment_id: string;
  patient_id: string;
  waitlist_id: string;
  specialty: string;
  /** ISO-8601 string — iptal edilen randevunun orijinal saati */
  original_slot: string;
  doctor_id: string;
  priority: number;
}

export interface AppointmentCancelledEvent {
  event: 'appointment.cancelled';
  clinic_id: string;
  appointment_id: string;
  patient_id: string;
  doctor_id: string;
  specialty: string;
  scheduled_at: string;
}

export interface AppointmentConfirmedEvent {
  event: 'appointment.confirmed';
  clinic_id: string;
  appointment_id: string;
  patient_id: string;
  doctor_id: string;
  specialty: string;
  scheduled_at: string;
}

export interface AppointmentCompletedEvent {
  event: 'appointment.completed';
  clinic_id: string;
  appointment_id: string;
  patient_id: string;
  doctor_id: string;
  specialty: string;
  completed_at: string;
}

export type NotificationEvent =
  | MatchFoundEvent
  | AppointmentCancelledEvent
  | AppointmentConfirmedEvent
  | AppointmentCompletedEvent;

// ── BullMQ Job veri tipleri ────────────────────────────────

export interface ConfirmationJobData {
  jobType: 'confirmation' | 'postop';
  clinicId: string;
  patientId: string;
  appointmentId: string;
  doctorId: string;
  specialty: string;
  scheduledAt: string;
}
