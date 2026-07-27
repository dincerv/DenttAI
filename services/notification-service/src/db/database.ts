/**
 * PostgreSQL bağlantı havuzu ve RLS context yardımcıları.
 * Notification Service (Node.js), RLS context'ini event payload'daki
 * clinic_id ile manuel olarak set eder — JWT middleware'e gerek yoktur.
 */
import { Pool, PoolClient } from 'pg';
import { config } from '../config/config';
import { logger } from '../utils/logger';

export const pool = new Pool({
  connectionString: config.database.url,
  max: 10,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});

pool.on('error', (err) => {
  logger.error('PostgreSQL havuz hatası', { error: err.message });
});

// ── RLS Transaction Sarmalayıcı ───────────────────────────

/**
 * Verilen clinic_id ile RLS context'ini set eder ve işlemi çalıştırır.
 * Transaction başı ve sonunda otomatik BEGIN/COMMIT/ROLLBACK yapılır.
 * SET LOCAL → transaction bitince context temizlenir (veri sızmaz).
 */
export async function withRls<T>(
  clinicId: string,
  fn: (client: PoolClient) => Promise<T>,
): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('SET LOCAL app.current_clinic_id = $1', [clinicId]);
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

// ── Yardımcı Sorgular ─────────────────────────────────────

/** Doktorun bildirim offset'ini okur (saat cinsinden). */
export async function getDoctorOffset(
  clinicId: string,
  doctorId: string,
): Promise<number> {
  return withRls(clinicId, async (client) => {
    const res = await client.query<{ notification_offset: number }>(
      'SELECT notification_offset FROM doctors WHERE id = $1',
      [doctorId],
    );
    return res.rows[0]?.notification_offset ?? 24;
  });
}

/** Hastanın telefon numarasını okur. Yoksa mock numara döner. */
export async function getPatientPhone(
  clinicId: string,
  patientId: string,
): Promise<string> {
  return withRls(clinicId, async (client) => {
    const res = await client.query<{ phone: string | null; full_name: string }>(
      'SELECT phone, full_name FROM patients WHERE id = $1',
      [patientId],
    );
    const row = res.rows[0];
    // Mock modda gerçek numara olmayabilir; placeholder kullan
    return row?.phone ?? `+90-MOCK-${patientId.slice(0, 8)}`;
  });
}

/** Gönderilen mesajı sent_messages tablosuna kaydeder. */
export async function saveSentMessage(params: {
  clinicId: string;
  patientId: string;
  messageType: string;
  content: string;
  status?: string;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  const { clinicId, patientId, messageType, content, status = 'sent', metadata = {} } = params;
  await withRls(clinicId, async (client) => {
    await client.query(
      `INSERT INTO sent_messages
         (clinic_id, patient_id, channel, message_type, content, status, metadata)
       VALUES ($1, $2, 'whatsapp', $3, $4, $5, $6)`,
      [clinicId, patientId, messageType, content, status, JSON.stringify(metadata)],
    );
  });
}

/** Yapay zeka tarafından üretilen hasta takip notunu patient_notes tablosuna kaydeder. */
export async function saveAiFeedbackNote(params: {
  clinicId: string;
  patientId: string;
  appointmentId?: string;
  content: string;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  const { clinicId, patientId, appointmentId, content, metadata = {} } = params;
  const serializedMetadata = Object.keys(metadata).length > 0
    ? `\n\n[AI Meta] ${JSON.stringify(metadata)}`
    : '';

  await withRls(clinicId, async (client) => {
    await client.query(
      `INSERT INTO patient_notes
         (clinic_id, patient_id, doctor_id, appointment_id, note_type, content)
       VALUES ($1, $2, NULL, $3, 'ai_feedback', $4)`,
      [clinicId, patientId, appointmentId ?? null, `${content}${serializedMetadata}`],
    );
  });
}
