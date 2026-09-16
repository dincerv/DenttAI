function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} environment variable is required`);
  }
  return value;
}

export const config = {
  rabbitmq: {
    url: requireEnv('RABBITMQ_URL'),
    exchange: process.env.RABBITMQ_EXCHANGE ?? 'dentai.events',
  },
  redis: {
    url: requireEnv('REDIS_URL'),
  },
  database: {
    url: requireEnv('DATABASE_URL'),
  },
  whatsapp: {
    // provider: 'meta' = Meta Cloud API; 'mock' = consol+DB (geliştirme)
    provider: (process.env.WHATSAPP_PROVIDER ?? 'mock') as 'meta' | 'mock',
    // Meta Cloud API
    phoneNumberId: process.env.WHATSAPP_PHONE_NUMBER_ID ?? '',
    accessToken: process.env.WHATSAPP_API_KEY ?? '',          // Meta access token
    apiUrl: process.env.WHATSAPP_API_URL ?? 'https://graph.facebook.com/v19.0',
    // Kolay geçiş: WHATSAPP_PROVIDER=mock veya WHATSAPP_MOCK=true → mock mode
    mockMode:
      process.env.WHATSAPP_PROVIDER === 'mock' ||
      process.env.WHATSAPP_MOCK === 'true' ||
      !process.env.WHATSAPP_PHONE_NUMBER_ID ||
      !process.env.WHATSAPP_API_KEY,
  },
  postOp: {
    // Tedavi tamamlandıktan kaç saat sonra bakım talimatı gönderilsin?
    delayHours: parseInt(process.env.POSTOP_DELAY_HOURS ?? '24', 10),
  },
  service: {
    port: parseInt(process.env.SERVICE_PORT ?? '3001', 10),
  },
} as const;
