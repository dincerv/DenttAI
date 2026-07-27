/**
 * Consumer: appointment.cancelled
 * ─────────────────────────────────────────────────────
 * İptal edilen randevuyu loglar. Yedek listede eşleşme
 * bulunamadıysa hastaya bilgi mesajı gönderilir.
 */
import { Channel, ConsumeMessage } from 'amqplib';
import { config } from '../config/config';
import { sendWhatsApp, templates } from '../providers/whatsapp.provider';
import { AppointmentCancelledEvent } from '../types/events';
import { logger } from '../utils/logger';

const QUEUE = 'notification.appointment.cancelled';

export async function startCancelledConsumer(channel: Channel): Promise<void> {
  await channel.assertQueue(QUEUE, { durable: true });
  await channel.bindQueue(QUEUE, config.rabbitmq.exchange, 'appointment.cancelled');
  await channel.prefetch(5);

  logger.info(`Consumer başlatıldı: ${QUEUE}`);

  channel.consume(QUEUE, async (msg: ConsumeMessage | null) => {
    if (!msg) return;

    let event: AppointmentCancelledEvent;
    try {
      event = JSON.parse(msg.content.toString()) as AppointmentCancelledEvent;
    } catch {
      logger.error('Geçersiz JSON payload', { queue: QUEUE });
      channel.nack(msg, false, false);
      return;
    }

    const PROCESS_TIMEOUT_MS = 30_000;
    try {
      logger.info('appointment.cancelled alındı', {
        clinicId: event.clinic_id,
        appointmentId: event.appointment_id,
        specialty: event.specialty,
        scheduledAt: event.scheduled_at,
      });

      await Promise.race([
        (async () => {
          // Yedek listede eşleşme bulunamadıktan sonra buraya gelinir.
          // Hastaya iptal bildirimi gönder.
          await sendWhatsApp({
            clinicId: event.clinic_id,
            patientId: event.patient_id,
            messageType: 'cancelled_notice',
            body: templates.cancelledNotice(event.specialty, event.scheduled_at),
            metadata: {
              appointment_id: event.appointment_id,
              doctor_id: event.doctor_id,
            },
          });
        })(),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Message processing timeout after 30s')), PROCESS_TIMEOUT_MS)
        ),
      ]);

      channel.ack(msg);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'unknown';
      logger.error('cancelled işleme hatası', { error: message });
      channel.nack(msg, false, msg.fields.redelivered === false);
    }
  });
}
