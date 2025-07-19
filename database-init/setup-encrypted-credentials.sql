-- Complete setup script for encrypted credential storage
-- This script sets up all necessary tables and functions for secure credential storage

-- Begin transaction
BEGIN;

-- Create thermoworks_credentials table if it doesn't exist
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

-- Create credential access log table
CREATE TABLE IF NOT EXISTS credential_access_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL, -- 'encrypt', 'decrypt', 'rotate', 'validate', 'delete'
    success BOOLEAN NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,

    -- Constraint to ensure valid actions
    CONSTRAINT chk_action CHECK (action IN ('encrypt', 'decrypt', 'rotate', 'validate', 'delete', 'deactivate'))
);

-- Create indexes for the audit log
CREATE INDEX IF NOT EXISTS idx_credential_access_log_user_id ON credential_access_log(user_id);
CREATE INDEX IF NOT EXISTS idx_credential_access_log_timestamp ON credential_access_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_credential_access_log_action ON credential_access_log(action);

-- Create encryption key management table
CREATE TABLE IF NOT EXISTS encryption_key_management (
    id SERIAL PRIMARY KEY,
    key_name TEXT NOT NULL UNIQUE,
    key_version INTEGER NOT NULL,
    algorithm TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rotated_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    -- Metadata
    metadata JSONB
);

-- Insert initial key management record
INSERT INTO encryption_key_management (key_name, key_version, algorithm, metadata)
VALUES ('thermoworks-user-credentials', 1, 'aes256-gcm96', '{"auto_rotate": true, "rotation_interval": "720h"}')
ON CONFLICT (key_name) DO NOTHING;

-- Create trigger function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_thermoworks_credentials_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to update the updated_at timestamp
DROP TRIGGER IF EXISTS trigger_thermoworks_credentials_updated_at ON thermoworks_credentials;
CREATE TRIGGER trigger_thermoworks_credentials_updated_at
    BEFORE UPDATE ON thermoworks_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_thermoworks_credentials_updated_at();

-- Create function to validate encryption metadata
CREATE OR REPLACE FUNCTION validate_encryption_metadata(metadata_json JSONB)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if all required fields are present
    IF NOT (
        metadata_json ? 'key_version' AND
        metadata_json ? 'algorithm' AND
        metadata_json ? 'encrypted_at' AND
        metadata_json ? 'access_count'
    ) THEN
        RETURN FALSE;
    END IF;

    -- Check if algorithm is valid
    IF (metadata_json->>'algorithm') NOT IN ('aes256-gcm96') THEN
        RETURN FALSE;
    END IF;

    -- Check if key_version is a positive integer
    IF NOT (metadata_json->>'key_version')::INTEGER > 0 THEN
        RETURN FALSE;
    END IF;

    -- Check if access_count is a non-negative integer
    IF NOT (metadata_json->>'access_count')::INTEGER >= 0 THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Create function to check if a credential is properly encrypted
