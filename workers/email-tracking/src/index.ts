/**
 * Email tracking Worker — open pixel, click redirect, unsubscribe.
 *
 * Routes:
 *   GET  /open/:token.gif   → 1×1 transparent GIF; log open event; POST webhook
 *   GET  /click/:token      → decode dest URL; log click event; 302 redirect
 *   GET  /unsub/:token      → render one-click unsubscribe confirmation page
 *   POST /unsub/:token      → suppress email in KV; POST webhook
 *
 * Secrets (set via `wrangler secret put`):
 *   SECRET_KEY            — HMAC-SHA256 key, shared with Python backend
 *   WORKER_WEBHOOK_SECRET — sent in X-Webhook-Secret header to backend
 *   BACKEND_URL           — https://outreach-api.lengrowth.com
 */

export interface Env {
  EMAIL_EVENTS: KVNamespace;
  EMAIL_SUPPRESSED: KVNamespace;
  SECRET_KEY: string;
  WORKER_WEBHOOK_SECRET: string;
  BACKEND_URL: string;
}

// ── 1×1 transparent GIF ───────────────────────────────────────────

const PIXEL_GIF = new Uint8Array([
  71, 73, 70, 56, 57, 97, 1, 0, 1, 0, 128, 0, 0, 255, 255, 255, 0, 0, 0, 33,
  249, 4, 0, 0, 0, 0, 0, 44, 0, 0, 0, 0, 1, 0, 1, 0, 0, 2, 2, 68, 1, 0, 59,
]);

// ── Token verification ────────────────────────────────────────────

interface TokenPayload {
  deal_id: string;
  campaign_id: string;
  event: string;
  dest_url: string;
  iat?: number;
  exp?: number;
}

const MAX_ID_LENGTH = 256;
const MAX_EVENT_LENGTH = 16;
const MAX_DESTINATION_LENGTH = 2048;
const MAX_TOKEN_LENGTH = 8192;
const VALID_EVENTS = new Set(["open", "click", "unsub"]);

function b64url(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

function b64urlDecode(s: string): Uint8Array {
  const padded = s + "=".repeat((4 - (s.length % 4)) % 4);
  const bin = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

async function verifyToken(token: string, secret: string): Promise<TokenPayload | null> {
  if (token.length > MAX_TOKEN_LENGTH) return null;
  const dot = token.indexOf(".");
  if (dot === -1) return null;
  const payloadB64 = token.slice(0, dot);
  const sigB64 = token.slice(dot + 1);

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );

  const expectedSig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(payloadB64)
  );
  const expectedB64 = b64url(expectedSig);

  // constant-time compare
  if (expectedB64.length !== sigB64.length) return null;
  let diff = 0;
  for (let i = 0; i < expectedB64.length; i++) {
    diff |= expectedB64.charCodeAt(i) ^ sigB64.charCodeAt(i);
  }
  if (diff !== 0) return null;

  try {
    const payload = JSON.parse(new TextDecoder().decode(b64urlDecode(payloadB64))) as Partial<TokenPayload>;
    if (
      !payload || typeof payload !== "object" ||
      typeof payload.deal_id !== "string" || payload.deal_id.length === 0 || payload.deal_id.length > MAX_ID_LENGTH ||
      typeof payload.campaign_id !== "string" || payload.campaign_id.length > MAX_ID_LENGTH ||
      typeof payload.event !== "string" || payload.event.length > MAX_EVENT_LENGTH || !VALID_EVENTS.has(payload.event) ||
      typeof payload.dest_url !== "string" || payload.dest_url.length > MAX_DESTINATION_LENGTH
    ) return null;
    for (const timestamp of [payload.iat, payload.exp]) {
      if (timestamp !== undefined && (typeof timestamp !== "number" || !Number.isFinite(timestamp))) return null;
    }
    // Legacy tokens without expiry remain valid during the coordinated
    // rollout; all newly issued tokens are time-bounded.
    if (payload.exp !== undefined && (!Number.isFinite(payload.exp) || payload.exp <= Date.now() / 1000)) {
      return null;
    }
    return payload as TokenPayload;
  } catch {
    return null;
  }
}

// ── Webhook helper ────────────────────────────────────────────────

async function postWebhook(
  env: Env,
  payload: { deal_id: string; campaign_id: string; event: string; ts: number }
): Promise<void> {
  const url = `${env.BACKEND_URL}/api/email-tracking/event`;
  const body = JSON.stringify(payload);
  const headers = {
    "Content-Type": "application/json",
    "X-Webhook-Secret": env.WORKER_WEBHOOK_SECRET,
  };
  for (let attempt = 0; attempt < 3; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5_000);
    try {
      const res = await fetch(url, { method: "POST", headers, body, signal: controller.signal });
      if (res.ok) return;
      // Do not retry permanent auth/validation/client failures. Retry only
      // throttling and transient upstream/server responses.
      if (res.status !== 429 && res.status < 500) return;
    } catch {
      // Timeout/network error — retry while attempts remain.
    } finally {
      clearTimeout(timeout);
    }
    if (attempt < 2) {
      await new Promise((r) => setTimeout(r, 200 * 2 ** attempt));
    }
  }
}

