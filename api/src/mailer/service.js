// src/mailer/service.js — Envoi SMTP via Nodemailer
// Compatible Gmail / OVH / Mailgun / Brevo — configurable via .env
import nodemailer from 'nodemailer';
import { readFile } from 'fs/promises';
import path from 'path';

// Transporter SMTP
function createTransporter() {
  const port    = parseInt(process.env.SMTP_PORT || '587');
  const tls     = process.env.SMTP_TLS || 'starttls';
  const secure  = tls === 'ssl';   // true = port 465, false = STARTTLS sur 587

  return nodemailer.createTransport({
    host:   process.env.SMTP_HOST || 'smtp.gmail.com',
    port,
    secure,
    auth: {
      user: process.env.SMTP_USER     || '',
      pass: process.env.SMTP_PASSWORD || '',
    },
    tls: { rejectUnauthorized: true },
  });
}

const FROM_NAME  = process.env.SMTP_FROM_NAME || 'CyberBrief';
const FROM_EMAIL = process.env.SMTP_FROM || process.env.SMTP_USER || '';
const BASE_URL   = process.env.REPORT_BASE_URL || 'http://localhost:8080';

// Template HTML commun
function emailWrapper(content) {
  return `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#07080a;font-family:'Courier New',monospace;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#0c0e12;border:1px solid #1c2028;">
        <tr>
          <td style="padding:24px 32px;border-bottom:1px solid #1c2028;">
            <span style="font-family:Georgia,serif;font-size:22px;font-weight:700;
                         color:#eef2f7;letter-spacing:-0.5px;">
              Cyber<span style="color:#00d4ff;">Brief</span>
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;color:#b8c4d0;font-size:14px;line-height:1.7;">
            ${content}
          </td>
        </tr>
        <tr>
          <td style="padding:18px 32px;border-top:1px solid #1c2028;">
            <p style="margin:0;font-size:11px;color:#4a5568;">
              CyberBrief — Veille cybersécurité automatisée<br>
              <a href="${BASE_URL}" style="color:#00d4ff;">Accéder à la plateforme</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;
}

// Envoi générique
async function sendMail({ to, subject, html, text, attachments = [] }) {
  if (!process.env.SMTP_USER || !process.env.SMTP_PASSWORD) {
    console.warn('[MAILER] SMTP non configuré — email ignoré');
    return;
  }

  const transporter = createTransporter();
  await transporter.sendMail({
    from:        `"${FROM_NAME}" <${FROM_EMAIL}>`,
    to:          Array.isArray(to) ? to.join(', ') : to,
    subject,
    text,
    html,
    attachments,
  });
}

// Emails transactionnels
export async function sendVerificationEmail(email, token) {
  const link = `${BASE_URL}/verify-email?token=${encodeURIComponent(token)}`;
  const html = emailWrapper(`
    <p style="color:#eef2f7;font-size:16px;font-weight:600;margin:0 0 14px;">
      Vérifiez votre adresse email
    </p>
    <p>Merci de votre inscription sur CyberBrief.</p>
    <p>Cliquez sur le bouton ci-dessous pour activer votre compte :</p>
    <p style="margin:24px 0;">
      <a href="${link}"
         style="display:inline-block;background:#00d4ff;color:#07080a;
                padding:12px 28px;text-decoration:none;font-weight:700;
                font-size:13px;letter-spacing:1px;">
        ACTIVER MON COMPTE →
      </a>
    </p>
    <p style="font-size:12px;color:#4a5568;">
      Ce lien expire dans 24 heures.<br>
      Si vous n'avez pas créé de compte, ignorez cet email.
    </p>
  `);

  await sendMail({
    to:      email,
    subject: '[CyberBrief] Vérifiez votre adresse email',
    html,
    text: `Activez votre compte CyberBrief : ${link}\n\nLien valable 24h.`,
  });
}

export async function sendPasswordResetEmail(email, token) {
  const link = `${BASE_URL}/reset-password?token=${encodeURIComponent(token)}`;
  const html = emailWrapper(`
    <p style="color:#eef2f7;font-size:16px;font-weight:600;margin:0 0 14px;">
      Réinitialisation du mot de passe
    </p>
    <p>Une demande de réinitialisation a été effectuée pour ce compte.</p>
    <p style="margin:24px 0;">
      <a href="${link}"
         style="display:inline-block;background:#00d4ff;color:#07080a;
                padding:12px 28px;text-decoration:none;font-weight:700;
                font-size:13px;letter-spacing:1px;">
        RÉINITIALISER MON MOT DE PASSE →
      </a>
    </p>
    <p style="font-size:12px;color:#4a5568;">
      Ce lien expire dans 24 heures.<br>
      Si vous n'avez pas effectué cette demande, votre compte est en sécurité.
    </p>
  `);

  await sendMail({
    to:      email,
    subject: '[CyberBrief] Réinitialisation de votre mot de passe',
    html,
    text: `Réinitialisez votre mot de passe : ${link}\n\nLien valable 24h.`,
  });
}

// Envoi rapport
export async function sendReportEmail({ recipients, reportPath, reportType, reportTitle }) {
  let htmlContent;
  try {
    htmlContent = await readFile(reportPath, 'utf-8');
  } catch (err) {
    console.error(`[MAILER] Impossible de lire ${reportPath}:`, err.message);
    return false;
  }

  const now      = new Date();
  const dateStr  = now.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const badge    = reportType === 'weekly' ? '🗓️ Récap Hebdo' : '🛡️ Brief Quotidien';
  const subject  = `[CyberBrief] ${badge} — ${dateStr}`;
  const filename = path.basename(reportPath);
  const url      = `${BASE_URL}/reports/${filename}`;

  // Styles inlinés pour la compatibilité email (Gmail, Outlook...)
  const styledContent = htmlContent
    .replace(/<h2>/g, '<h2 style="color:#00d4ff;font-size:16px;font-family:\'Courier New\',monospace;border-bottom:1px solid #1c2028;padding-bottom:6px;margin:24px 0 12px;">')
    .replace(/<h3>/g, '<h3 style="color:#eef2f7;font-size:14px;font-family:\'Courier New\',monospace;margin:16px 0 8px;">')
    .replace(/<p>/g, '<p style="margin:8px 0;line-height:1.6;">')
    .replace(/<ul>/g, '<ul style="margin:8px 0;padding-left:20px;">')
    .replace(/<li>/g, '<li style="margin:4px 0;">');

  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#07080a;font-family:'Courier New',monospace;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="680" cellpadding="0" cellspacing="0"
             style="background:#0c0e12;border:1px solid #1c2028;">
        <tr>
          <td style="padding:24px 32px;border-bottom:1px solid #1c2028;">
            <span style="font-family:Georgia,serif;font-size:22px;font-weight:700;
                         color:#eef2f7;letter-spacing:-0.5px;">
              Cyber<span style="color:#00d4ff;">Brief</span>
            </span>
            <span style="float:right;font-size:12px;color:#4a5568;line-height:2.2;">
              ${badge} · ${dateStr}
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;color:#b8c4d0;font-size:13px;line-height:1.7;">
            ${styledContent}
          </td>
        </tr>
        <tr>
          <td style="padding:18px 32px;border-top:1px solid #1c2028;">
            <p style="margin:0 0 8px;font-size:11px;color:#4a5568;">
              <a href="${url}" style="color:#00d4ff;">→ Voir le rapport en ligne</a>
              &nbsp;·&nbsp;
              <a href="${BASE_URL}/dashboard" style="color:#00d4ff;">Gérer mes préférences</a>
            </p>
            <p style="margin:0;font-size:10px;color:#2d3748;">
              CyberBrief — Veille cybersécurité automatisée · ${BASE_URL}
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;

  try {
    await sendMail({
      to:      recipients,
      subject,
      html,
      text:    `Rapport disponible : ${url}`,
    });
    return true;
  } catch (err) {
    console.error(`[MAILER] Échec envoi à ${recipients}:`, err.message);
    return false;
  }
}
