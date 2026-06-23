// src/admin/routes.js — Panel admin complet
// Stats Claude API, coûts, graphiques, users, logs
import { Router } from 'express';
import { z }      from 'zod';
import prisma     from '../db/prisma.js';

const router = Router();

const ADMIN_TOKEN = process.env.ADMIN_API_TOKEN || '';

function checkAdminToken(req, res, next) {
  const token = req.headers['x-admin-token'];
  if (!ADMIN_TOKEN || token !== ADMIN_TOKEN) {
    return res.status(403).json({ detail: 'Accès refusé' });
  }
  next();
}

router.use(checkAdminToken);

// GET /api/admin/stats
router.get('/stats', async (_req, res) => {
  const now   = new Date();
  const day30 = new Date(now - 30 * 86400000);
  const day7  = new Date(now - 7  * 86400000);
  const som   = new Date(now.getFullYear(), now.getMonth(), 1); // Start of month

  const [
    totalUsers, activeUsers, adminUsers,
    newUsers30d, newUsers7d,
    mailsSent, mailsFailed, mailsSent30d,
    totalReports,
    totalCostRaw, costThisMonth,
    avgIn, avgOut,
    lastLogin, lastAudit,
  ] = await Promise.all([
    prisma.user.count(),
    prisma.user.count({ where: { isActive: true  } }),
    prisma.user.count({ where: { isAdmin:  true  } }),
    prisma.user.count({ where: { createdAt: { gte: day30 } } }),
    prisma.user.count({ where: { createdAt: { gte: day7  } } }),
    prisma.mailSendLog.count({ where: { status: 'sent'   } }),
    prisma.mailSendLog.count({ where: { status: 'failed' } }),
    prisma.mailSendLog.count({ where: { status: 'sent', sentAt: { gte: day30 } } }),
    prisma.apiUsageLog.count(),
    prisma.apiUsageLog.aggregate({ _sum: { costUsd: true } }),
    prisma.apiUsageLog.aggregate({ where: { createdAt: { gte: som } }, _sum: { costUsd: true } }),
    prisma.apiUsageLog.aggregate({ _avg: { inputTokens:  true } }),
    prisma.apiUsageLog.aggregate({ _avg: { outputTokens: true } }),
    prisma.user.findFirst({ where: { lastLoginAt: { not: null } }, orderBy: { lastLoginAt: 'desc' }, select: { lastLoginAt: true } }),
    prisma.auditLog.findFirst({ orderBy: { createdAt: 'desc' }, select: { createdAt: true } }),
  ]);

  res.json({
    users: {
      total: totalUsers, active: activeUsers,
      pending: totalUsers - activeUsers, admins: adminUsers,
      new_30d: newUsers30d, new_7d: newUsers7d,
    },
    mail: { sent: mailsSent, failed: mailsFailed, sent_30d: mailsSent30d },
    api: {
      total_reports:       totalReports,
      total_cost_usd:      totalCostRaw._sum.costUsd    || 0,
      cost_this_month_usd: costThisMonth._sum.costUsd   || 0,
      avg_input_tokens:    Math.round(avgIn._avg.inputTokens   || 0),
      avg_output_tokens:   Math.round(avgOut._avg.outputTokens || 0),
    },
    last_activity: {
      last_login: lastLogin?.lastLoginAt || null,
      last_audit: lastAudit?.createdAt   || null,
    },
  });
});

// GET /api/admin/charts/users  inscriptions 30j
router.get('/charts/users', async (_req, res) => {
  const days = 30;
  const from = new Date(Date.now() - days * 86400000);

  const rows = await prisma.$queryRaw`
    SELECT DATE_TRUNC('day', "created_at") AS day, COUNT(*)::int AS count
    FROM users WHERE "created_at" >= ${from}
    GROUP BY 1 ORDER BY 1 ASC`;

  const map = {};
  for (const r of rows) map[r.day.toISOString().slice(0, 10)] = r.count;

  const labels = [], data = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
    labels.push(d); data.push(map[d] || 0);
  }
  res.json({ labels, datasets: [{ label: 'Inscriptions', data }] });
});

// GET /api/admin/charts/activity  connexions 30j
router.get('/charts/activity', async (_req, res) => {
  const days = 30;
  const from = new Date(Date.now() - days * 86400000);

  const rows = await prisma.$queryRaw`
    SELECT DATE_TRUNC('day', "created_at") AS day, COUNT(*)::int AS count
    FROM audit_logs WHERE action = 'login_success' AND "created_at" >= ${from}
    GROUP BY 1 ORDER BY 1 ASC`;

  const map = {};
  for (const r of rows) map[r.day.toISOString().slice(0, 10)] = r.count;

  const labels = [], data = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
    labels.push(d); data.push(map[d] || 0);
  }
  res.json({ labels, datasets: [{ label: 'Connexions', data }] });
});

