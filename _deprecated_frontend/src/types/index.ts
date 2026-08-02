// ── Admin / Platform ──────────────────────────────────────

export interface ClinicSummary {
  id: string;
  name: string;
  slug: string;
  code: string | null;
  email_domain: string | null;
  is_active: boolean;
  user_count: number;
  created_at: string;
}

export interface PlatformStats {
  total_clinics: number;
  active_clinics: number;
  total_users: number;
}

export type AIUsagePeriod = 'day' | 'week' | 'month' | 'year';

export interface ClinicAIUsageSummary {
  clinic_id: string;
  clinic_name: string;
  clinic_slug: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  ai_cost_usd: number;
  whatsapp_message_count: number;
  whatsapp_cost_usd: number;
  total_cost_usd: number;
  request_count: number;
  last_usage_at: string | null;
}

export interface ClinicsAIUsageResponse {
  period: AIUsagePeriod;
  range_start: string;
  range_end: string;
  items: ClinicAIUsageSummary[];
}

// ── AI Insights (Owner Dashboard) ─────────────────────────────────────────────

export type InsightCategory = 'appointment' | 'revenue' | 'patient' | 'inventory' | 'performance';
export type InsightSeverity = 'info' | 'warning' | 'critical';

export interface InsightCard {
  category: InsightCategory;
  title: string;
  description: string;
  severity: InsightSeverity;
  metric_label: string;
  metric_value: string;
  action: string;
  generated_at: string;
}

export interface InsightsMetricsSummary {
  total_appointments_30d: number;
  cancel_rate_pct: number;
  noshow_rate_pct: number;
  active_waitlist: number;
  low_stock_items: number;
  urgent_feedback: number;
}

export interface ClinicInsightsResponse {
  insights: InsightCard[];
  generated_at: string;
  ai_powered: boolean;
  model_used: string;
  metrics_summary: InsightsMetricsSummary;
}

// ── Auth ──────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface MeResponse {
  id: string;
  clinic_id: string | null;
  email: string;
  full_name: string;
  role: 'super_admin' | 'owner' | 'doctor' | 'assistant';
  allowed_pages: string[];
  clinic_code: string | null;
  clinic_email_domain: string | null;
}

// ── Appointments ──────────────────────────────────────────

export type AppointmentStatus = 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show';

export interface Appointment {
  id: string;
  clinic_id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  duration_minutes?: number;
  is_new_patient?: boolean;
  treatment_follow_up_enabled?: boolean;
  status: AppointmentStatus;
  type: string | null;
  notes: string | null;
  created_at: string;
  // Joined fields (enriched by frontend where needed)
  patient_name?: string;
  patient_phone?: string;
  doctor_name?: string;
  specialty?: string;
}

export interface AppointmentCreateBody {
  patient_id: string;
  doctor_id: string;
  specialty: string;
  scheduled_at: string;
  type?: string;
  notes?: string;
  duration_minutes?: number;
  is_new_patient?: boolean;
  treatment_follow_up_enabled?: boolean;
}

export interface PatientTypePeriodOverview {
  new_count: number;
  old_count: number;
}

export interface PatientSummary {
  id: string;
  full_name: string;
  phone?: string | null;
}

export interface DoctorSummary {
  id: string;
  full_name: string;
  specialty?: string | null;
}

export interface ExternalDoctorMapping {
  external_name: string;
  mapped_doctor_id?: string | null;
}

export interface DoctorMappingsResponse {
  local_doctors: DoctorSummary[];
  external_doctors: ExternalDoctorMapping[];
}

// ── Waitlist ──────────────────────────────────────────────

export interface WaitlistEntry {
  id: string;
  clinic_id: string;
  patient_id: string;
  doctor_id?: string;
  specialty: string | null;
  priority: number;
  is_active: boolean;
  created_at: string;
  patient_name?: string;
  doctor_name?: string;
  patient_notes?: string;
  next_appointment_date?: string;
}

// ── Inventory ─────────────────────────────────────────────

