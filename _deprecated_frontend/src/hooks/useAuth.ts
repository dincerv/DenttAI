'use client';
/**
 * useAuth — AuthContext'i sarmalayan uyumluluk hook'u.
 * Tüm mevcut kullanımlar değişmeden çalışır; ancak artık
 * her bileşen ayrı /auth/me isteği atmaz; context paylaşır.
 */
export { useAuthContext as useAuth } from '@/context/AuthContext';
