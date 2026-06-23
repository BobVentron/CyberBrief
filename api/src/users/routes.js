// src/users/routes.js — Profil, préférences mail, droits RGPD
import { Router } from 'express';
import { z }      from 'zod';
import prisma     from '../db/prisma.js';
import { requireAuth, hashPassword, verifyPassword } from '../auth/security.js';

const router = Router();

const MAX_EMAILS = 5;

// Schemas
const PrefsSchema = z.object({
  recipient_emails: z.array(z.string().email())
    .min(1, 'Au moins une adresse email requise')
    .max(MAX_EMAILS, `Maximum ${MAX_EMAILS} adresses`),
  send_daily:  z.boolean(),
  send_weekly: z.boolean(),
});

const ChangePwdSchema = z.object({
  current_password: z.string().min(1),
  new_password: z.string()
    .min(8,  'Minimum 8 caractères')
    .regex(/[A-Z]/, 'Au moins une majuscule')
    .regex(/[0-9]/, 'Au moins un chiffre'),
});

// Helpers
async function audit(action, userId, req, details = null) {
  await prisma.auditLog.create({
    data: {
      userId,
      action,
      ipAddress: req.ip || null,
      userAgent: req.headers['user-agent']?.slice(0, 256) || null,
      details,
    },
  });
}

// GET /api/users/me
router.get('/me', requireAuth, async (req, res) => {
  const user = await prisma.user.findUnique({
    where:   { id: req.user.sub },
    include: { preferences: true },
  });
  if (!user) return res.status(404).json({ detail: 'Utilisateur introuvable' });

  res.json({
    id:       user.id,
    email:    user.email,
    isAdmin:  user.isAdmin,
    createdAt: user.createdAt,
    lastLogin: user.lastLoginAt,
    consentGivenAt: user.consentGivenAt,
    preferences: user.preferences
      ? {
          recipient_emails: user.preferences.recipientEmails,
          send_daily:       user.preferences.sendDaily,
          send_weekly:      user.preferences.sendWeekly,
        }
      : null,
  });
});

// PUT /api/users/me/preferences
router.put('/me/preferences', requireAuth, async (req, res) => {
  const parse = PrefsSchema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: parse.error.errors[0].message });

  const { recipient_emails, send_daily, send_weekly } = parse.data;

  await prisma.mailPreference.upsert({
    where:  { userId: req.user.sub },
    update: { recipientEmails: recipient_emails, sendDaily: send_daily, sendWeekly: send_weekly },
    create: { userId: req.user.sub, recipientEmails: recipient_emails, sendDaily: send_daily, sendWeekly: send_weekly },
  });

  await audit('update_preferences', req.user.sub, req);

  res.json({
    message:     'Préférences mises à jour',
    preferences: { recipient_emails, send_daily, send_weekly },
  });
});

// POST /api/users/me/change-password
router.post('/me/change-password', requireAuth, async (req, res) => {
  const parse = ChangePwdSchema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: parse.error.errors[0].message });

  const user = await prisma.user.findUnique({ where: { id: req.user.sub } });
  if (!user) return res.status(404).json({ detail: 'Utilisateur introuvable' });

  const valid = await verifyPassword(parse.data.current_password, user.passwordHash);
  if (!valid) return res.status(400).json({ detail: 'Mot de passe actuel incorrect' });

  await prisma.$transaction([
    prisma.user.update({
      where: { id: req.user.sub },
      data:  { passwordHash: await hashPassword(parse.data.new_password) },
    }),
    prisma.userSession.updateMany({ where: { userId: req.user.sub }, data: { revoked: true } }),
  ]);

  await audit('change_password', req.user.sub, req);

  res.json({ message: 'Mot de passe modifié. Veuillez vous reconnecter.' });
});

// GET /api/users/me/export — Portabilité RGPD art. 20
router.get('/me/export', requireAuth, async (req, res) => {
  const user = await prisma.user.findUnique({
    where:   { id: req.user.sub },
    include: { preferences: true },
  });
  if (!user) return res.status(404).json({ detail: 'Utilisateur introuvable' });

  await audit('data_export', req.user.sub, req);

  res.json({
    export_date:     new Date().toISOString(),
    data_controller: 'CyberBrief — self-hosted instance',
    user: {
      id:       user.id,
      email:    user.email,
      createdAt: user.createdAt,
      lastLogin: user.lastLoginAt,
      consentGivenAt: user.consentGivenAt,
    },
    preferences: user.preferences
      ? {
          recipient_emails: user.preferences.recipientEmails,
          send_daily:       user.preferences.sendDaily,
          send_weekly:      user.preferences.sendWeekly,
        }
      : {},
    rgpd_rights: {
      access:        'GET /api/users/me',
      rectification: 'PUT /api/users/me/preferences',
      erasure:       'DELETE /api/users/me',
      portability:   'GET /api/users/me/export',
    },
  });
});

// DELETE /api/users/me — Droit à l'effacement RGPD art. 17
router.delete('/me', requireAuth, async (req, res) => {
  const userId = req.user.sub;

  // Anonymisation des logs d'audit (NIS-2 : conservation obligatoire, RGPD : minimisation)
  await prisma.auditLog.updateMany({
    where: { userId },
    data:  { userId: null },
  });

  // Suppression en cascade (sessions, préférences, tokens)
  await prisma.user.delete({ where: { id: userId } });

  await prisma.auditLog.create({
    data: {
      userId:    null,
      action:    'account_deleted',
      ipAddress: req.ip || null,
      userAgent: req.headers['user-agent']?.slice(0, 256) || null,
      details:   { note: 'Logs anonymisés — art. 17 RGPD / art. 21 NIS-2' },
    },
  });

  res.json({ message: 'Compte supprimé. Vos données personnelles ont été effacées.' });
});

export default router;
