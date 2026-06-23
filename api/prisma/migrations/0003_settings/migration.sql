-- Migration 0003 : table settings (config dynamique)

CREATE TABLE "settings" (
    "key"        TEXT         NOT NULL,
    "value"      TEXT         NOT NULL,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "settings_pkey" PRIMARY KEY ("key")
);

-- Valeurs par défaut
INSERT INTO "settings" ("key", "value", "updated_at") VALUES
    ('cron_schedule',    '0 21 * * *',        CURRENT_TIMESTAMP),
    ('claude_model',     'claude-sonnet-4-6',  CURRENT_TIMESTAMP),
    ('trigger_now',      'false',              CURRENT_TIMESTAMP),
    ('last_run_at',      '',                   CURRENT_TIMESTAMP),
    ('last_run_status',  'idle',               CURRENT_TIMESTAMP),
    ('last_run_articles','0',                  CURRENT_TIMESTAMP),
    ('last_run_cves',    '0',                  CURRENT_TIMESTAMP),
    ('next_run',         '',                   CURRENT_TIMESTAMP)
ON CONFLICT ("key") DO NOTHING;
