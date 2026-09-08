/**
 * Email tracking Worker — open pixel, click redirect, unsubscribe.
 *
 * Routes:
 *   GET  /open/:token.gif   → 1×1 transparent GIF; log open event; POST webhook
 *   GET  /click/:short/:token → resolve compact click token; log; 302 redirect
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
  tracked_link_id?: string;
  lead_id?: string;
  step_id?: string;
  message_id?: string;
  channel?: string;
  short_code?: string;
}

const MAX_ID_LENGTH = 256;
const MAX_EVENT_LENGTH = 16;
const MAX_DESTINATION_LENGTH = 2048;
const MAX_SHORT_CODE_LENGTH = 128;
const MAX_TOKEN_LENGTH = 8192;
const VALID_EVENTS = new Set(["open", "click", "unsub"]);

function b64url(buf: ArrayBufferLike): string {
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
      typeof payload.dest_url !== "string" || payload.dest_url.length > MAX_DESTINATION_LENGTH ||
      (payload.short_code !== undefined && (typeof payload.short_code !== "string" || payload.short_code.length > MAX_SHORT_CODE_LENGTH)) ||
      (payload.event === "click" && !payload.dest_url && (typeof payload.short_code !== "string" || !payload.short_code))
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
  payload: { deal_id: string; campaign_id: string; event: string; ts: number; event_id: string; tracked_link_id?: string; lead_id?: string; step_id?: string; message_id?: string; channel?: string }
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

async function eventId(token: string, event: string): Promise<string> {
  if (event === "click") {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return `${Date.now().toString(36)}-${b64url(bytes.buffer as ArrayBuffer)}`;
  }
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${event}:${token}`));
  return b64url(digest);
}

async function resolveDestination(env: Env, payload: TokenPayload, shortCode: string): Promise<string | null> {
  if (payload.dest_url) return payload.dest_url;
  if (!shortCode || payload.short_code !== shortCode) return null;
  try {
    const response = await fetch(
      `${env.BACKEND_URL}/api/email-tracking/resolve/${encodeURIComponent(payload.campaign_id)}/${encodeURIComponent(shortCode)}?channel=${encodeURIComponent(payload.channel || "email")}&step_id=${encodeURIComponent(payload.step_id || "")}`,
      { headers: { "X-Tracking-Resolver-Secret": env.WORKER_WEBHOOK_SECRET } },
    );
    if (!response.ok) return null;
    const result = await response.json() as { destination_url?: string };
    return result.destination_url || null;
  } catch {
    return null;
  }
}

async function resolveOpaqueClick(env: Env, shortCode: string, tokenId: string): Promise<TokenPayload | null> {
  try {
    const response = await fetch(
      `${env.BACKEND_URL}/api/email-tracking/resolve-click/${encodeURIComponent(tokenId)}`,
      { headers: { "X-Tracking-Resolver-Secret": env.WORKER_WEBHOOK_SECRET } },
    );
    if (!response.ok) return null;
    const result = await response.json() as Partial<TokenPayload> & { destination_url?: string; short_code?: string };
    if (result.short_code !== shortCode || !result.destination_url || !result.deal_id || !result.campaign_id) return null;
    return {
      deal_id: result.deal_id,
      campaign_id: result.campaign_id,
      event: "click",
      dest_url: result.destination_url,
      tracked_link_id: result.tracked_link_id,
      lead_id: result.lead_id,
      step_id: result.step_id,
      message_id: result.message_id,
      channel: result.channel,
      short_code: result.short_code,
    };
  } catch {
    return null;
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

async function isRateLimited(request: Request, env: Env, route: string): Promise<boolean> {
  // Keep only a keyed visitor fingerprint in KV; never persist the raw IP.
  const address = request.headers.get("CF-Connecting-IP") || "unknown";
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(`${env.SECRET_KEY}:${address}`),
  );
  const bucket = Math.floor(Date.now() / 60_000);
  const key = `rate:${route}:${b64url(digest)}:${bucket}`;
  const parsed = Number(await env.EMAIL_EVENTS.get(key) || "0");
  const current = Number.isFinite(parsed) ? parsed : 0;
  if (current >= 120) return true;
  await env.EMAIL_EVENTS.put(key, String(current + 1), { expirationTtl: 120 });
  return false;
}

// ── Route handlers ────────────────────────────────────────────────

async function handleOpen(request: Request, env: Env, ctx: ExecutionContext, tokenRaw: string): Promise<Response> {
  if (await isRateLimited(request, env, "open")) return new Response(null, { status: 429, headers: { "Retry-After": "60" } });
  const token = tokenRaw.replace(/\.gif$/, "");
  const payload = await verifyToken(token, env.SECRET_KEY);
  if (!payload || payload.event !== "open") {
    return new Response(null, { status: 400 });
  }

  // Always return the pixel — suppress tracking only if already unsubscribed.
  const suppressed = await env.EMAIL_SUPPRESSED.get(payload.deal_id);
  if (!suppressed) {
    const id = await eventId(token, "open");
    const key = `${payload.deal_id}:open:${id}`;
    await env.EMAIL_EVENTS.put(key, JSON.stringify({ ...payload, ts: Date.now() }), {
      expirationTtl: 60 * 60 * 24 * 90, // 90 days
    });
    ctx.waitUntil(postWebhook(env, {
      deal_id: payload.deal_id,
      campaign_id: payload.campaign_id,
      event: "open",
      ts: Math.floor(Date.now() / 1000),
      event_id: id,
      tracked_link_id: payload.tracked_link_id,
      lead_id: payload.lead_id,
      step_id: payload.step_id,
      message_id: payload.message_id,
      channel: payload.channel,
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

async function handleClick(request: Request, env: Env, ctx: ExecutionContext, token: string, shortCode = "", opaque = false): Promise<Response> {
  if (await isRateLimited(request, env, "click")) return new Response(null, { status: 429, headers: { "Retry-After": "60" } });
  const payload = opaque
    ? await resolveOpaqueClick(env, shortCode, token)
    : await verifyToken(token, env.SECRET_KEY);
  const destination = payload ? await resolveDestination(env, payload, shortCode) : null;
  if (!payload || payload.event !== "click" || !destination || !isSafeRedirect(destination)) {
    return new Response(null, { status: 400 });
  }

  // Suppress tracking if already unsubscribed — still redirect the user.
  const suppressed = await env.EMAIL_SUPPRESSED.get(payload.deal_id);
  if (!suppressed) {
    const id = await eventId(token, "click");
    const key = `${payload.deal_id}:click:${id}`;
    await env.EMAIL_EVENTS.put(key, JSON.stringify({ ...payload, ts: Date.now() }), {
      expirationTtl: 60 * 60 * 24 * 90,
    });
    ctx.waitUntil(postWebhook(env, {
      deal_id: payload.deal_id,
      campaign_id: payload.campaign_id,
      event: "click",
      ts: Math.floor(Date.now() / 1000),
      event_id: id,
      tracked_link_id: payload.tracked_link_id,
      lead_id: payload.lead_id,
      step_id: payload.step_id,
      message_id: payload.message_id,
      channel: payload.channel,
    }));
  }

  return Response.redirect(destination, 302);
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

async function handleUnsubGet(request: Request, env: Env, token: string): Promise<Response> {
  if (await isRateLimited(request, env, "unsub")) return new Response(null, { status: 429, headers: { "Retry-After": "60" } });
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
  if (await isRateLimited(request, env, "unsub")) return new Response(null, { status: 429, headers: { "Retry-After": "60" } });
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
    event_id: await eventId(token, "unsub"),
    lead_id: payload.lead_id,
    step_id: payload.step_id,
    message_id: payload.message_id,
    channel: payload.channel,
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
      const parts = clickMatch[1].split("/");
      return parts.length >= 2
        ? handleClick(request, env, ctx, parts.slice(1).join("/"), parts[0], !parts.slice(1).join("/").includes("."))
        : handleClick(request, env, ctx, parts[0]);
    }

    const unsubMatch = pathname.match(/^\/unsub\/(.+)$/);
    if (unsubMatch) {
      if (request.method === "GET") return handleUnsubGet(request, env, unsubMatch[1]);
      if (request.method === "POST") return handleUnsubPost(request, env, ctx, unsubMatch[1]);
    }

    return new Response("Not Found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
