# Secret Management in CI/CD Pipeline

This document provides comprehensive guidance on managing secrets securely in the Grill Stats CI/CD pipeline.

## Table of Contents

- [Overview](#overview)
- [Secret Types](#secret-types)
- [Secret Storage](#secret-storage)
- [Secret Usage](#secret-usage)
- [Secret Rotation](#secret-rotation)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Proper secret management is critical for maintaining the security of your CI/CD pipeline and deployed applications. The Grill Stats project uses Gitea repository secrets to securely store and use sensitive information like authentication tokens and credentials.

## Secret Types

The following types of secrets are used in the Grill Stats CI/CD pipeline:

1. **Docker Registry Authentication**
   - `DOCKER_AUTH`: Base64-encoded string for Docker Hub authentication

2. **Environment-Specific Configuration**
   - Development, staging, and production environment variables

3. **Database Credentials**
   - PostgreSQL connection information
   - InfluxDB credentials
   - Redis authentication

4. **API Keys and Tokens**
   - ThermoWorks API keys
   - Home Assistant tokens

## Secret Storage

### Gitea Repository Secrets

Gitea Secrets are the primary method for storing sensitive information used by workflows. These secrets are:
- Encrypted at rest
- Masked in logs
- Only accessible to authorized users and workflows

### Creating Secrets

To add a new secret:

1. Navigate to your repository on Gitea
2. Go to "Settings" > "Secrets"
3. Click "New Secret"
4. Enter the secret name (uppercase, with underscores)
5. Enter the secret value
6. Click "Add Secret"

### Docker Authentication Secret

The `DOCKER_AUTH` secret is a base64-encoded string containing your Docker Hub credentials:

```bash
# Generate the auth string
echo -n "yourusername:yourtoken" | base64
# Example output: eW91cnVzZXJuYW1lOnlvdXJ0b2tlbg==
```

## Secret Usage

### In Workflow Files

Secrets are accessed in workflow files using the `secrets` context:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    env:
      DOCKER_AUTH: ${{ secrets.DOCKER_AUTH }}
    steps:
      - name: Use secret
        run: |
          # Use the secret in your commands
          echo "Using secret: $DOCKER_AUTH" # The actual value will be masked in logs
```

### Environment Variables vs Secrets

- **Environment Variables**: For non-sensitive data that can be visible in logs
- **Secrets**: For sensitive data that should never be exposed in logs

## Secret Rotation

Regular rotation of secrets is essential for maintaining security:

### Docker Authentication

1. Create a new Docker Hub Personal Access Token with an expiration date
2. Update the `DOCKER_AUTH` secret with the new token
3. Verify the build pipeline works with the new token
4. Revoke the old token

### API Keys and Service Credentials

1. Generate new credentials in the respective service
2. Update the corresponding secret in Gitea
3. Test the workflow with the new credentials
4. Revoke the old credentials

### Recommended Rotation Schedule

- **High-Value Secrets** (Docker Hub, API keys): Every 30-90 days
- **Service Accounts**: Every 180 days
- **Project-Specific Tokens**: At least annually

## Security Best Practices

1. **Principle of Least Privilege**
   - Create tokens with only the permissions needed
   - Use read-only tokens where possible

2. **Secret Isolation**
   - Use different tokens for different environments
   - Isolate production credentials from development

3. **Audit and Monitoring**
   - Regularly review access logs
   - Monitor for unexpected credential usage

4. **No Hardcoded Secrets**
   - Never commit secrets to code
   - Use secrets management for all sensitive data

5. **Secure Transmission**
   - Only access secrets over HTTPS
   - Ensure proper TLS configuration

## Troubleshooting

### Common Issues

1. **Missing Secret Error**

   If you see an error like:

   ```
   ERROR: DOCKER_AUTH secret is not set
   ```

   Check that:
   - The secret is properly defined in Gitea
   - The workflow has access to the secret
   - The secret name matches exactly (case-sensitive)

2. **Authentication Failure**

   If you see authentication errors:

   ```
   unauthorized: authentication required
   ```

   Check that:
   - The token is still valid and not expired
   - The token has the necessary permissions
   - The base64 encoding is correct (no newlines, whitespace)

3. **Debugging Secret Usage**

   To debug secret usage without exposing values:

   ```yaml
   - name: Debug secret existence
     run: |
       # Check if secret exists (don't print the value)
       if [ -n "$DOCKER_AUTH" ]; then
         echo "Secret exists and is not empty"
       else
         echo "Secret is missing or empty"
       fi
   ```

## Conclusion

Proper secret management is a critical aspect of CI/CD security. By following the practices outlined in this document, you can maintain a secure pipeline while ensuring your workflows have access to the necessary credentials.

---

Last updated: 2025-07-19
