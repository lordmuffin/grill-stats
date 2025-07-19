# Grill Stats Deployment

This directory contains deployment scripts and templates for the Grill Stats application.

## Directory Structure

- **scripts/**: Contains deployment scripts for different environments
  - `deploy-dev.sh`: Development environment deployment using docker-compose
  - `deploy-staging.sh`: Staging environment deployment using docker-compose
  - `deploy-production.sh`: Production environment deployment using docker-compose
  - `deploy-kubernetes.sh`: Kubernetes deployment script for all environments

- **templates/**: Contains Kubernetes YAML templates
  - Application manifests (deployments, services, etc.)
  - Database manifests (PostgreSQL, InfluxDB, Redis)
  - Ingress and networking configuration
  - Secret management templates

## Deployment Environments

### Development Environment

The development environment is designed for local development and testing. It uses docker-compose to set up all required services locally.

```bash
# Deploy to development environment
./scripts/deploy-dev.sh

# Force rebuild of containers
./scripts/deploy-dev.sh --build

# Clean up existing containers and volumes
./scripts/deploy-dev.sh --clean
```

### Staging Environment

The staging environment mimics the production setup but with lower resource allocations and is used for testing before production deployment.

```bash
# Deploy to staging environment
./scripts/deploy-staging.sh

# Force rebuild of containers
./scripts/deploy-staging.sh --build

# Clean up existing containers and volumes
./scripts/deploy-staging.sh --clean

# Deploy specific image tag
./scripts/deploy-staging.sh --tag v1.2.3
```

### Production Environment

The production environment is designed for reliability and performance with proper resource allocation and redundancy.

```bash
# Deploy to production environment
./scripts/deploy-production.sh

# Clean up existing containers and volumes
./scripts/deploy-production.sh --clean

# Deploy specific image tag
./scripts/deploy-production.sh --tag v1.2.3

# Skip confirmation prompt
./scripts/deploy-production.sh --force
```

## Kubernetes Deployment

The Kubernetes deployment script supports deploying to different environments (dev, staging, production) with environment-specific configurations.

```bash
# Deploy to Kubernetes development environment
./scripts/deploy-kubernetes.sh --env=dev

# Deploy to Kubernetes staging environment
./scripts/deploy-kubernetes.sh --env=staging

# Deploy to Kubernetes production environment
./scripts/deploy-kubernetes.sh --env=prod

# Deploy specific image tag
./scripts/deploy-kubernetes.sh --env=prod --tag=v1.2.3

# Print the generated YAML without applying
./scripts/deploy-kubernetes.sh --env=prod --dry-run
```

## Environment Configuration

### Environment Variables

Each environment requires specific environment variables to be set. These can be defined in:

- `.env` file for local development
- `.env.staging.secrets` file for staging environment
- `.env.prod.secrets` file for production environment

The deployment scripts will check for the presence of these files and create templates if they don't exist.

### Secret Management

Secrets are managed differently depending on the deployment target:

- **Docker Compose**: Uses `.env` files
- **Kubernetes**: Uses Kubernetes Secrets resources with base64 encoding

The `deploy-kubernetes.sh` script automatically converts environment variables from the environment-specific secrets file into Kubernetes Secrets.

## Deployment Process

1. **Preparation**:
   - Ensure all required environment variables are set
   - Check that Docker or kubectl is installed (depending on deployment target)
   - Verify connectivity to deployment target

2. **Deployment**:
   - Run the appropriate deployment script for your target environment
   - The script will validate prerequisites and environment variables
   - For Kubernetes, templates are processed with environment-specific values
   - Resources are created in the correct order (namespace → secrets → storage → databases → application)

3. **Verification**:
   - The scripts perform basic health checks after deployment
   - For detailed verification, follow the instructions printed at the end of deployment

## Troubleshooting

Common issues and their solutions:

1. **Missing Environment Variables**:
   - Check that all required variables are set in the appropriate environment file
   - The scripts will create template files if they don't exist

2. **Docker Connectivity Issues**:
   - Ensure Docker daemon is running (`docker ps`)
   - Check for network connectivity issues

3. **Kubernetes Connectivity Issues**:
   - Verify kubectl is configured correctly (`kubectl config current-context`)
   - Ensure you have the necessary permissions to create resources

4. **Resource Constraints**:
   - If pods fail to start, check for resource constraints
   - Adjust resource limits in templates if necessary

## Additional Resources

- For more details on the application architecture, see the project's main README
- For information on CI/CD integration, see the .gitea/workflows directory