// GET /api/admin/charts/mails  envois 30j
router.get('/charts/mails', async (_req, res) => {
  const days = 30;
  const from = new Date(Date.now() - days * 86400000);

  const rows = await prisma.$queryRaw`
    SELECT DATE_TRUNC('day', "sent_at") AS day, status, COUNT(*)::int AS count
    FROM mail_send_logs WHERE "sent_at" >= ${from}
    GROUP BY 1, 2 ORDER BY 1 ASC`;

  const sentMap = {}, failedMap = {};
  for (const r of rows) {
    const d = r.day.toISOString().slice(0, 10);
    if (r.status === 'sent')   sentMap[d]   = r.count;
    if (r.status === 'failed') failedMap[d] = r.count;
  }

  const labels = [], sent = [], failed = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
    labels.push(d); sent.push(sentMap[d] || 0); failed.push(failedMap[d] || 0);
  }
  res.json({ labels, datasets: [
    { label: 'Envoyés', data: sent   },
    { label: 'Échoués', data: failed },
  ]});
});

// GET /api/admin/charts/costs  coûts API
router.get('/charts/costs', async (_req, res) => {
  const days = 30;
  const from = new Date(Date.now() - days * 86400000);

  const rows = await prisma.$queryRaw`
    SELECT DATE_TRUNC('day', "created_at") AS day,
           SUM("cost_usd")::float          AS cost,
           SUM("total_tokens")::int        AS tokens,
           COUNT(*)::int                   AS reports
    FROM api_usage_logs WHERE "created_at" >= ${from}
    GROUP BY 1 ORDER BY 1 ASC`;

  const costMap = {}, tokensMap = {}, reportsMap = {};
  for (const r of rows) {
    const d = r.day.toISOString().slice(0, 10);
    costMap[d]    = parseFloat((r.cost    || 0).toFixed(4));
    tokensMap[d]  = r.tokens  || 0;
    reportsMap[d] = r.reports || 0;
  }

  const labels = [], costData = [], tokensData = [], reportsData = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
    labels.push(d);
    costData.push(costMap[d]    || 0);
    tokensData.push(tokensMap[d]  || 0);
    reportsData.push(reportsMap[d] || 0);
  }

  // Détail des 20 derniers rapports
  const detail = await prisma.apiUsageLog.findMany({
    orderBy: { createdAt: 'desc' }, take: 20,
    select: {
      reportFile: true, reportType: true, modelUsed: true,
      inputTokens: true, outputTokens: true, totalTokens: true,
      costUsd: true, createdAt: true,
    },
  });

  res.json({
    labels,
    datasets: [
      { label: 'Coût USD', data: costData    },
      { label: 'Tokens',   data: tokensData  },
      { label: 'Rapports', data: reportsData },
    ],
    detail: detail.map(l => ({
      date:          l.createdAt.toISOString().slice(0, 10),
      report:        l.reportFile,
      type:          l.reportType,
      model:         l.modelUsed,
      input_tokens:  l.inputTokens,
      output_tokens: l.outputTokens,
      total_tokens:  l.totalTokens,
      cost_usd:      l.costUsd,
    })),
  });
});

// GET /api/admin/users
router.get('/users', async (req, res) => {
  const page   = Math.max(1, parseInt(req.query.page  || '1'));
  const limit  = Math.min(100, Math.max(1, parseInt(req.query.limit || '20')));
  const search = req.query.search?.trim() || '';
  const where  = search ? { email: { contains: search, mode: 'insensitive' } } : {};

  const [total, users] = await Promise.all([
    prisma.user.count({ where }),
    prisma.user.findMany({
      where, orderBy: { createdAt: 'desc' },
      skip: (page - 1) * limit, take: limit,
      select: {
        id: true, email: true, isActive: true, isAdmin: true,
        createdAt: true, lastLoginAt: true, deletionRequestedAt: true,
      },
    }),
  ]);

  res.json({ total, page, limit, users: users.map(u => ({
    id: u.id, email: u.email,
    is_active: u.isActive, is_admin: u.isAdmin,
    created_at: u.createdAt, last_login: u.lastLoginAt,
    deletion_requested: u.deletionRequestedAt !== null,
  }))});
});

