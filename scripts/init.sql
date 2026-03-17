CREATE TABLE IF NOT EXISTS fraud_rules_config (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ZAR',
    merchant_id VARCHAR(50),
    merchant_category VARCHAR(50),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS fraud_alerts (
    id UUID PRIMARY KEY, 
    transaction_id UUID REFERENCES transactions(id) ON DELETE CASCADE,
    rule_name VARCHAR(50) NOT NULL,
    is_flagged BOOLEAN NOT NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blacklisted_merchants (
    id SERIAL PRIMARY KEY,
    merchant_id VARCHAR(50) UNIQUE NOT NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- This table tracks which transactions have been processed by which rules to ensure idempotency.
CREATE TABLE IF NOT EXISTS processed_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL,
    rule_name VARCHAR(50) NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tx_rule UNIQUE (transaction_id, rule_name)
);

INSERT INTO fraud_rules_config  (name, enabled) 
VALUES
    ('HIGH_AMOUNT_RULE', TRUE),
    ('BLACKLIST_RULE', TRUE),
    ('VELOCITY_RULE', TRUE);


-- blacklist data for testing and demo purposes
INSERT INTO blacklisted_merchants (merchant_id, reason)
VALUES 
    ('merch_999', 'Confirmed Phishing Site - Operation Red October'),
    ('scam_central_01', 'Associated with known card-cloning ring'),
    ('fake_invest_ltd', 'Unregulated financial entity - Ponzi scheme alert'),
    ('dark_web_gateway', 'High frequency of stolen credential usage'),
    ('crypto_mixer_xyz', 'High-risk anonymity service'),
    ('anonymous_vpn_provider', 'Commonly used for location spoofing')
ON CONFLICT (merchant_id) DO NOTHING;

CREATE INDEX idx_fraud_alerts_transaction_id ON fraud_alerts(transaction_id);
CREATE INDEX idx_processed_events_tx ON processed_events(transaction_id);