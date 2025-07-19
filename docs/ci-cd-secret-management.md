# CI/CD Secret Management Guide

This document provides comprehensive guidance on managing secrets for the Grill Stats CI/CD pipeline, focusing on secure practices and integration with Gitea Actions.

## Table of Contents

- [Overview](#overview)
- [Secret Types](#secret-types)
- [Secret Management Tools](#secret-management-tools)
- [Setting Up Secrets](#setting-up-secrets)
- [Using Secrets in Workflows](#using-secrets-in-workflows)
- [Secret Rotation](#secret-rotation)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The Grill Stats CI/CD pipeline requires various secrets for authentication, database access, and external API integration. These secrets must be managed securely to prevent unauthorized access while ensuring they're available for legitimate CI/CD operations.

The project uses two complementary approaches for secret management:

1. **Gitea Repository Secrets**: For CI/CD pipeline authentication and testing
2. **1Password Connect**: For Kubernetes deployment and runtime secrets

## Secret Types

### CI/CD Pipeline Secrets

These secrets are stored as Gitea repository secrets and used during build, test, and deployment:

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `DOCKER_AUTH` | Base64-encoded Docker Hub credentials | Yes |
| `SECRET_KEY` | Application secret key for testing | Yes |
| `THERMOWORKS_API_KEY` | ThermoWorks API key for testing | Yes |
| `HOMEASSISTANT_URL` | Home Assistant URL for testing | Yes |
| `HOMEASSISTANT_TOKEN` | Home Assistant token for testing | Yes |
| `DB_HOST` | PostgreSQL host | Yes |
| `DB_PORT` | PostgreSQL port | Yes |
| `DB_NAME` | PostgreSQL database name | Yes |
| `DB_USERNAME` | PostgreSQL username | Yes |
| `DB_PASSWORD` | PostgreSQL password | Yes |
| `DATABASE_URL` | Full PostgreSQL connection URL | Yes |
| `INFLUXDB_HOST` | InfluxDB host | No |
| `INFLUXDB_PORT` | InfluxDB port | No |
| `INFLUXDB_DATABASE` | InfluxDB database name | No |
| `INFLUXDB_USERNAME` | InfluxDB username | No |
| `INFLUXDB_PASSWORD` | InfluxDB password | No |
| `INFLUXDB_TOKEN` | InfluxDB authentication token | No |
| `REDIS_HOST` | Redis host | No |
| `REDIS_PORT` | Redis port | No |
| `REDIS_PASSWORD` | Redis password | No |

### Runtime Secrets

These secrets are managed through 1Password Connect and deployed to Kubernetes:

- See [Grill Stats 1Password Connect Secrets](/apps/secrets/grill-stats/README.md) for details on runtime secrets

## Secret Management Tools

The project provides the following tools for secret management:

1. **scripts/setup-ci-cd-secrets.sh**: Script for setting up Gitea repository secrets
2. **apps/secrets/grill-stats/setup-1password-vaults.sh**: Script for setting up 1Password vaults
3. **apps/secrets/grill-stats/deploy-secrets.sh**: Script for deploying 1Password secrets to Kubernetes

## Setting Up Secrets

### CI/CD Pipeline Secrets

To set up the CI/CD pipeline secrets:

1. Generate an API token in Gitea:
   - Go to your Gitea user settings
   - Navigate to "Applications"
   - Create a new token with appropriate permissions

2. Run the setup script:
   ```bash
   ./scripts/setup-ci-cd-secrets.sh --gitea-url https://your-gitea-instance.com --gitea-token YOUR_TOKEN --repository owner/repo
   ```

3. The script will prompt for the necessary credentials and set up all required secrets.

4. You can verify the secrets are properly set by checking the repository settings in Gitea:
   - Go to your repository settings
   - Navigate to "Secrets"
   - You should see all the secrets listed

### Manual Secret Setup

If you prefer to set up secrets manually:

1. Go to your repository settings in Gitea
2. Navigate to "Secrets"
3. Click "New Secret"
4. Enter the secret name (from the table above)
5. Enter the secret value
6. Click "Add Secret"

## Using Secrets in Workflows

Secrets can be accessed in workflow files using the `secrets` context:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    env:
      # Use repository secrets
      SECRET_KEY: ${{ secrets.SECRET_KEY }}
      THERMOWORKS_API_KEY: ${{ secrets.THERMOWORKS_API_KEY }}
    steps:
      - name: Use the secrets
        run: |
          # Use the secrets in commands
          echo "Using secret: $SECRET_KEY" # The actual value will be masked in logs
```

Important notes:
- Secret values are automatically masked in logs
- Secrets are available as environment variables within jobs
- Environment variables containing secrets should not be echoed or printed
- Store only the minimum set of secrets required for each workflow

## Secret Rotation

Regular rotation of secrets is essential for maintaining security:

### Docker Hub Authentication

1. Create a new Docker Hub Personal Access Token:
   - Go to Docker Hub → Account Settings → Security
   - Generate a new access token with an expiration date
   - Copy the token value

2. Update the `DOCKER_AUTH` secret:
   - Generate the base64-encoded value:
     ```bash
     echo -n "yourusername:yourtoken" | base64
     ```
   - Update the secret in Gitea repository settings

3. Test the workflow to verify the new token works

4. Revoke the old token in Docker Hub

### API Keys and Credentials

Follow a similar process for other credentials:

1. Generate new credentials in the respective service
2. Update the corresponding secret in Gitea
3. Test the workflow with the new credentials
4. Revoke the old credentials if possible

### Recommended Rotation Schedule

- **High-Value Secrets** (Docker Hub, API keys): Every 30-90 days
- **Service Accounts**: Every 180 days
- **Project-Specific Tokens**: At least annually

## Security Best Practices

### 1. Principle of Least Privilege

- Create tokens with only the permissions needed
- Use read-only tokens where possible
- Limit scope and expiration for all tokens

### 2. Secret Isolation

- Use different tokens for different environments
- Isolate production credentials from development
- Never use production credentials in CI/CD testing

### 3. Audit and Monitoring

- Regularly review access logs
- Monitor for unexpected credential usage
- Set up alerts for suspicious activity

### 4. No Hardcoded Secrets

- Never commit secrets to code
- Use environment variables or secret management
- Scan repositories for leaked secrets

### 5. Secure Transmission

- Only access secrets over HTTPS
- Ensure proper TLS configuration
- Disable verbose logging of credentials

## Troubleshooting

### Common Issues

#### 1. Missing Secret Error

If you see an error like:

```
ERROR: DOCKER_AUTH secret is not set
```

Check that:
- The secret is properly defined in Gitea
- The workflow has access to the secret
- The secret name matches exactly (case-sensitive)

#### 2. Authentication Failure

If you see authentication errors:

```
unauthorized: authentication required
```

Check that:
- The token is still valid and not expired
- The token has the necessary permissions
- The base64 encoding is correct (no newlines, whitespace)

#### 3. Debug Secret Existence

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

#### 4. Secret Format Issues

If you encounter format-related issues:

- For Docker Hub auth: verify base64 encoding is correct
- For database URLs: check for special characters that might need escaping
- For JSON values: ensure proper quoting and escaping

## Additional Resources

- [Gitea Secrets Documentation](https://docs.gitea.io/en-us/actions/secrets/)
- [Docker Hub Access Tokens](https://docs.docker.com/docker-hub/access-tokens/)
- [1Password Connect Documentation](https://developer.1password.com/docs/connect)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

Last updated: 2025-07-19

