// src/app.js — CyberBrief API entry point
import 'dotenv/config';
import express      from 'express';
import cors         from 'cors';
import helmet       from 'helmet';
import { rateLimit } from 'express-rate-limit';

import authRouter     from './auth/routes.js';
import usersRouter    from './users/routes.js';
import adminRouter    from './admin/routes.js';
import mailerRouter   from './mailer/routes.js';
import internalRouter from './internal/routes.js';

const app  = express();
const PORT = process.env.PORT || 8000;

// Trust proxy (nginx devant)
app.set('trust proxy', 1);

// Sécurité HTTP
app.use(helmet({
  crossOriginResourcePolicy: { policy: 'cross-origin' },
}));

// CORS
const allowedOrigins = (process.env.ALLOWED_ORIGINS || 'http://localhost:8080').split(',');
app.use(cors({
  origin:      allowedOrigins,
  credentials: true,
  methods:     ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-ID'],
}));

// Body parser
app.use(express.json({ limit: '64kb' }));

// Rate limiting global
const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,  // 15 min
  max:      200,
  standardHeaders: true,
  legacyHeaders:   false,
  message: { detail: 'Trop de requêtes, veuillez réessayer dans quelques minutes.' },
});
app.use('/api/', globalLimiter);

// Routes
app.use('/api/auth',     authRouter);
app.use('/api/users',    usersRouter);
app.use('/api/admin',    adminRouter);
app.use('/api/mailer',   mailerRouter);
app.use('/api/internal', internalRouter);

// Healthcheck
app.get('/api/health', (_req, res) => res.json({ status: 'ok', service: 'cyberbrief-api' }));

// 404
app.use((_req, res) => res.status(404).json({ detail: 'Route introuvable' }));

// Error handler
app.use((err, _req, res, _next) => {
  console.error('[ERROR]', err);
  res.status(err.status || 500).json({ detail: err.message || 'Erreur interne' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[API] CyberBrief API démarrée sur le port ${PORT}`);
});

export default app;