function isSafeRedirect(destination: string): boolean {
  if (destination.length > 2048) return false;
  try {
    const parsed = new URL(destination);
    return (
      (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      parsed.hostname.length > 0 &&
      !parsed.username &&
      !parsed.password
    );
  } catch {
    return false;
  }
}

// ── Route handlers ────────────────────────────────────────────────

async function handleOpen(request: Request, env: Env, ctx: ExecutionContext, tokenRaw: string): Promise<Response> {
  const token = tokenRaw.replace(/\.gif$/, "");
  const payload = await verifyToken(token, env.SECRET_KEY);
  if (!payload || payload.event !== "open") {
    return new Response(null, { status: 400 });
  }

  // Always return the pixel — suppress tracking only if already unsubscribed.
  const suppressed = await env.EMAIL_SUPPRESSED.get(payload.deal_id);
  if (!suppressed) {
    const key = `${payload.deal_id}:open:${Date.now()}`;
    await env.EMAIL_EVENTS.put(key, JSON.stringify({ ...payload, ts: Date.now() }), {
      expirationTtl: 60 * 60 * 24 * 90, // 90 days
    });
    ctx.waitUntil(postWebhook(env, {
      deal_id: payload.deal_id,
      campaign_id: payload.campaign_id,
      event: "open",
      ts: Math.floor(Date.now() / 1000),
    }));
  }

  return new Response(PIXEL_GIF, {
    headers: {
      "Content-Type": "image/gif",
      "Cache-Control": "no-store, no-cache, must-revalidate",
      Pragma: "no-cache",
    },
  });
}

async function handleClick(request: Request, env: Env, ctx: ExecutionContext, token: string): Promise<Response> {
  const payload = await verifyToken(token, env.SECRET_KEY);
  if (!payload || payload.event !== "click" || !payload.dest_url || !isSafeRedirect(payload.dest_url)) {
    return new Response(null, { status: 400 });
  }

  // Suppress tracking if already unsubscribed — still redirect the user.
  const suppressed = await env.EMAIL_SUPPRESSED.get(payload.deal_id);
  if (!suppressed) {
    const key = `${payload.deal_id}:click:${Date.now()}`;
    await env.EMAIL_EVENTS.put(key, JSON.stringify({ ...payload, ts: Date.now() }), {
      expirationTtl: 60 * 60 * 24 * 90,
    });
    ctx.waitUntil(postWebhook(env, {
      deal_id: payload.deal_id,
      campaign_id: payload.campaign_id,
      event: "click",
      ts: Math.floor(Date.now() / 1000),
    }));
  }

  return Response.redirect(payload.dest_url, 302);
}

function unsubscribePage(_token: string): Response {
  const html = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Unsubscribe</title>
<style>body{font-family:sans-serif;max-width:480px;margin:80px auto;padding:0 16px;text-align:center}
button{padding:12px 32px;font-size:16px;background:#dc2626;color:#fff;border:none;border-radius:6px;cursor:pointer}
button:hover{background:#b91c1c}</style>
</head>
<body>
<h2>Unsubscribe</h2>
<p>Click below to stop receiving emails from this campaign.</p>
<form method="POST">
  <button type="submit">Unsubscribe me</button>
</form>
</body>
</html>`;
  return new Response(html, {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

function unsubscribeDonePage(): Response {
  const html = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Unsubscribed</title>
<style>body{font-family:sans-serif;max-width:480px;margin:80px auto;padding:0 16px;text-align:center}
p{color:#16a34a;font-size:18px}</style>
</head>
<body>
<h2>You're unsubscribed</h2>
<p>You won't receive any more emails from this campaign.</p>
</body>
</html>`;
  return new Response(html, {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

async function handleUnsubGet(_request: Request, env: Env, token: string): Promise<Response> {
  const payload = await verifyToken(token, env.SECRET_KEY);
  if (!payload || payload.event !== "unsub") {
    return new Response("Invalid or expired unsubscribe link.", {
      status: 400,
      headers: { "Content-Type": "text/plain" },
    });
  }
  return unsubscribePage(token);
}

async function handleUnsubPost(request: Request, env: Env, ctx: ExecutionContext, token: string): Promise<Response> {
  const payload = await verifyToken(token, env.SECRET_KEY);
  if (!payload || payload.event !== "unsub") {
    return new Response(null, { status: 400 });
  }

  await env.EMAIL_SUPPRESSED.put(payload.deal_id, "1");

  ctx.waitUntil(postWebhook(env, {
    deal_id: payload.deal_id,
    campaign_id: payload.campaign_id,
    event: "unsub",
    ts: Math.floor(Date.now() / 1000),
  }));

  return unsubscribeDonePage();
}

// ── Router ────────────────────────────────────────────────────────

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const pathname = url.pathname;

    const openMatch = pathname.match(/^\/open\/(.+\.gif)$/);
    if (openMatch && request.method === "GET") {
      return handleOpen(request, env, ctx, openMatch[1]);
    }

    const clickMatch = pathname.match(/^\/click\/(.+)$/);
    if (clickMatch && request.method === "GET") {
      return handleClick(request, env, ctx, clickMatch[1]);
    }

    const unsubMatch = pathname.match(/^\/unsub\/(.+)$/);
    if (unsubMatch) {
      if (request.method === "GET") return handleUnsubGet(request, env, unsubMatch[1]);
      if (request.method === "POST") return handleUnsubPost(request, env, ctx, unsubMatch[1]);
    }

    return new Response("Not Found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