router.patch('/users/:id', async (req, res) => {
  const Schema = z.object({ is_active: z.boolean().optional(), is_admin: z.boolean().optional() });
  const parse  = Schema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: parse.error.errors[0].message });

  const user = await prisma.user.findUnique({ where: { id: req.params.id } });
  if (!user) return res.status(404).json({ detail: 'Utilisateur introuvable' });

  const data = {};
  if (parse.data.is_active !== undefined) data.isActive = parse.data.is_active;
  if (parse.data.is_admin  !== undefined) data.isAdmin  = parse.data.is_admin;

  await prisma.user.update({ where: { id: req.params.id }, data });
  res.json({ message: 'Mis à jour' });
});

router.delete('/users/:id', async (req, res) => {
  const user = await prisma.user.findUnique({ where: { id: req.params.id } });
  if (!user) return res.status(404).json({ detail: 'Utilisateur introuvable' });

  await prisma.auditLog.updateMany({ where: { userId: req.params.id }, data: { userId: null } });
  await prisma.user.delete({ where: { id: req.params.id } });
  res.json({ message: 'Supprimé' });
});

// GET /api/admin/audit
router.get('/audit', async (req, res) => {
  const page  = Math.max(1, parseInt(req.query.page  || '1'));
  const limit = Math.min(200, Math.max(1, parseInt(req.query.limit || '50')));
  const where = {};
  if (req.query.action)  where.action = { contains: req.query.action,  mode: 'insensitive' };
  if (req.query.user_id) where.userId = req.query.user_id;

  const [total, logs] = await Promise.all([
    prisma.auditLog.count({ where }),
    prisma.auditLog.findMany({ where, orderBy: { createdAt: 'desc' }, skip: (page-1)*limit, take: limit }),
  ]);

  res.json({ total, page, logs: logs.map(l => ({
    id: l.id, user_id: l.userId, action: l.action,
    ip_address: l.ipAddress, created_at: l.createdAt, details: l.details,
  }))});
});

// GET /api/admin/mail-logs
router.get('/mail-logs', async (req, res) => {
  const page  = Math.max(1, parseInt(req.query.page  || '1'));
  const limit = Math.min(200, Math.max(1, parseInt(req.query.limit || '50')));

  const [total, logs] = await Promise.all([
    prisma.mailSendLog.count(),
    prisma.mailSendLog.findMany({ orderBy: { sentAt: 'desc' }, skip: (page-1)*limit, take: limit }),
  ]);

  res.json({ total, page, logs: logs.map(l => ({
    id: l.id, user_id: l.userId, recipient: l.recipient,
    report_file: l.reportFile, report_type: l.reportType,
    status: l.status, error: l.error, sent_at: l.sentAt,
  }))});
});

// POST /api/admin/api-usage  appelé par gotify.py
router.post('/api-usage', async (req, res) => {
  // Accepte aussi le token interne (cron Python)
  const internalToken = process.env.INTERNAL_API_TOKEN || '';
  const token = req.headers['x-internal-token'] || req.headers['x-admin-token'];
  if (!token || (token !== internalToken && token !== ADMIN_TOKEN)) {
    return res.status(403).json({ detail: 'Token invalide' });
  }

  const Schema = z.object({
    report_file:   z.string(),
    report_type:   z.string(),
    input_tokens:  z.number().int(),
    output_tokens: z.number().int(),
    model_used:    z.string(),
  });
  const parse = Schema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: parse.error.errors[0].message });

  const { report_file, report_type, input_tokens, output_tokens, model_used } = parse.data;

  // Tarifs Claude Anthropic (USD / 1M tokens) — maj mai 2026
  const PRICING = {
    'claude-sonnet-4-6':         { in: 3,   out: 15  },
    'claude-sonnet-4-5':         { in: 3,   out: 15  },
    'claude-sonnet-4-20250514':  { in: 3,   out: 15  },
    'claude-opus-4-8':           { in: 15,  out: 75  },
    'claude-opus-4-5':           { in: 15,  out: 75  },
    'claude-opus-4-20250514':    { in: 15,  out: 75  },
    'claude-haiku-4-5-20251001': { in: 0.8, out: 4   },
  };
  const rates   = PRICING[model_used] || { in: 3, out: 15 };
  const costUsd = (input_tokens * rates.in + output_tokens * rates.out) / 1_000_000;

  await prisma.apiUsageLog.create({
    data: {
      reportFile:   report_file,
      reportType:   report_type,
      inputTokens:  input_tokens,
      outputTokens: output_tokens,
      totalTokens:  input_tokens + output_tokens,
      costUsd,
      modelUsed:    model_used,
    },
  });

  res.json({ cost_usd: parseFloat(costUsd.toFixed(6)), total_tokens: input_tokens + output_tokens });
});

// GET /api/admin/settings
router.get('/settings', async (_req, res) => {
  const rows = await prisma.setting.findMany();
  const obj  = {};
  for (const r of rows) obj[r.key] = r.value;
  res.json(obj);
});

