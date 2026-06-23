// src/internal/routes.js — Routes appelées par le daemon Python uniquement
// Authentification : X-Internal-Token
import { Router } from 'express';
import prisma from '../db/prisma.js';

const router = Router();
const INTERNAL_TOKEN = process.env.INTERNAL_API_TOKEN || '';

function checkToken(req, res, next) {
  const token = req.headers['x-internal-token'];
  if (!INTERNAL_TOKEN || token !== INTERNAL_TOKEN) {
    return res.status(403).json({ detail: 'Token interne invalide' });
  }
  next();
}

router.use(checkToken);

// GET /api/internal/settings/:key
router.get('/settings/:key', async (req, res) => {
  const s = await prisma.setting.findUnique({ where: { key: req.params.key } });
  res.json({ value: s?.value ?? null });
});

// PUT /api/internal/settings/:key
router.put('/settings/:key', async (req, res) => {
  const { value } = req.body;
  if (typeof value !== 'string') {
    return res.status(422).json({ detail: 'value doit être une chaîne' });
  }
  await prisma.setting.upsert({
    where:  { key: req.params.key },
    create: { key: req.params.key, value },
    update: { value },
  });
  res.json({ ok: true });
});

// POST /api/internal/api-usage — appelé par le daemon Python après chaque génération
router.post('/api-usage', async (req, res) => {
  const { z } = await import('zod');
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

  const PRICING = {
    'claude-sonnet-4-6':         { in: 3,    out: 15  },
    'claude-sonnet-4-5':         { in: 3,    out: 15  },
    'claude-sonnet-4-20250514':  { in: 3,    out: 15  },
    'claude-opus-4-8':           { in: 15,   out: 75  },
    'claude-opus-4-5':           { in: 15,   out: 75  },
    'claude-opus-4-20250514':    { in: 15,   out: 75  },
    'claude-haiku-4-5-20251001': { in: 0.8,  out: 4   },
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

export default router;
