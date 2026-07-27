/**
 * Consumer: appointment.completed
 * ─────────────────────────────────────────────────────
 * Tedavi tamamlandığında post-op bakım mesajını
 * yapılandırılmış gecikmeyle (varsayılan 24 saat) planlar.
 */
import { Channel, ConsumeMessage } from 'amqplib';
import { config } from '../config/config';
import { schedulePostOp } from '../scheduler/confirmationScheduler';
import { AppointmentCompletedEvent } from '../types/events';
import { logger } from '../utils/logger';

const QUEUE = 'notification.appointment.completed';

export async function startCompletedConsumer(channel: Channel): Promise<void> {
  await channel.assertQueue(QUEUE, { durable: true });
  await channel.bindQueue(QUEUE, config.rabbitmq.exchange, 'appointment.completed');
  await channel.prefetch(5);

  logger.info(`Consumer başlatıldı: ${QUEUE}`);

  channel.consume(QUEUE, async (msg: ConsumeMessage | null) => {
    if (!msg) return;

    let event: AppointmentCompletedEvent;
    try {
      event = JSON.parse(msg.content.toString()) as AppointmentCompletedEvent;
    } catch {
      channel.nack(msg, false, false);
      return;
    }

    const PROCESS_TIMEOUT_MS = 30_000;
    try {
      logger.info('appointment.completed alındı', {
        appointmentId: event.appointment_id,
        specialty: event.specialty,
      });

      await Promise.race([
        schedulePostOp({
          clinicId: event.clinic_id,
          patientId: event.patient_id,
          appointmentId: event.appointment_id,
          doctorId: event.doctor_id,
          specialty: event.specialty,
          scheduledAt: event.completed_at,
          delayHours: config.postOp.delayHours,
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Message processing timeout after 30s')), PROCESS_TIMEOUT_MS)
        ),
      ]);

      channel.ack(msg);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'unknown';
      logger.error('completed işleme hatası', { error: message });
      channel.nack(msg, false, msg.fields.redelivered === false);
    }
  });
}