// PUT /api/admin/settings/:key
const EDITABLE_KEYS = ['cron_schedule', 'claude_model'];

router.put('/settings/:key', async (req, res) => {
  if (!EDITABLE_KEYS.includes(req.params.key)) {
    return res.status(422).json({ detail: 'Clé non modifiable depuis l\'admin' });
  }
  const { value } = req.body;
  if (typeof value !== 'string' || !value.trim()) {
    return res.status(422).json({ detail: 'value requis' });
  }

  // Validation légère du cron si c'est le planning
  if (req.params.key === 'cron_schedule') {
    const parts = value.trim().split(/\s+/);
    if (parts.length !== 5) {
      return res.status(422).json({ detail: 'Expression cron invalide (5 champs requis)' });
    }
  }

  await prisma.setting.upsert({
    where:  { key: req.params.key },
    create: { key: req.params.key, value: value.trim() },
    update: { value: value.trim() },
  });
  res.json({ ok: true });
});

// POST /api/admin/trigger  déclenchement immédiat
router.post('/trigger', async (_req, res) => {
  await prisma.setting.upsert({
    where:  { key: 'trigger_now' },
    create: { key: 'trigger_now', value: 'true' },
    update: { value: 'true' },
  });
  res.json({ ok: true, message: 'Déclenchement demandé — exécution dans les 30 secondes' });
});

// GET /api/admin/reports  liste depuis manifest.json
router.get('/reports', async (_req, res) => {
  const { readFile } = await import('fs/promises');
  const { existsSync } = await import('fs');
  const dir = process.env.REPORTS_DIR || '/app/reports';
  const p   = `${dir}/manifest.json`;
  if (!existsSync(p)) return res.json([]);
  try {
    const data = JSON.parse(await readFile(p, 'utf-8'));
    res.json(Array.isArray(data) ? data : []);
  } catch { res.json([]); }
});

// GET /api/admin/sources-health  santé des sources RSS
router.get('/sources-health', async (_req, res) => {
  const s = await prisma.setting.findUnique({ where: { key: 'last_sources_health' } });
  try {
    res.json(s?.value ? JSON.parse(s.value) : []);
  } catch { res.json([]); }
});

// GET /api/admin/logs/stream  SSE logs dernière exécution
router.get('/logs/stream', (req, res) => {
  res.setHeader('Content-Type',  'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection',    'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');   // désactive le buffering nginx
  res.flushHeaders();

  const send = async () => {
    try {
      const [logS, statusS, atS] = await Promise.all([
        prisma.setting.findUnique({ where: { key: 'last_run_log'    } }),
        prisma.setting.findUnique({ where: { key: 'last_run_status' } }),
        prisma.setting.findUnique({ where: { key: 'last_run_at'     } }),
      ]);
      res.write(`data: ${JSON.stringify({
        log:    logS?.value    || '',
        status: statusS?.value || 'idle',
        at:     atS?.value     || '',
      })}\n\n`);
    } catch { /* DB temporairement indispo */ }
  };

  send();
  const interval = setInterval(send, 2000);
  req.on('close', () => clearInterval(interval));
});

// GET /api/admin/recipients  destinataires supplémentaires
router.get('/recipients', async (_req, res) => {
  const s = await prisma.setting.findUnique({ where: { key: 'extra_recipients' } });
  try { res.json(s?.value ? JSON.parse(s.value) : []); }
  catch { res.json([]); }
});

// POST /api/admin/recipients
router.post('/recipients', async (req, res) => {
  const { email } = req.body || {};
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(422).json({ detail: 'Email invalide' });
  }
  const s    = await prisma.setting.findUnique({ where: { key: 'extra_recipients' } });
  const list = s?.value ? JSON.parse(s.value) : [];
  if (list.includes(email)) return res.status(409).json({ detail: 'Déjà présent' });
  list.push(email);
  await prisma.setting.upsert({
    where:  { key: 'extra_recipients' },
    create: { key: 'extra_recipients', value: JSON.stringify(list) },
    update: { value: JSON.stringify(list) },
  });
  res.json({ ok: true, recipients: list });
});

// DELETE /api/admin/recipients/:email
router.delete('/recipients/:email', async (req, res) => {
  const email = decodeURIComponent(req.params.email);
  const s     = await prisma.setting.findUnique({ where: { key: 'extra_recipients' } });
  const list  = s?.value ? JSON.parse(s.value) : [];
  const next  = list.filter(e => e !== email);
  await prisma.setting.upsert({
    where:  { key: 'extra_recipients' },
    create: { key: 'extra_recipients', value: JSON.stringify(next) },
    update: { value: JSON.stringify(next) },
  });
  res.json({ ok: true, recipients: next });
});

export default router;
