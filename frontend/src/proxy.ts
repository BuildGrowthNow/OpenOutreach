/**
 * Next.js Proxy for Multi-Tenant Authentication and Billing Enforcement
 *
 * Protects routes and redirects unauthenticated users to login.
 * Redirects authenticated users with inactive subscriptions to the plan page.
 */
import { NextRequest, NextResponse } from 'next/server';

// Public paths that don't require authentication
const PUBLIC_PATHS = [
  '/',
  '/login',
  '/signup',
  '/register',
  '/reset-password',
  '/verify-email',
  '/pricing',
  '/lifetime',
  '/terms',
  '/privacy',
];

// API routes don't need middleware protection (handled by backend)
const API_PATHS = ['/api'];

// Static assets and Next.js internals
const IGNORED_PATHS = ['/_next', '/favicon.ico', '/images', '/fonts'];

// Settings sub-paths users must reach even with inactive subscriptions
// (so they can re-subscribe, update payment info, or log out)
const BILLING_EXEMPT_PATHS = [
  '/settings/plan',
  '/settings/billing',
  '/settings/account',
];

// Subscription statuses considered active - access permitted
const ACTIVE_STATUSES = new Set(['active', 'trialing']);

export function proxy(request: NextRequest) {
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

  // Check for auth token in cookies (refresh_token for JWT auth)
  const token = request.cookies.get('refresh_token')?.value;
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
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('returnUrl', pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Billing enforcement - only on dashboard routes (not settings/plan itself)
  // billing_status is a readable (non-HTTP-only) cookie set by the backend on
  // login and token refresh. It mirrors user.subscription_status.
  if (isProtectedRoute && token) {
    const billingStatus = request.cookies.get('billing_status')?.value;
    const isBillingExempt = BILLING_EXEMPT_PATHS.some(p => pathname.startsWith(p));

    // Only redirect when we have a definitive inactive status.
    // Missing cookie (e.g. existing sessions before this deploy) - let through;
    // the billing overlay in the app will handle it at render time.
    if (
      billingStatus &&
      !ACTIVE_STATUSES.has(billingStatus) &&
      !isBillingExempt
    ) {
      const planUrl = new URL('/settings/plan', request.url);
      planUrl.searchParams.set('reason', billingStatus);
      return NextResponse.redirect(planUrl);
    }
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
