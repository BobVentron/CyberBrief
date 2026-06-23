// src/auth/routes.js — Inscription, connexion, refresh, reset password
import { Router }   from 'express';
import { rateLimit } from 'express-rate-limit';
import { z }        from 'zod';
import prisma       from '../db/prisma.js';
import {
  hashPassword, verifyPassword,
  createAccessToken, generateRefreshToken,
  generateVerificationToken, hashToken,
} from './security.js';
import { sendVerificationEmail, sendPasswordResetEmail } from '../mailer/service.js';

const router = Router();

// Rate limiter strict sur les routes d'auth
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max:      10,
  message:  { detail: 'Trop de tentatives, réessayez dans 15 minutes.' },
  standardHeaders: true, legacyHeaders: false,
});

// Schemas Zod
const passwordSchema = z.string()
  .min(8,  'Minimum 8 caractères')
  .regex(/[A-Z]/, 'Au moins une majuscule')
  .regex(/[0-9]/, 'Au moins un chiffre');

const RegisterSchema = z.object({
  email:        z.string().email('Email invalide'),
  password:     passwordSchema,
  consent_rgpd: z.literal(true, { errorMap: () => ({ message: 'Le consentement RGPD est obligatoire' }) }),
});

const LoginSchema = z.object({
  email:    z.string().email(),
  password: z.string().min(1),
});

const ForgotSchema = z.object({
  email: z.string().email(),
});

const ResetSchema = z.object({
  token:    z.string().min(1),
  password: passwordSchema,
});

const RefreshSchema = z.object({
  refresh_token: z.string().min(1),
});

// Helpers
function getIp(req) {
  return req.ip || req.socket?.remoteAddress || 'unknown';
}

async function audit(action, req, userId = null, details = null) {
  await prisma.auditLog.create({
    data: {
      userId,
      action,
      ipAddress: getIp(req),
      userAgent: req.headers['user-agent']?.slice(0, 256) || null,
      details,
    },
  });
}

// POST /api/auth/register
router.post('/register', authLimiter, async (req, res) => {
  const parse = RegisterSchema.safeParse(req.body);
  if (!parse.success) {
    return res.status(422).json({ detail: parse.error.errors[0].message });
  }

  const { email, password } = parse.data;

  // Anti-énumération : même réponse que l'email existe ou non
  const SAFE_RESPONSE = { message: "Si cet email est valide, un lien de vérification vous a été envoyé." };

  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) {
    await audit('register_duplicate', req, null, { email });
    return res.status(201).json(SAFE_RESPONSE);
  }

  const user = await prisma.user.create({
    data: {
      email,
      passwordHash:   await hashPassword(password),
      isActive:       false,
      consentGivenAt: new Date(),
      preferences: {
        create: {
          recipientEmails: [email],
          sendDaily:  true,
          sendWeekly: true,
        },
      },
    },
  });

  const { raw, hash, expiresAt } = generateVerificationToken();
  await prisma.verificationToken.create({
    data: { userId: user.id, tokenHash: hash, purpose: 'email_verify', expiresAt },
  });

  await audit('register', req, user.id);

  // Envoi asynchrone — ne bloque pas la réponse
  sendVerificationEmail(email, raw).catch(err =>
    console.error('[MAILER] Erreur envoi vérif:', err.message)
  );

  res.status(201).json(SAFE_RESPONSE);
});

// GET /api/auth/verify-email
router.get('/verify-email', async (req, res) => {
  const { token } = req.query;
  if (!token) return res.status(400).json({ detail: 'Token manquant' });

  const vt = await prisma.verificationToken.findUnique({
    where: { tokenHash: hashToken(token) },
  });

  if (!vt || vt.purpose !== 'email_verify' || vt.used || vt.expiresAt < new Date()) {
    return res.status(400).json({ detail: 'Lien invalide ou expiré' });
  }

  await prisma.$transaction([
    prisma.user.update({ where: { id: vt.userId }, data: { isActive: true } }),
    prisma.verificationToken.update({ where: { id: vt.id }, data: { used: true } }),
  ]);

  res.json({ message: 'Email vérifié. Vous pouvez maintenant vous connecter.' });
});