export interface InventoryItem {
  id: string;
  clinic_id: string;
  name: string;
  category: string | null;
  quantity: number;
  unit: string;
  min_stock_level: number;
  cost_per_unit: number | null;
  shelf_code: string | null;
  expiry_date: string | null;   // ISO date: YYYY-MM-DD
  batch_number: string | null;  // Parti/lot numarası
  is_low_stock: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface InventoryAdjustment {
  id: string;
  item_id: string;
  delta: number;
  reason: string | null;
  performed_by_email: string | null;
  created_at: string;
}

// ── Batch (Parti) Özet Tipleri ────────────────────────────

export interface BatchInfo {
  batch_id: string;
  batch_number: string | null;
  quantity: number;
  expiry_date: string | null;
  days_until_expiry: number | null;
  is_low_stock: boolean;
}

export interface BatchSummary {
  name: string;
  category: string | null;
  unit: string | null;
  total_quantity: number;
  total_min_stock: number;
  is_low_stock: boolean;
  nearest_expiry_date: string | null;
  days_until_nearest_expiry: number | null;
  batches: BatchInfo[];
}

export interface CycleMaterial {
  id: string;
  clinic_id: string;
  qr_id: string;
  shelf_code: string | null;
  name: string;
  category: string | null;
  start_date: string | null;
  end_date: string | null;
  activated_at: string | null;  // ISO datetime with timezone
  expected_lifespan: number | null;
  actual_lifespan: number | null;
  is_active: boolean;
  is_high_waste: boolean;
  end_reason: string | null;
  waste_note: string | null;
  created_at: string;
}

export interface QRGenerateResponse {
  qr_id: string;
  shelf_code: string;
  material_id: string;
  qr_code_base64: string;
}

// ── Analytics ─────────────────────────────────────────────

export interface RecoveredRevenueResponse {
  period_start: string;
  period_end: string;
  total_recovered_appointments: number;
  total_recovered_revenue: number;
  by_specialty: { specialty: string; count: number; revenue: number }[];
  appointments: {
    message_id: string;
    sent_at: string;
    original_appointment_id: string;
    specialty: string | null;
    patient_name: string;
    fee: number;
  }[];
  cached: boolean;
}

export interface AppointmentStatsResponse {
  period_start: string;
  period_end: string;
  total: number;
  cancelled: number;
  no_show: number;
  completed: number;
  upcoming: number;
  cancel_rate_pct: number | null;
  no_show_rate_pct: number | null;
  completion_rate_pct: number | null;
  by_specialty: {
    specialty: string | null;
    total: number;
    cancelled: number;
    no_show: number;
    completed: number;
    cancel_rate_pct: number | null;
    no_show_rate_pct: number | null;
  }[];
  cached: boolean;
}

export interface NewPatientsOverviewResponse {
  day: PatientTypePeriodOverview;
  week: PatientTypePeriodOverview;
  month: PatientTypePeriodOverview;
  year: PatientTypePeriodOverview;
  generated_at: string;
}

export interface WasteReportResponse {
  total_high_waste: number;
  by_category: {
    category: string;
    total_cycles: number;
    high_waste_count: number;
    waste_rate_pct: number | null;
    avg_actual_lifespan: number | null;
    avg_expected_lifespan: number | null;
  }[];
  materials: CycleMaterial[];
  cached: boolean;
}

export interface DoctorScorecard {
  doctor_id: string;
  doctor_name: string;
  specialty: string | null;
  total: number;
  completed: number;
  cancelled: number;
  no_show: number;
  cancel_rate_pct: number | null;
  completion_rate_pct: number | null;
  loyal_patient_count: number;
}

export interface DoctorPerformanceResponse {
  period_start: string;
  period_end: string;
  doctors: DoctorScorecard[];
  cached: boolean;
}

// ── Expiring Cycles ──────────────────────────────────────────────────────────

export interface ExpiringCycle {
  id: string;
  qr_id: string;
  shelf_code: string | null;
  name: string;
  category: string | null;
  start_date: string | null;
  expected_lifespan: number | null;
  actual_lifespan: number | null;
  lifespan_used_pct: number | null;
}

export interface ExpiringCyclesResponse {
  items: ExpiringCycle[];
  cached: boolean;
}

// ── Treatment Counts ─────────────────────────────────────────────────────────

export interface TreatmentPeriod {
  period: string;
  total_completed: number;
  dolgu: number;
  kanal: number;
  implant: number;
  kron: number;
  cekim: number;
  protez: number;
  ortodonti: number;
  temizlik: number;
  beyazlatma: number;
}

export interface TreatmentTotals {
  total_completed: number;
  dolgu: number;
  kanal: number;
  implant: number;
  kron: number;
  cekim: number;
  protez: number;
  ortodonti: number;
  temizlik: number;
}

export interface ClinicUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  allowed_pages: string[];
  created_at: string;
}

export interface TreatmentCountsResponse {
  period_start: string;
  period_end: string;
  group_by: string;
  doctor_id: string | null;
  doctor_name: string | null;
  totals: TreatmentTotals;
  trend: TreatmentPeriod[];
  cached: boolean;
}

export interface DoctorTreatmentRow {
  doctor_id: string;
  doctor_name: string;
  specialty: string | null;
  total_completed: number;
  dolgu: number;
  kanal: number;
  implant: number;
  kron: number;
  cekim: number;
  protez: number;
  ortodonti: number;
  temizlik: number;
}

export interface TreatmentsByDoctorResponse {
  period_start: string;
  period_end: string;
  doctors: DoctorTreatmentRow[];
  cached: boolean;
}

export interface AIChatRequest {
  message: string;
}

export interface AIChatResponse {
  answer: string;
  model: string;
  fallback_used: boolean;
}

// ── Patient Notes ─────────────────────────────────────────

export type NoteType = 'treatment' | 'ai_feedback' | 'general';

export interface PatientNote {
  id: string;
  clinic_id: string;
  patient_id: string;
  doctor_id: string | null;
  doctor_name: string | null;
  patient_name: string | null;
  appointment_id: string | null;
  note_type: NoteType;
  content: string;
  created_at: string;
}

export interface PatientNotesSummary {
  doctor_id: string;
  doctor_name: string;
  specialty: string | null;
  period: string;
  treatment_count: number;
  notes: PatientNote[];
}

// ── Integration ───────────────────────────────────────────

export interface IntegrationConfig {
  id: string;
  clinic_id: string;
  provider: string;
  display_name: string;
  is_active: boolean;
  has_session_cookie: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_message: string | null;
  sync_interval_minutes: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface SyncResult {
  provider: string;
  patients_pulled: number;
  patients_inserted: number;
  appointments_pulled: number;
  appointments_inserted: number;
  doctors_pulled: number;
  errors: string[];
  synced_at: string | null;
}
