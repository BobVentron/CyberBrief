// src/auth/security.js — JWT, bcrypt, tokens sécurisés
import crypto    from 'crypto';
import bcrypt    from 'bcryptjs';
import jwt       from 'jsonwebtoken';

const JWT_SECRET      = process.env.JWT_SECRET;
const ACCESS_TTL_MIN  = parseInt(process.env.ACCESS_TTL_MIN  || '15');
const REFRESH_TTL_DAY = parseInt(process.env.REFRESH_TTL_DAYS || '30');

if (!JWT_SECRET) throw new Error('JWT_SECRET manquant dans les variables d\'environnement');

// Passwords
/** bcrypt cost=12 — résistant aux attaques GPU */
export async function hashPassword(plain) {
  return bcrypt.hash(plain, 12);
}

/** Comparaison en temps constant */
export async function verifyPassword(plain, hashed) {
  try { return await bcrypt.compare(plain, hashed); }
  catch { return false; }
}

// JWT Access Token
export function createAccessToken(userId, isAdmin = false) {
  return jwt.sign(
    { sub: userId, admin: isAdmin, type: 'access', jti: crypto.randomUUID() },
    JWT_SECRET,
    { expiresIn: `${ACCESS_TTL_MIN}m`, algorithm: 'HS256' }
  );
}

export function decodeAccessToken(token) {
  try {
    const payload = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] });
    if (payload.type !== 'access') throw new Error('Type invalide');
    return payload;
  } catch (err) {
    const e = new Error(err.name === 'TokenExpiredError' ? 'Token expiré' : 'Token invalide');
    e.status = 401;
    throw e;
  }
}

// Refresh Token
/**
 * Génère un refresh token.
 * @returns {{ raw: string, hash: string, expiresAt: Date }}
 * On ne stocke QUE le hash SHA-256 en base — jamais le token brut.
 */
export function generateRefreshToken() {
  const raw      = crypto.randomBytes(64).toString('base64url');
  const hash     = hashToken(raw);
  const expiresAt = new Date(Date.now() + REFRESH_TTL_DAY * 86400 * 1000);
  return { raw, hash, expiresAt };
}

// Verification / Reset Tokens
/** Token email verify / reset password (24h) */
export function generateVerificationToken() {
  const raw      = crypto.randomBytes(48).toString('base64url');
  const hash     = hashToken(raw);
  const expiresAt = new Date(Date.now() + 24 * 3600 * 1000);
  return { raw, hash, expiresAt };
}

// Utilitaires
export function hashToken(raw) {
  return crypto.createHash('sha256').update(raw).digest('hex');
}

// Auth Middleware
export function requireAuth(req, res, next) {
  const header = req.headers.authorization;
  if (!header?.startsWith('Bearer ')) {
    return res.status(401).json({ detail: 'Authentification requise' });
  }
  try {
    req.user = decodeAccessToken(header.slice(7));
    next();
  } catch (err) {
    res.status(err.status || 401).json({ detail: err.message });
  }
}

export function requireAdmin(req, res, next) {
  requireAuth(req, res, () => {
    if (!req.user?.admin) {
      return res.status(403).json({ detail: 'Accès réservé aux administrateurs' });
    }
    next();
  });
}
