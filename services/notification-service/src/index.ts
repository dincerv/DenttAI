/**
 * DentAI Flow — Notification & Scheduler Service
 * ================================================
 * Başlatma akışı:
 *   1. PostgreSQL bağlantısı test edilir
 *   2. BullMQ worker başlatılır (zamanlanmış joblar için)
 *   3. RabbitMQ'ya bağlanılır, 4 consumer başlatılır
 *
 * Dinlenen event'ler:
 *   waitlist.match_found      → anında slot bildirimi + teyit zamanla
 *   appointment.cancelled     → hastaya iptal bildirimi
 *   appointment.confirmed     → teyit hatırlatıcısı zamanla
 *   appointment.completed     → post-op mesajı zamanla
 */
import http from 'http';
import amqplib, { Channel } from 'amqplib';
import { config } from './config/config';
import { startCancelledConsumer } from './consumers/cancelledConsumer';
import { startCompletedConsumer } from './consumers/completedConsumer';
import { startConfirmedConsumer } from './consumers/confirmedConsumer';
import { startMatchFoundConsumer } from './consumers/matchFoundConsumer';
import { pool, saveAiFeedbackNote } from './db/database';
import { buildAiFeedbackNote, notificationWorker } from './scheduler/confirmationScheduler';
import { logger } from './utils/logger';

// Module-level RabbitMQ state — health endpoint tarafından erişilir
let rabbitConnection: amqplib.Connection | null = null;
let rabbitChannel: Channel | null = null;
const HEALTHCHECK_QUEUE = 'notification.appointment.cancelled';

async function connectRabbitMQ() {
  const connection = await amqplib.connect(config.rabbitmq.url);
  const channel = await connection.createChannel();

  // Exchange'i bu servis de declare eder (idempotent)
  await channel.assertExchange(config.rabbitmq.exchange, 'topic', { durable: true });

  logger.info('RabbitMQ bağlantısı kuruldu', { exchange: config.rabbitmq.exchange });

  connection.on('error', (err) => {
    logger.error('RabbitMQ bağlantı hatası', { error: err.message });
    rabbitConnection = null;
    rabbitChannel = null;
    process.exit(1); // Docker restart policy devreye girecek
  });

  return { connection: connection as unknown as amqplib.Connection, channel };
}

async function bootstrap(): Promise<void> {
  logger.info('Notification Service başlatılıyor...', {
    port: config.service.port,
    mockMode: config.whatsapp.mockMode,
    postOpDelayHours: config.postOp.delayHours,
  });

  // 1. Veritabanı bağlantısını test et
  try {
    const client = await pool.connect();
    await client.query('SELECT 1');
    client.release();
    logger.info('PostgreSQL bağlantısı başarılı');
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'unknown';
    logger.error('PostgreSQL bağlantısı kurulamadı', { error: message });
    process.exit(1);
  }

  // 2. BullMQ worker zaten modül import'unda başladı — log'a yaz
  logger.info('BullMQ worker hazır', { queue: 'dentai-notification-jobs' });

  // 3. RabbitMQ bağla ve consumer'ları başlat
  const { connection, channel } = await connectRabbitMQ();
  rabbitConnection = connection;
  rabbitChannel = channel;

  await startMatchFoundConsumer(channel);
  await startCancelledConsumer(channel);
  await startConfirmedConsumer(channel);
  await startCompletedConsumer(channel);

  // 4. HTTP health endpoint (Docker healthcheck için)
  const healthServer = http.createServer(async (req, res) => {
    if (req.url === '/health' && req.method === 'GET') {
      const checks: Record<string, string> = {};
      let status = 'ok';

      // Postgres check
      try {
        const client = await pool.connect();
        await client.query('SELECT 1');
        client.release();
        checks.postgres = 'ok';
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'unknown';
        checks.postgres = `error: ${message}`;
        status = 'degraded';
      }

      // RabbitMQ check — gerçek bağlantı durumunu ölç
      try {
        if (rabbitConnection && rabbitChannel) {
          await rabbitChannel.checkQueue(HEALTHCHECK_QUEUE);
          checks.rabbitmq = 'ok';
        } else {
          checks.rabbitmq = 'disconnected';
          status = 'degraded';
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'unknown';
        checks.rabbitmq = `error: ${message}`;
        status = 'degraded';
      }

      const code = status === 'ok' ? 200 : 503;
      res.writeHead(code, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status, service: 'notification-service', checks }));
    } else if (req.url === '/internal/ai-feedback-note' && req.method === 'POST') {
      const chunks: Buffer[] = [];
      req.on('data', (chunk) => chunks.push(chunk));
      req.on('end', async () => {
        try {
          const raw = Buffer.concat(chunks).toString('utf-8');
          const body = JSON.parse(raw) as {
            clinicId?: string;
            patientId?: string;
            appointmentId?: string;
            specialty?: string;
            summary?: string;
            source?: 'postop_followup' | 'reply_analysis';
            detectedSentiment?: 'positive' | 'neutral' | 'negative';
            metadata?: Record<string, unknown>;
          };

          if (!body.clinicId || !body.patientId || !body.summary) {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'clinicId, patientId ve summary zorunludur' }));
            return;
          }

          await saveAiFeedbackNote({
            clinicId: body.clinicId,
            patientId: body.patientId,
            appointmentId: body.appointmentId,
            content: buildAiFeedbackNote({
              specialty: body.specialty ?? 'Belirtilmedi',
              summary: body.summary,
              source: body.source ?? 'reply_analysis',
              detectedSentiment: body.detectedSentiment,
            }),
            metadata: {
              source: body.source ?? 'reply_analysis',
              detectedSentiment: body.detectedSentiment,
              ...(body.metadata ?? {}),
            },
          });

          res.writeHead(201, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true }));
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : 'unknown';
          logger.error('AI feedback note kaydı başarısız', { error: message });
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: message }));
        }
      });
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  healthServer.listen(config.service.port, () => {
    logger.info('Health HTTP server dinliyor', { port: config.service.port });
  });

  logger.info('Notification Service HAZIR — 4 consumer dinliyor 👂');
}

// ── Graceful Shutdown ─────────────────────────────────────
process.on('SIGTERM', async () => {
  logger.info('SIGTERM alındı; kapatılıyor...');
  await notificationWorker.close();
  await pool.end();
  process.exit(0);
});

bootstrap().catch((err: Error) => {
  logger.error('Servis başlatılamadı', { error: err.message, stack: err.stack });
  process.exit(1);
});

