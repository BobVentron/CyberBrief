-- Migration : ajout table api_usage_logs (suivi coûts Claude API)

CREATE TABLE "api_usage_logs" (
    "id"            SERIAL       NOT NULL,
    "report_file"   TEXT         NOT NULL,
    "report_type"   TEXT         NOT NULL,
    "input_tokens"  INTEGER      NOT NULL,
    "output_tokens" INTEGER      NOT NULL,
    "total_tokens"  INTEGER      NOT NULL,
    "cost_usd"      DOUBLE PRECISION NOT NULL,
    "model_used"    TEXT         NOT NULL,
    "created_at"    TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "api_usage_logs_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "api_usage_logs_created_at_idx" ON "api_usage_logs"("created_at");
