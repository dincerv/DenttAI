/**
 * Consumer: waitlist.match_found
 * ─────────────────────────────────────────────────────
 * Randevu iptali sonrası eşleşen yedek hastaya gönderilecek
 * "Boş slot var!" WhatsApp mesajını işler.
 * Aynı zamanda ilgili doktorun notification_offset'ini okuyarak
 * yeni randevu teyit mesajını dinamik olarak planlar.
 */
import { Channel, ConsumeMessage } from 'amqplib';
import { config } from '../config/config';
import { getDoctorOffset } from '../db/database';
import { sendWhatsApp, templates } from '../providers/whatsapp.provider';
import { scheduleConfirmation } from '../scheduler/confirmationScheduler';
import { MatchFoundEvent } from '../types/events';
import { logger } from '../utils/logger';

const QUEUE = 'notification.waitlist.match_found';

export async function startMatchFoundConsumer(channel: Channel): Promise<void> {
  await channel.assertQueue(QUEUE, { durable: true });
  await channel.bindQueue(QUEUE, config.rabbitmq.exchange, 'waitlist.match_found');
  await channel.prefetch(5);

  logger.info(`Consumer başlatıldı: ${QUEUE}`);

  channel.consume(QUEUE, async (msg: ConsumeMessage | null) => {
    if (!msg) return;

    let event: MatchFoundEvent;
    try {
      event = JSON.parse(msg.content.toString()) as MatchFoundEvent;
    } catch {
      logger.error('Geçersiz JSON payload', { queue: QUEUE });
      channel.nack(msg, false, false); // dead-letter'a gönder
      return;
    }

    const PROCESS_TIMEOUT_MS = 30_000;
    try {
      logger.info('waitlist.match_found alındı', {
        clinicId: event.clinic_id,
        patientId: event.patient_id,
        specialty: event.specialty,
      });

      await Promise.race([
        (async () => {
          // 1. Yedek hastaya anında "slot açıldı" mesajı gönder
          await sendWhatsApp({
            clinicId: event.clinic_id,
            patientId: event.patient_id,
            messageType: 'match_found',
            body: templates.matchFound(event.specialty, event.original_slot),
            metadata: {
              waitlist_id: event.waitlist_id,
              cancelled_appointment_id: event.cancelled_appointment_id,
            },
          });

          // 2. Doktorun notification_offset'ini oku
          const offsetHours = await getDoctorOffset(event.clinic_id, event.doctor_id);

          // 3. Onay hatırlatıcısını zamanla (slot zamanı - offset saat)
          const slotDate = new Date(event.original_slot);
          const sendAt = new Date(slotDate.getTime() - offsetHours * 60 * 60 * 1000);

          await scheduleConfirmation({
            clinicId: event.clinic_id,
            patientId: event.patient_id,
            appointmentId: event.cancelled_appointment_id,
            doctorId: event.doctor_id,
            specialty: event.specialty,
            scheduledAt: event.original_slot,
            sendAt,
          });
        })(),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Message processing timeout after 30s')), PROCESS_TIMEOUT_MS)
        ),
      ]);

      channel.ack(msg);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'unknown';
      logger.error('match_found işleme hatası', { error: message, patientId: event?.patient_id });
      // Yeniden deneme için requeue (ilk denemeyse); sonrasında dead-letter'a
      channel.nack(msg, false, msg.fields.redelivered === false);
    }
  });
}