CREATE OR REPLACE FUNCTION is_credential_encrypted(encrypted_value TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if the value starts with Vault's ciphertext prefix
    RETURN encrypted_value LIKE 'vault:v%:%';
END;
$$ LANGUAGE plpgsql;

-- Create function to log credential access
CREATE OR REPLACE FUNCTION log_credential_access(
    p_user_id INTEGER,
    p_action TEXT,
    p_success BOOLEAN,
    p_details TEXT DEFAULT NULL,
    p_ip_address TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO credential_access_log (
        user_id,
        action,
        success,
        details,
        ip_address
    ) VALUES (
        p_user_id,
        p_action,
        p_success,
        p_details,
        p_ip_address
    );
END;
$$ LANGUAGE plpgsql;

-- Create function to clean up old audit logs
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM credential_access_log
    WHERE timestamp < NOW() - INTERVAL '1 day' * retention_days;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create function to generate security metrics
CREATE OR REPLACE FUNCTION get_credential_security_metrics()
RETURNS TABLE (
    metric_name TEXT,
    metric_value BIGINT,
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'total_encrypted_credentials'::TEXT,
        COUNT(*)::BIGINT,
        'Total encrypted credentials in system'::TEXT
    FROM thermoworks_credentials
    WHERE is_active = TRUE

    UNION ALL

    SELECT
        'credentials_accessed_today'::TEXT,
        COUNT(DISTINCT user_id)::BIGINT,
        'Unique users who accessed credentials today'::TEXT
    FROM credential_access_log
    WHERE action = 'decrypt'
    AND success = TRUE
    AND timestamp >= CURRENT_DATE

    UNION ALL

    SELECT
        'failed_decrypt_attempts_today'::TEXT,
        COUNT(*)::BIGINT,
        'Failed decryption attempts today'::TEXT
    FROM credential_access_log
    WHERE action = 'decrypt'
    AND success = FALSE
    AND timestamp >= CURRENT_DATE

    UNION ALL

    SELECT
        'inactive_credentials'::TEXT,
        COUNT(*)::BIGINT,
        'Inactive credentials (validation failed)'::TEXT
    FROM thermoworks_credentials
    WHERE is_active = FALSE

    UNION ALL

    SELECT
        'credentials_needing_validation'::TEXT,
        COUNT(*)::BIGINT,
        'Credentials that have never been validated'::TEXT
    FROM thermoworks_credentials
    WHERE last_validated IS NULL
    AND is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Create comprehensive validation function
CREATE OR REPLACE FUNCTION validate_thermoworks_credentials()
RETURNS TABLE (
    user_id INTEGER,
    validation_status TEXT,
    issue_description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tc.user_id,
        CASE
            WHEN NOT is_credential_encrypted(tc.encrypted_email) THEN 'INVALID_EMAIL_ENCRYPTION'
            WHEN NOT is_credential_encrypted(tc.encrypted_password) THEN 'INVALID_PASSWORD_ENCRYPTION'
            WHEN NOT validate_encryption_metadata(tc.encryption_metadata) THEN 'INVALID_METADATA'
            WHEN tc.encrypted_email IS NULL OR tc.encrypted_email = '' THEN 'MISSING_EMAIL'
            WHEN tc.encrypted_password IS NULL OR tc.encrypted_password = '' THEN 'MISSING_PASSWORD'
            ELSE 'VALID'
        END,
        CASE
            WHEN NOT is_credential_encrypted(tc.encrypted_email) THEN 'Email is not properly encrypted with Vault'
            WHEN NOT is_credential_encrypted(tc.encrypted_password) THEN 'Password is not properly encrypted with Vault'
            WHEN NOT validate_encryption_metadata(tc.encryption_metadata) THEN 'Encryption metadata is invalid or incomplete'
            WHEN tc.encrypted_email IS NULL OR tc.encrypted_email = '' THEN 'Encrypted email is missing'
            WHEN tc.encrypted_password IS NULL OR tc.encrypted_password = '' THEN 'Encrypted password is missing'
            ELSE 'Credential is properly encrypted and validated'
        END
    FROM thermoworks_credentials tc
    ORDER BY tc.user_id;
END;
$$ LANGUAGE plpgsql;

-- Create view for credential information without sensitive data
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

-- Create view for encrypted credential statistics
CREATE OR REPLACE VIEW encrypted_credential_stats AS
SELECT
    COUNT(*) as total_credentials,
    COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_credentials,
    COUNT(CASE WHEN is_active = FALSE THEN 1 END) as inactive_credentials,
    COUNT(CASE WHEN last_validated IS NOT NULL THEN 1 END) as validated_credentials,
    COUNT(CASE WHEN validation_attempts > 0 THEN 1 END) as credentials_with_failed_attempts,
    COALESCE(AVG(validation_attempts), 0) as avg_validation_attempts,
    MIN(created_at) as oldest_credential,
    MAX(created_at) as newest_credential,
    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as credentials_created_today
FROM thermoworks_credentials;

-- Create application user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_user WHERE usename = 'grill_stats_app') THEN
        CREATE USER grill_stats_app WITH ENCRYPTED PASSWORD 'secure_password_changeme';
    END IF;
END
$$;

-- Grant appropriate permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON thermoworks_credentials TO grill_stats_app;
GRANT SELECT, INSERT ON credential_access_log TO grill_stats_app;
GRANT SELECT ON thermoworks_credentials_info TO grill_stats_app;
GRANT SELECT ON encrypted_credential_stats TO grill_stats_app;
GRANT SELECT, UPDATE ON encryption_key_management TO grill_stats_app;
GRANT USAGE ON SEQUENCE thermoworks_credentials_id_seq TO grill_stats_app;
GRANT USAGE ON SEQUENCE credential_access_log_id_seq TO grill_stats_app;
GRANT USAGE ON SEQUENCE encryption_key_management_id_seq TO grill_stats_app;

-- Grant execute permissions on functions
GRANT EXECUTE ON FUNCTION validate_thermoworks_credentials() TO grill_stats_app;
GRANT EXECUTE ON FUNCTION validate_encryption_metadata(JSONB) TO grill_stats_app;
GRANT EXECUTE ON FUNCTION is_credential_encrypted(TEXT) TO grill_stats_app;
GRANT EXECUTE ON FUNCTION log_credential_access(INTEGER, TEXT, BOOLEAN, TEXT, TEXT) TO grill_stats_app;
GRANT EXECUTE ON FUNCTION cleanup_old_audit_logs(INTEGER) TO grill_stats_app;
GRANT EXECUTE ON FUNCTION get_credential_security_metrics() TO grill_stats_app;

-- Add comments for documentation
COMMENT ON TABLE thermoworks_credentials IS 'Encrypted ThermoWorks user credentials with metadata';
COMMENT ON COLUMN thermoworks_credentials.encrypted_email IS 'ThermoWorks email encrypted using Vault Transit engine';
COMMENT ON COLUMN thermoworks_credentials.encrypted_password IS 'ThermoWorks password encrypted using Vault Transit engine';
COMMENT ON COLUMN thermoworks_credentials.encryption_metadata IS 'Metadata about encryption (key version, algorithm, timestamps)';
COMMENT ON COLUMN thermoworks_credentials.is_active IS 'Whether the credentials are active and valid';
COMMENT ON COLUMN thermoworks_credentials.last_validated IS 'Last time credentials were successfully validated';
COMMENT ON COLUMN thermoworks_credentials.validation_attempts IS 'Number of failed validation attempts';

COMMENT ON TABLE credential_access_log IS 'Audit log for all credential access operations';
COMMENT ON TABLE encryption_key_management IS 'Management table for encryption key versions and rotation';
COMMENT ON VIEW thermoworks_credentials_info IS 'Non-sensitive view of ThermoWorks credentials information';
COMMENT ON VIEW encrypted_credential_stats IS 'Statistics view for encrypted credentials';

COMMENT ON FUNCTION validate_thermoworks_credentials() IS 'Validate all encrypted credentials';
COMMENT ON FUNCTION log_credential_access(INTEGER, TEXT, BOOLEAN, TEXT, TEXT) IS 'Log credential access operations';
COMMENT ON FUNCTION cleanup_old_audit_logs(INTEGER) IS 'Clean up old audit logs based on retention policy';
COMMENT ON FUNCTION get_credential_security_metrics() IS 'Get security metrics for encrypted credentials';

-- Commit the transaction
COMMIT;

-- Display setup results
SELECT 'Encrypted credential storage setup completed successfully!' as status;
SELECT * FROM get_credential_security_metrics();
