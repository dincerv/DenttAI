/**
 * Consumer: appointment.confirmed
 * ─────────────────────────────────────────────────────
 * Randevu teyit edildiğinde doktor bazlı offset okuyarak
 * BullMQ'ya zamanlanmış teyit mesajı ekler.
 */
import { Channel, ConsumeMessage } from 'amqplib';
import { config } from '../config/config';
import { getDoctorOffset } from '../db/database';
import { scheduleConfirmation } from '../scheduler/confirmationScheduler';
import { AppointmentConfirmedEvent } from '../types/events';
import { logger } from '../utils/logger';

const QUEUE = 'notification.appointment.confirmed';

export async function startConfirmedConsumer(channel: Channel): Promise<void> {
  await channel.assertQueue(QUEUE, { durable: true });
  await channel.bindQueue(QUEUE, config.rabbitmq.exchange, 'appointment.confirmed');
  await channel.prefetch(5);

  logger.info(`Consumer başlatıldı: ${QUEUE}`);

  channel.consume(QUEUE, async (msg: ConsumeMessage | null) => {
    if (!msg) return;

    let event: AppointmentConfirmedEvent;
    try {
      event = JSON.parse(msg.content.toString()) as AppointmentConfirmedEvent;
    } catch {
      channel.nack(msg, false, false);
      return;
    }

    const PROCESS_TIMEOUT_MS = 30_000;
    try {
      logger.info('appointment.confirmed alındı', {
        appointmentId: event.appointment_id,
        scheduledAt: event.scheduled_at,
      });

      await Promise.race([
        (async () => {
          const offsetHours = await getDoctorOffset(event.clinic_id, event.doctor_id);
          const slotDate = new Date(event.scheduled_at);
          const sendAt = new Date(slotDate.getTime() - offsetHours * 60 * 60 * 1000);

          await scheduleConfirmation({
            clinicId: event.clinic_id,
            patientId: event.patient_id,
            appointmentId: event.appointment_id,
            doctorId: event.doctor_id,
            specialty: event.specialty,
            scheduledAt: event.scheduled_at,
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
      logger.error('confirmed işleme hatası', { error: message });
      channel.nack(msg, false, msg.fields.redelivered === false);
    }
  });
}
