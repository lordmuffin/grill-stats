-- Migration script to migrate existing ThermoWorks credentials to encrypted storage
-- This script should be run after the encryption service is deployed and configured

-- First, let's ensure the thermoworks_credentials table exists with proper structure
-- (The add_thermoworks_credentials_table.sql should have been run first)

-- Create a backup of existing credentials if they exist in the users table
CREATE TABLE IF NOT EXISTS thermoworks_credentials_backup AS
SELECT
    id as user_id,
    email,
    thermoworks_access_token,
    thermoworks_refresh_token,
    thermoworks_token_expires,
    created_at,
    updated_at
FROM users
WHERE thermoworks_access_token IS NOT NULL
   OR thermoworks_refresh_token IS NOT NULL;

-- Add a comment to the backup table
COMMENT ON TABLE thermoworks_credentials_backup IS 'Backup of ThermoWorks credentials before migration to encrypted storage';

-- Create a function to generate migration status report
CREATE OR REPLACE FUNCTION generate_migration_report()
RETURNS TABLE (
    metric_name TEXT,
    count_value BIGINT,
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'users_with_thermoworks_tokens'::TEXT,
        COUNT(*)::BIGINT,
        'Users with ThermoWorks tokens in users table'::TEXT
    FROM users
    WHERE thermoworks_access_token IS NOT NULL
       OR thermoworks_refresh_token IS NOT NULL

    UNION ALL

    SELECT
        'encrypted_credentials_count'::TEXT,
        COUNT(*)::BIGINT,
        'Encrypted credentials in thermoworks_credentials table'::TEXT
    FROM thermoworks_credentials
    WHERE is_active = TRUE

    UNION ALL

    SELECT
        'backup_records_count'::TEXT,
        COUNT(*)::BIGINT,
        'Records in backup table'::TEXT
    FROM thermoworks_credentials_backup

    UNION ALL

    SELECT
        'total_users_count'::TEXT,
        COUNT(*)::BIGINT,
        'Total users in system'::TEXT
    FROM users;
END;
$$ LANGUAGE plpgsql;

-- Create a function to validate encryption metadata
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

-- Create a function to check if a credential is properly encrypted
CREATE OR REPLACE FUNCTION is_credential_encrypted(encrypted_value TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if the value starts with Vault's ciphertext prefix
    RETURN encrypted_value LIKE 'vault:v%:%';
END;
$$ LANGUAGE plpgsql;

-- Create a comprehensive validation function
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

-- Create audit logging function
CREATE OR REPLACE FUNCTION log_credential_access(
    p_user_id INTEGER,
    p_action TEXT,
    p_success BOOLEAN,
    p_details TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO credential_access_log (
        user_id,
        action,
        success,
        details,
        timestamp,
        ip_address
    ) VALUES (
        p_user_id,
        p_action,
        p_success,
        p_details,
        CURRENT_TIMESTAMP,
        current_setting('application_name', true) -- This would be set by the application
    );
END;
$$ LANGUAGE plpgsql;

-- Create credential access log table
CREATE TABLE IF NOT EXISTS credential_access_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL, -- 'encrypt', 'decrypt', 'rotate', 'validate'
    success BOOLEAN NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,

    -- Index for querying
    CONSTRAINT chk_action CHECK (action IN ('encrypt', 'decrypt', 'rotate', 'validate', 'delete'))
);

-- Create indexes for the audit log
CREATE INDEX IF NOT EXISTS idx_credential_access_log_user_id ON credential_access_log(user_id);
CREATE INDEX IF NOT EXISTS idx_credential_access_log_timestamp ON credential_access_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_credential_access_log_action ON credential_access_log(action);

-- Create a function to clean up old audit logs (retention policy)
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

-- Create a trigger to update the updated_at timestamp for thermoworks_credentials
CREATE OR REPLACE FUNCTION update_thermoworks_credentials_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop the trigger if it exists and recreate it
DROP TRIGGER IF EXISTS trigger_thermoworks_credentials_updated_at ON thermoworks_credentials;
CREATE TRIGGER trigger_thermoworks_credentials_updated_at
    BEFORE UPDATE ON thermoworks_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_thermoworks_credentials_updated_at();

-- Create a view for encrypted credential statistics
CREATE OR REPLACE VIEW encrypted_credential_stats AS
SELECT
    COUNT(*) as total_credentials,
    COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_credentials,
    COUNT(CASE WHEN is_active = FALSE THEN 1 END) as inactive_credentials,
    COUNT(CASE WHEN last_validated IS NOT NULL THEN 1 END) as validated_credentials,
    COUNT(CASE WHEN validation_attempts > 0 THEN 1 END) as credentials_with_failed_attempts,
    AVG(validation_attempts) as avg_validation_attempts,
    MIN(created_at) as oldest_credential,
    MAX(created_at) as newest_credential,
    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as credentials_created_today
FROM thermoworks_credentials;

-- Grant appropriate permissions
GRANT SELECT ON encrypted_credential_stats TO grill_stats_app;
GRANT SELECT, INSERT ON credential_access_log TO grill_stats_app;
GRANT USAGE ON SEQUENCE credential_access_log_id_seq TO grill_stats_app;

-- Grant execute permissions on functions
GRANT EXECUTE ON FUNCTION generate_migration_report() TO grill_stats_app;
GRANT EXECUTE ON FUNCTION validate_thermoworks_credentials() TO grill_stats_app;
GRANT EXECUTE ON FUNCTION validate_encryption_metadata(JSONB) TO grill_stats_app;
GRANT EXECUTE ON FUNCTION is_credential_encrypted(TEXT) TO grill_stats_app;
GRANT EXECUTE ON FUNCTION log_credential_access(INTEGER, TEXT, BOOLEAN, TEXT) TO grill_stats_app;
GRANT EXECUTE ON FUNCTION cleanup_old_audit_logs(INTEGER) TO grill_stats_app;

-- Add comments for documentation
COMMENT ON TABLE credential_access_log IS 'Audit log for all credential access operations';
COMMENT ON VIEW encrypted_credential_stats IS 'Statistics view for encrypted credentials';
COMMENT ON FUNCTION generate_migration_report() IS 'Generate migration status report';
COMMENT ON FUNCTION validate_thermoworks_credentials() IS 'Validate all encrypted credentials';
COMMENT ON FUNCTION log_credential_access(INTEGER, TEXT, BOOLEAN, TEXT) IS 'Log credential access operations';
COMMENT ON FUNCTION cleanup_old_audit_logs(INTEGER) IS 'Clean up old audit logs based on retention policy';

-- Generate initial migration report
SELECT 'Migration script executed successfully' as status;
SELECT * FROM generate_migration_report();

-- Show validation results for existing credentials
SELECT 'Credential validation results:' as status;
SELECT * FROM validate_thermoworks_credentials();

-- Show encrypted credential statistics
SELECT 'Encrypted credential statistics:' as status;
SELECT * FROM encrypted_credential_stats;
