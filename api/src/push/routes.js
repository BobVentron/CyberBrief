// src/push/routes.js — Web Push (PWA) : abonnements + envoi des notifications
import { Router } from 'express';
import { z }      from 'zod';
import webpush    from 'web-push';
import prisma     from '../db/prisma.js';
import { decodeAccessToken } from '../auth/security.js';

const router = Router();

const VAPID_PUBLIC  = process.env.VAPID_PUBLIC_KEY  || '';
const VAPID_PRIVATE = process.env.VAPID_PRIVATE_KEY || '';
const VAPID_SUBJECT = process.env.VAPID_SUBJECT || 'mailto:admin@cyberbrief.local';

const ENABLED = Boolean(VAPID_PUBLIC && VAPID_PRIVATE);
if (ENABLED) {
  webpush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC, VAPID_PRIVATE);
  console.log('[PUSH] Web Push activé');
} else {
  console.warn('[PUSH] VAPID non configuré — notifications push désactivées');
}

// ── Envoi à tous les abonnés ────────────────────────────────────────────────
export async function sendPushToAll(payload) {
  if (!ENABLED) return { sent: 0, failed: 0 };
  const subs = await prisma.pushSubscription.findMany();
  const data = JSON.stringify(payload);
  let sent = 0, failed = 0;

  await Promise.all(subs.map(async (s) => {
    try {
      await webpush.sendNotification(
        { endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } },
        data,
      );
      sent++;
    } catch (err) {
      failed++;
      // 404 / 410 → abonnement expiré, on le supprime
      if (err.statusCode === 404 || err.statusCode === 410) {
        await prisma.pushSubscription.delete({ where: { endpoint: s.endpoint } }).catch(() => {});
      }
    }
  }));

  console.log(`[PUSH] Notif envoyée — ${sent} ok / ${failed} échecs`);
  return { sent, failed };
}

// ── GET /api/push/key — clé publique VAPID pour le navigateur ───────────────
router.get('/key', (_req, res) => res.json({ publicKey: VAPID_PUBLIC, enabled: ENABLED }));

// ── POST /api/push/subscribe ────────────────────────────────────────────────
const SubSchema = z.object({
  endpoint: z.string().url(),
  keys:     z.object({ p256dh: z.string().min(1), auth: z.string().min(1) }),
});

router.post('/subscribe', async (req, res) => {
  const parse = SubSchema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: 'Abonnement invalide' });

  const { endpoint, keys } = parse.data;

  // Lien optionnel avec un compte si un token est présent
  let userId = null;
  const auth = req.headers.authorization;
  if (auth?.startsWith('Bearer ')) {
    try { userId = decodeAccessToken(auth.slice(7)).sub; } catch { /* anonyme */ }
  }

  const ua = req.headers['user-agent']?.slice(0, 256) || null;
  await prisma.pushSubscription.upsert({
    where:  { endpoint },
    update: { p256dh: keys.p256dh, auth: keys.auth, userId, userAgent: ua, lastSeenAt: new Date() },
    create: { endpoint, p256dh: keys.p256dh, auth: keys.auth, userId, userAgent: ua },
  });

  res.json({ ok: true });
});

// ── POST /api/push/unsubscribe ──────────────────────────────────────────────
router.post('/unsubscribe', async (req, res) => {
  const endpoint = req.body?.endpoint;
  if (typeof endpoint === 'string') {
    await prisma.pushSubscription.deleteMany({ where: { endpoint } });
  }
  res.json({ ok: true });
});

// ── POST /api/push/track-install — compteur d'installations PWA ─────────────
router.post('/track-install', async (_req, res) => {
  const s = await prisma.setting.findUnique({ where: { key: 'pwa_installs' } });
  const n = (parseInt(s?.value || '0', 10) || 0) + 1;
  await prisma.setting.upsert({
    where:  { key: 'pwa_installs' },
    update: { value: String(n) },
    create: { key: 'pwa_installs', value: '1' },
  });
  res.json({ ok: true });
});

export default router;
