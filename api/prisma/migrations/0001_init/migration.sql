-- Migration initiale CyberBrief v2

CREATE TABLE "users" (
    "id"                    TEXT        NOT NULL,
    "email"                 TEXT        NOT NULL,
    "password_hash"         TEXT        NOT NULL,
    "is_active"             BOOLEAN     NOT NULL DEFAULT false,
    "is_admin"              BOOLEAN     NOT NULL DEFAULT false,
    "consent_given_at"      TIMESTAMP(3),
    "deletion_requested_at" TIMESTAMP(3),
    "last_login_at"         TIMESTAMP(3),
    "created_at"            TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at"            TIMESTAMP(3) NOT NULL,
    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

CREATE TABLE "user_sessions" (
    "id"          TEXT        NOT NULL,
    "user_id"     TEXT        NOT NULL,
    "token_hash"  TEXT        NOT NULL,
    "user_agent"  TEXT,
    "ip_address"  TEXT,
    "created_at"  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at"  TIMESTAMP(3) NOT NULL,
    "revoked"     BOOLEAN     NOT NULL DEFAULT false,
    CONSTRAINT "user_sessions_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "user_sessions_token_hash_key" ON "user_sessions"("token_hash");
CREATE INDEX "user_sessions_user_id_idx" ON "user_sessions"("user_id");

CREATE TABLE "mail_preferences" (
    "id"               TEXT        NOT NULL,
    "user_id"          TEXT        NOT NULL,
    "recipient_emails" TEXT[]      NOT NULL DEFAULT ARRAY[]::TEXT[],
    "send_daily"       BOOLEAN     NOT NULL DEFAULT true,
    "send_weekly"      BOOLEAN     NOT NULL DEFAULT true,
    "updated_at"       TIMESTAMP(3) NOT NULL,
    CONSTRAINT "mail_preferences_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "mail_preferences_user_id_key" ON "mail_preferences"("user_id");

CREATE TABLE "verification_tokens" (
    "id"         TEXT        NOT NULL,
    "user_id"    TEXT        NOT NULL,
    "token_hash" TEXT        NOT NULL,
    "purpose"    TEXT        NOT NULL,
    "expires_at" TIMESTAMP(3) NOT NULL,
    "used"       BOOLEAN     NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "verification_tokens_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "verification_tokens_token_hash_key" ON "verification_tokens"("token_hash");
CREATE INDEX "verification_tokens_user_id_idx" ON "verification_tokens"("user_id");

CREATE TABLE "audit_logs" (
    "id"         SERIAL      NOT NULL,
    "user_id"    TEXT,
    "action"     TEXT        NOT NULL,
    "ip_address" TEXT,
    "user_agent" TEXT,
    "details"    JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "audit_logs_user_id_idx"   ON "audit_logs"("user_id");
CREATE INDEX "audit_logs_created_at_idx" ON "audit_logs"("created_at");

CREATE TABLE "mail_send_logs" (
    "id"          SERIAL      NOT NULL,
    "user_id"     TEXT        NOT NULL,
    "recipient"   TEXT        NOT NULL,
    "report_file" TEXT        NOT NULL,
    "report_type" TEXT        NOT NULL,
    "status"      TEXT        NOT NULL,
    "error"       TEXT,
    "sent_at"     TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "mail_send_logs_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "mail_send_logs_user_id_idx" ON "mail_send_logs"("user_id");

-- Foreign keys
ALTER TABLE "user_sessions"     ADD CONSTRAINT "user_sessions_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "mail_preferences"  ADD CONSTRAINT "mail_preferences_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "verification_tokens" ADD CONSTRAINT "verification_tokens_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
