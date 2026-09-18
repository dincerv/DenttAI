import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Sunucu tarafı rota koruması.
 *
 * Access token sessionStorage'da olduğu için middleware onu göremez.
 * Login sonrası client'ta set edilen `dentai_session` cookie bayrağı kontrol edilir.
 * Asıl JWT doğrulama backend + AuthContext'te kalır.
 */
const SESSION_COOKIE = 'dentai_session';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  const isDashboard = pathname.startsWith('/dashboard');
  const isLogin = pathname === '/login' || pathname.startsWith('/login/');

  if (isDashboard && !hasSession) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('next', pathname);
    return NextResponse.redirect(loginUrl);
  }

  // NOT: Oturum cookie'si varken login sayfasına gitmeye izin veriyoruz.
  // Böylece URL ile giriş yapılmış izlenimi oluşmuyor; yeniden kimlik
  // doğrulama AuthContext/client tarafında kontrol edilir.
  // Bu aynı zamanda URL paylaşımı yoluyla otomatik giriş riskini ortadan kaldırır.

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/login'],
};
