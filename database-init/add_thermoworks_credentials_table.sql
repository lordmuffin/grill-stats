-- Migration: Add ThermoWorks credentials table with encryption support
-- This table stores encrypted ThermoWorks user credentials with metadata

-- Create the thermoworks_credentials table
CREATE TABLE IF NOT EXISTS thermoworks_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Encrypted credential data (stored as encrypted strings from Vault Transit)
    encrypted_email TEXT NOT NULL,
    encrypted_password TEXT NOT NULL,
    
    -- Encryption metadata (stored as JSON)
    encryption_metadata JSONB NOT NULL,
    
    -- Credential status and validation
    is_active BOOLEAN DEFAULT TRUE,
    last_validated TIMESTAMP,
    validation_attempts INTEGER DEFAULT 0,
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure one credential per user
    UNIQUE(user_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_thermoworks_credentials_user_id ON thermoworks_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_thermoworks_credentials_active ON thermoworks_credentials(is_active);
CREATE INDEX IF NOT EXISTS idx_thermoworks_credentials_updated_at ON thermoworks_credentials(updated_at);

-- Create a trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_thermoworks_credentials_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_thermoworks_credentials_updated_at
    BEFORE UPDATE ON thermoworks_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_thermoworks_credentials_updated_at();

-- Add comments for documentation
COMMENT ON TABLE thermoworks_credentials IS 'Encrypted ThermoWorks user credentials with metadata';
COMMENT ON COLUMN thermoworks_credentials.encrypted_email IS 'ThermoWorks email encrypted using Vault Transit engine';
COMMENT ON COLUMN thermoworks_credentials.encrypted_password IS 'ThermoWorks password encrypted using Vault Transit engine';
COMMENT ON COLUMN thermoworks_credentials.encryption_metadata IS 'Metadata about encryption (key version, algorithm, timestamps)';
COMMENT ON COLUMN thermoworks_credentials.is_active IS 'Whether the credentials are active and valid';
COMMENT ON COLUMN thermoworks_credentials.last_validated IS 'Last time credentials were successfully validated';
COMMENT ON COLUMN thermoworks_credentials.validation_attempts IS 'Number of failed validation attempts';

-- Create a view for credential information without sensitive data
CREATE OR REPLACE VIEW thermoworks_credentials_info AS
SELECT 
    tc.id,
    tc.user_id,
    u.email as user_email,
    u.name as user_name,
    tc.is_active,
    tc.last_validated,
    tc.validation_attempts,
    tc.encryption_metadata->>'algorithm' as encryption_algorithm,
    tc.encryption_metadata->>'key_version' as encryption_key_version,
    tc.encryption_metadata->>'encrypted_at' as encrypted_at,
    tc.encryption_metadata->>'access_count' as access_count,
    tc.created_at,
    tc.updated_at
FROM thermoworks_credentials tc
JOIN users u ON tc.user_id = u.id;

COMMENT ON VIEW thermoworks_credentials_info IS 'Non-sensitive view of ThermoWorks credentials information';

-- Grant appropriate permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON thermoworks_credentials TO grill_stats_app;
GRANT SELECT ON thermoworks_credentials_info TO grill_stats_app;
GRANT USAGE ON SEQUENCE thermoworks_credentials_id_seq TO grill_stats_app;