// POST /api/auth/login
router.post('/login', authLimiter, async (req, res) => {
  const parse = LoginSchema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: 'Données invalides' });

  const { email, password } = parse.data;

  const user = await prisma.user.findUnique({ where: { email } });

  // Toujours vérifier le mdp même si user inexistant (anti-timing)
  const valid = user ? await verifyPassword(password, user.passwordHash) : false;

  if (!user || !valid) {
    await audit('login_failed', req, null, { email });
    return res.status(401).json({ detail: 'Email ou mot de passe incorrect' });
  }

  if (!user.isActive) {
    return res.status(403).json({ detail: 'Compte non activé — vérifiez vos emails' });
  }

  const { raw, hash, expiresAt } = generateRefreshToken();
  await prisma.userSession.create({
    data: {
      userId:    user.id,
      tokenHash: hash,
      userAgent: req.headers['user-agent']?.slice(0, 256) || null,
      ipAddress: getIp(req),
      expiresAt,
    },
  });

  await prisma.user.update({ where: { id: user.id }, data: { lastLoginAt: new Date() } });
  await audit('login_success', req, user.id);

  res.json({
    access_token:  createAccessToken(user.id, user.isAdmin),
    refresh_token: raw,
    token_type:    'Bearer',
    expires_in:    parseInt(process.env.ACCESS_TTL_MIN || '15') * 60,
  });
});

// POST /api/auth/refresh
router.post('/refresh', async (req, res) => {
  const parse = RefreshSchema.safeParse(req.body);
  if (!parse.success) return res.status(400).json({ detail: 'refresh_token requis' });

  const session = await prisma.userSession.findUnique({
    where:   { tokenHash: hashToken(parse.data.refresh_token) },
    include: { user: true },
  });

  if (!session || session.revoked || session.expiresAt < new Date()) {
    return res.status(401).json({ detail: 'Session expirée ou invalide' });
  }
  if (!session.user.isActive) {
    return res.status(401).json({ detail: 'Utilisateur inactif' });
  }

  // Rotation : révoque l'ancien, crée un nouveau
  const { raw, hash, expiresAt } = generateRefreshToken();
  await prisma.$transaction([
    prisma.userSession.update({ where: { id: session.id }, data: { revoked: true } }),
    prisma.userSession.create({
      data: {
        userId:    session.userId,
        tokenHash: hash,
        userAgent: session.userAgent,
        ipAddress: session.ipAddress,
        expiresAt,
      },
    }),
  ]);

  res.json({
    access_token:  createAccessToken(session.user.id, session.user.isAdmin),
    refresh_token: raw,
    token_type:    'Bearer',
    expires_in:    parseInt(process.env.ACCESS_TTL_MIN || '15') * 60,
  });
});

// POST /api/auth/logout
router.post('/logout', async (req, res) => {
  const parse = RefreshSchema.safeParse(req.body);
  if (!parse.success) return res.json({ message: 'Déconnecté' });

  await prisma.userSession.updateMany({
    where: { tokenHash: hashToken(parse.data.refresh_token) },
    data:  { revoked: true },
  });

  res.json({ message: 'Déconnecté' });
});

// POST /api/auth/forgot-password
router.post('/forgot-password', authLimiter, async (req, res) => {
  const parse = ForgotSchema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: 'Email invalide' });

  const SAFE = { message: "Si cet email est associé à un compte, un lien de réinitialisation vous a été envoyé." };

  const user = await prisma.user.findUnique({ where: { email: parse.data.email } });
  await audit('forgot_password', req, null, { email: parse.data.email });

  if (user?.isActive) {
    const { raw, hash, expiresAt } = generateVerificationToken();
    await prisma.verificationToken.create({
      data: { userId: user.id, tokenHash: hash, purpose: 'password_reset', expiresAt },
    });
    sendPasswordResetEmail(parse.data.email, raw).catch(err =>
      console.error('[MAILER] Erreur envoi reset:', err.message)
    );
  }

  res.json(SAFE);
});

// POST /api/auth/reset-password
router.post('/reset-password', authLimiter, async (req, res) => {
  const parse = ResetSchema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: parse.error.errors[0].message });

  const vt = await prisma.verificationToken.findUnique({
    where: { tokenHash: hashToken(parse.data.token) },
  });

  if (!vt || vt.purpose !== 'password_reset' || vt.used || vt.expiresAt < new Date()) {
    return res.status(400).json({ detail: 'Lien invalide ou expiré' });
  }

  await prisma.$transaction([
    prisma.user.update({
      where: { id: vt.userId },
      data:  { passwordHash: await hashPassword(parse.data.password) },
    }),
    prisma.verificationToken.update({ where: { id: vt.id }, data: { used: true } }),
    prisma.userSession.updateMany({ where: { userId: vt.userId }, data: { revoked: true } }),
  ]);

  res.json({ message: 'Mot de passe réinitialisé. Vous pouvez maintenant vous connecter.' });
});

export default router;
