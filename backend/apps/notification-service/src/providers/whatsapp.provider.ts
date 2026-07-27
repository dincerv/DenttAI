/**
 * WhatsApp Entegrasyon Katmanı
 * ================================
 * Mock Mode  : WHATSAPP_MOCK=true veya WHATSAPP_PHONE_NUMBER_ID eksik → console + DB
 * Live Mode  : WHATSAPP_PROVIDER=meta, WHATSAPP_PHONE_NUMBER_ID ve WHATSAPP_API_KEY dolu
 *              → Meta Cloud API v19 (graph.facebook.com)
 *
 * Live mod aktivasyonu:
 *   1. Meta Business Suite > WhatsApp > Ayarlar > Telefon Numarası ID'sini al
 *   2. .env: WHATSAPP_PROVIDER=meta, WHATSAPP_PHONE_NUMBER_ID=..., WHATSAPP_API_KEY=<token>
 *   3. docker compose restart notification-service
 */
import axios, { AxiosError } from 'axios';
import { config } from '../config/config';
import { getPatientPhone, saveSentMessage } from '../db/database';
import { logger } from '../utils/logger';

export interface OutgoingMessage {
  clinicId: string;
  patientId: string;
  messageType: string;
  body: string;
  metadata?: Record<string, unknown>;
}

// ── Mesaj Şablonları ──────────────────────────────────────

export const templates = {
  matchFound: (specialty: string, slot: string) =>
    `Merhaba! ${specialty} branşında ${new Date(slot).toLocaleString('tr-TR')} tarihinde boş bir randevumuz oluştu. Randevuyu almak ister misiniz? Lütfen kliniğimizi arayın veya bu mesajı onaylayın.`,

  confirmation: (specialty: string, slot: string) =>
    `Randevu Hatırlatma: ${specialty} randevunuz ${new Date(slot).toLocaleString('tr-TR')} tarihinde. Doğrulama veya iptal için lütfen bizimle iletişime geçin. Sizi bekliyoruz!`,

  postOp: (specialty: string) =>
    `${specialty} tedavinizin ardından geçmiş olsun diliyoruz! Bakım talimatları için kliniğimizle iletişime geçebilirsiniz. Herhangi bir ağrı veya şikayette lütfen bizi arayın.`,

  cancelledNotice: (specialty: string, slot: string) =>
    `${new Date(slot).toLocaleString('tr-TR')} tarihindeki ${specialty} randevunuz iptal edilmiştir. Yeni randevu için kliniğimizi arayabilirsiniz.`,
};

// ── Ana Gönderim Fonksiyonu ───────────────────────────────

export async function sendWhatsApp(msg: OutgoingMessage): Promise<void> {
  const phone = await getPatientPhone(msg.clinicId, msg.patientId);

  if (config.whatsapp.mockMode) {
    await sendMock(msg, phone);
  } else {
    await sendMetaWithRetry(msg, phone);
  }
}

// ── Mock Mod ─────────────────────────────────────────────

async function sendMock(msg: OutgoingMessage, phone: string): Promise<void> {
  logger.info('[WhatsApp MOCK] ─── Mesaj Gönderildi ───', {
    to: phone,
    type: msg.messageType,
    clinicId: msg.clinicId,
    patientId: msg.patientId,
    body: msg.body,
  });

  await saveSentMessage({
    clinicId: msg.clinicId,
    patientId: msg.patientId,
    messageType: msg.messageType,
    content: msg.body,
    status: 'sent',
    metadata: { phone, mock: true, ...msg.metadata },
  });
}

// ── Real Mod — Meta Cloud API v19 (exponential-backoff retry) ──

const RETRY_DELAYS_MS = [500, 1000, 2000]; // 3 deneme

async function sendMetaWithRetry(msg: OutgoingMessage, phone: string): Promise<void> {
  const url = `${config.whatsapp.apiUrl}/${config.whatsapp.phoneNumberId}/messages`;

  let lastError: unknown;
  for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt++) {
    try {
      await axios.post(
        url,
        {
          messaging_product: 'whatsapp',
          to: phone,
          type: 'text',
          text: { preview_url: false, body: msg.body },
        },
        {
          headers: {
            Authorization: `Bearer ${config.whatsapp.accessToken}`,
            'Content-Type': 'application/json',
          },
          timeout: 10_000,
        },
      );

      await saveSentMessage({
        clinicId: msg.clinicId,
        patientId: msg.patientId,
        messageType: msg.messageType,
        content: msg.body,
        status: 'sent',
        metadata: { phone, provider: 'meta', attempt, ...msg.metadata },
      });

      logger.info('[WhatsApp META] Mesaj gönderildi', {
        to: phone,
        type: msg.messageType,
        attempt,
      });
      return; // başarı — çık
    } catch (err: unknown) {
      lastError = err;
      const status = err instanceof AxiosError ? err.response?.status : undefined;
      logger.warn('[WhatsApp META] Deneme başarısız', { attempt, status });

      // 4xx istemci hatası → yeniden deneme anlamsız
      if (status && status >= 400 && status < 500) break;

      if (attempt < RETRY_DELAYS_MS.length) {
        await new Promise((r) => setTimeout(r, RETRY_DELAYS_MS[attempt]));
      }
    }
  }

  // Tüm denemeler başarısız — hata kayıt et
  const message = lastError instanceof Error ? lastError.message : 'unknown';
  logger.error('[WhatsApp META] Tüm denemeler başarısız', { error: message, phone });

  await saveSentMessage({
    clinicId: msg.clinicId,
    patientId: msg.patientId,
    messageType: msg.messageType,
    content: msg.body,
    status: 'failed',
    metadata: { phone, error: message },
  });

  throw lastError;
}
