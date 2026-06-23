// src/mailer/routes.js — Route interne : envoi rapport déclenché par le cron
import { Router } from 'express';
import path       from 'path';
import { existsSync } from 'fs';
import { z }      from 'zod';
import prisma     from '../db/prisma.js';
import { sendReportEmail } from './service.js';

const router = Router();

const INTERNAL_TOKEN = process.env.INTERNAL_API_TOKEN || '';

// Middleware : vérifie le token interne
function checkInternalToken(req, res, next) {
  const token = req.headers['x-internal-token'];
  if (!INTERNAL_TOKEN || token !== INTERNAL_TOKEN) {
    return res.status(403).json({ detail: 'Token interne invalide' });
  }
  next();
}

const SendReportSchema = z.object({
  report_file:  z.string().min(1),
  report_type:  z.enum(['daily', 'weekly']),
  report_title: z.string().min(1),
});

// POST /api/mailer/send-report
router.post('/send-report', checkInternalToken, async (req, res) => {
  const parse = SendReportSchema.safeParse(req.body);
  if (!parse.success) return res.status(422).json({ detail: parse.error.errors[0].message });

  const { report_file, report_type, report_title } = parse.data;
  const reportsDir  = process.env.REPORTS_DIR || '/app/reports';
  const reportPath  = path.join(reportsDir, report_file);

  if (!existsSync(reportPath)) {
    return res.status(404).json({ detail: `Rapport introuvable : ${report_file}` });
  }

  // Récupère tous les users actifs avec préférences activées pour ce type
  const prefs = await prisma.mailPreference.findMany({
    where: {
      user: { isActive: true },
      ...(report_type === 'daily'  ? { sendDaily:  true } : {}),
      ...(report_type === 'weekly' ? { sendWeekly: true } : {}),
    },
    include: { user: true },
  });

  let sent   = 0;
  let failed = 0;

  for (const pref of prefs) {
    const recipients = pref.recipientEmails;
    if (!recipients.length) continue;

    const success = await sendReportEmail({
      recipients,
      reportPath,
      reportType:  report_type,
      reportTitle: report_title,
    });

    for (const recipient of recipients) {
      await prisma.mailSendLog.create({
        data: {
          userId:     pref.userId,
          recipient,
          reportFile: report_file,
          reportType: report_type,
          status:     success ? 'sent' : 'failed',
        },
      });
    }

    success ? sent++ : failed++;
  }

  // Destinataires admin supplémentaires (extra_recipients setting)
  const extraSetting = await prisma.setting.findUnique({ where: { key: 'extra_recipients' } });
  const extraEmails  = extraSetting?.value ? JSON.parse(extraSetting.value) : [];
  if (extraEmails.length) {
    const success = await sendReportEmail({
      recipients:  extraEmails,
      reportPath,
      reportType:  report_type,
      reportTitle: report_title,
    });
    for (const recipient of extraEmails) {
      await prisma.mailSendLog.create({
        data: { userId: null, recipient, reportFile: report_file, reportType: report_type, status: success ? 'sent' : 'failed' },
      });
    }
  }

  res.json({
    report:           report_file,
    users_notified:   sent,
    users_failed:     failed,
    total_users:      prefs.length,
    extra_recipients: extraEmails.length,
  });
});

export default router;
