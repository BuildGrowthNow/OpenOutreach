/**
 * Next.js Middleware for Multi-Tenant Authentication
 *
 * Protects routes and redirects unauthenticated users to login.
 */
import { NextRequest, NextResponse } from 'next/server';

// Public paths that don't require authentication
const PUBLIC_PATHS = [
  '/',
  '/login',
  '/login-v2',
  '/signup',
  '/signup-v2',
  '/register',
  '/reset-password',
  '/pricing',
  '/about',
];

// API routes don't need middleware protection (handled by backend)
const API_PATHS = ['/api'];

// Static assets and Next.js internals
const IGNORED_PATHS = ['/_next', '/favicon.ico', '/images', '/fonts'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow static assets and Next.js internals
  if (IGNORED_PATHS.some(path => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  // Allow API routes
  if (API_PATHS.some(path => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  // Allow public paths
  if (PUBLIC_PATHS.some(path => pathname === path)) {
    return NextResponse.next();
  }

  // Check for auth token in cookies or localStorage (via header)
  const token = request.cookies.get('auth_token')?.value;
  const authHeader = request.headers.get('authorization');

  // Protected routes - require authentication
  const protectedPaths = [
    '/dashboard',
    '/campaigns',
    '/leads',
    '/messages',
    '/analytics',
    '/settings',
  ];

  const isProtectedRoute = protectedPaths.some(path => pathname.startsWith(path));

  if (isProtectedRoute && !token && !authHeader) {
    // Redirect to login with return URL
    const loginUrl = new URL('/login-v2', request.url);
    loginUrl.searchParams.set('returnUrl', pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
