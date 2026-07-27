/**
 * BullMQ Zamanlayıcı — Dinamik Bildirim Kuyruğu
 * ================================================
 * iki ayrı görev tipi:
 *   "confirmation" — randevu saatinden X saat önce teyit hatırlatıcısı
 *   "postop"       — tedavi tamamlandıktan N saat sonra bakım mesajı
 *
 * Redis üzerinde durable olarak saklanır; servis yeniden başlasa da
 * zamanlanmış joblar kaybolmaz.
 */
import { Job, Queue, Worker } from 'bullmq';
import IORedis from 'ioredis';
import { config } from '../config/config';
import { saveAiFeedbackNote } from '../db/database';
import { sendWhatsApp, templates } from '../providers/whatsapp.provider';
import { ConfirmationJobData } from '../types/events';
import { logger } from '../utils/logger';

// BullMQ için ayrı bir Redis bağlantısı (maxRetriesPerRequest=null zorunlu)
const redisConnection = new IORedis(config.redis.url, {
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
});

const QUEUE_NAME = 'dentai-notification-jobs';

// ── Queue Tanımı ─────────────────────────────────────────

export const notificationQueue = new Queue<ConfirmationJobData>(QUEUE_NAME, {
  connection: redisConnection,
  defaultJobOptions: {
    attempts: 3,
    backoff: { type: 'exponential', delay: 10_000 },
    removeOnComplete: { count: 100 },
    removeOnFail: { count: 50 },
  },
});

// ── Worker — Job İşleyicisi ──────────────────────────────

export const notificationWorker = new Worker<ConfirmationJobData>(
  QUEUE_NAME,
  async (job: Job<ConfirmationJobData>) => {
    const { jobType, clinicId, patientId, specialty, scheduledAt } = job.data;

    logger.info('Job işleniyor', {
      jobId: job.id,
      jobType,
      clinicId,
      patientId,
      specialty,
    });

    if (jobType === 'confirmation') {
      await sendWhatsApp({
        clinicId,
        patientId,
        messageType: 'confirmation',
        body: templates.confirmation(specialty, scheduledAt),
        metadata: { appointmentId: job.data.appointmentId, source: 'scheduler' },
      });
    } else if (jobType === 'postop') {
      await sendWhatsApp({
        clinicId,
        patientId,
        messageType: 'postop',
        body: templates.postOp(specialty),
        metadata: { appointmentId: job.data.appointmentId, source: 'scheduler' },
      });

      await saveAiFeedbackNote({
        clinicId,
        patientId,
        appointmentId: job.data.appointmentId,
        content: buildAiFeedbackNote({
          specialty,
          summary: 'WhatsApp üzerinden post-op takip mesajı otomatik gönderildi. Hasta yanıtı beklenecek ve analiz sonucunda bu başlık altında yeni AI notları eklenecek.',
          source: 'postop_followup',
        }),
        metadata: { source: 'postop_followup', specialty, scheduledAt },
      });
    }
  },
  { connection: redisConnection },
);

export function buildAiFeedbackNote(params: {
  specialty: string;
  summary: string;
  source: 'postop_followup' | 'reply_analysis';
  detectedSentiment?: 'positive' | 'neutral' | 'negative';
}): string {
  const lines = [
    'Yapay Zeka Notu',
    `Kaynak: ${params.source === 'postop_followup' ? 'Post-op otomatik takip' : 'Hasta yanıt analizi'}`,
    `Tedavi: ${params.specialty || 'Belirtilmedi'}`,
  ];

  if (params.detectedSentiment) {
    lines.push(`Duygu Analizi: ${params.detectedSentiment}`);
  }

  lines.push(`Özet: ${params.summary}`);
  return lines.join('\n');
}

// ── Worker Olayları ──────────────────────────────────────

notificationWorker.on('completed', (job) => {
  logger.info('Job tamamlandı', { jobId: job.id, type: job.data.jobType });
});

notificationWorker.on('failed', (job, err) => {
  logger.error('Job başarısız', {
    jobId: job?.id,
    type: job?.data?.jobType,
    attempt: job?.attemptsMade,
    error: err.message,
  });
});

// ── Zamanlama Fonksiyonları ──────────────────────────────

/**
 * Randevu teyit mesajını zamanlar.
 * sendAt = scheduled_at - doctor.notification_offset saat
 */
export async function scheduleConfirmation(params: {
  clinicId: string;
  patientId: string;
  appointmentId: string;
  doctorId: string;
  specialty: string;
  scheduledAt: string;
  sendAt: Date;
}): Promise<void> {
  const delayMs = Math.max(0, params.sendAt.getTime() - Date.now());

  await notificationQueue.add(
    'send-confirmation',
    {
      jobType: 'confirmation',
      clinicId: params.clinicId,
      patientId: params.patientId,
      appointmentId: params.appointmentId,
      doctorId: params.doctorId,
      specialty: params.specialty,
      scheduledAt: params.scheduledAt,
    },
    { delay: delayMs },
  );

  logger.info('Teyit mesajı planlandı', {
    patientId: params.patientId,
    sendAt: params.sendAt.toISOString(),
    delayHours: (delayMs / 3_600_000).toFixed(2),
  });
}

/**
 * Post-op bakım mesajını zamanlar.
 * delayHours sonra gönderilir (varsayılan: 24s sonra).
 */
export async function schedulePostOp(params: {
  clinicId: string;
  patientId: string;
  appointmentId: string;
  doctorId: string;
  specialty: string;
  scheduledAt: string;
  delayHours: number;
}): Promise<void> {
  const delayMs = params.delayHours * 60 * 60 * 1000;

  await notificationQueue.add(
    'send-postop',
    {
      jobType: 'postop',
      clinicId: params.clinicId,
      patientId: params.patientId,
      appointmentId: params.appointmentId,
      doctorId: params.doctorId,
      specialty: params.specialty,
      scheduledAt: params.scheduledAt,
    },
    { delay: delayMs },
  );

  logger.info('Post-op mesajı planlandı', {
    patientId: params.patientId,
    sendAfterHours: params.delayHours,
    specialty: params.specialty,
  });
}
