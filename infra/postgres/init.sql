CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','succeeded','failed','timeout')),
    final_output JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE steps (
    step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(run_id) ON DELETE CASCADE,
    parent_step_id UUID REFERENCES steps(step_id),
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    input JSONB,
    output JSONB,
    error TEXT,
    latency_ms INT,
    tokens JSONB,
    cost_usd FLOAT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);
CREATE INDEX idx_steps_run_id ON steps(run_id);