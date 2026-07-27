# shared/events — RabbitMQ Event Şema Tanımları
#
# Bu klasör, servisler arası asenkron iletişimde kullanılan
# event adlarını ve payload yapılarını belgelemek için ayrılmıştır.
#
# ── Planlanan Event'ler ──────────────────────────────────────
#
# Exchange: dentai.events (topic)
#
# appointment.cancelled    → Notification Service tetiklenir
#                            Payload: { appointment_id, patient_id, doctor_id, clinic_id, cancelled_at }
#
# appointment.confirmed    → Notification Service tetiklenir
#                            Payload: { appointment_id, patient_id, scheduled_at, notification_offset }
#
# waitlist.slot_available  → Appointment Service yedek listeyi işler
#                            Payload: { clinic_id, specialty, slot_datetime }
#
# postop.message_scheduled → Notification Service post-op mesajı gönderir
#                            Payload: { patient_id, template_id, send_at }
#
# inventory.low_stock      → (Gelecek) Alert tetiklenir
#                            Payload: { clinic_id, item_id, current_qty, threshold }
#
# Implementasyon: Prompt-3, Prompt-4 ve Prompt-5'te gerçekleştirilecek
