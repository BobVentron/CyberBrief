-- Migration 0004 : table push_subscriptions (Web Push / PWA)

CREATE TABLE "push_subscriptions" (
    "id"          TEXT         NOT NULL,
    "endpoint"    TEXT         NOT NULL,
    "p256dh"      TEXT         NOT NULL,
    "auth"        TEXT         NOT NULL,
    "user_id"     TEXT,
    "user_agent"  TEXT,
    "created_at"  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_seen_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "push_subscriptions_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "push_subscriptions_endpoint_key" ON "push_subscriptions"("endpoint");
CREATE INDEX "push_subscriptions_user_id_idx" ON "push_subscriptions"("user_id");

ALTER TABLE "push_subscriptions"
    ADD CONSTRAINT "push_subscriptions_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id")
    ON DELETE SET NULL ON UPDATE CASCADE;

-- Compteur d'installations PWA (rough, via settings)
INSERT INTO "settings" ("key", "value", "updated_at") VALUES
    ('pwa_installs', '0', CURRENT_TIMESTAMP)
ON CONFLICT ("key") DO NOTHING;
