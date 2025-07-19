# Grill Stats CI/CD Pipeline Documentation

This document explains how the CI/CD pipelines are set up for the Grill Stats project, using Gitea Actions for continuous integration and container image building on Kubernetes.

## Recent Updates - 2025-07-19

The CI/CD pipeline has been recently enhanced with the following improvements:

1. **Separated Test and Build Jobs**
   - Test job now runs all tests and code quality checks
   - Build job runs only if tests pass successfully

2. **Enhanced Code Quality Checks**
   - Syntax checking with flake8
   - Code style verification with black and isort
   - Type checking with mypy
   - Vulnerability scanning with safety

3. **Comprehensive Testing**
   - Unit tests with pytest
   - Alert system testing
   - Container startup verification

4. **Docker Image Security**
   - Image vulnerability scanning with Trivy
   - Container verification testing

## Overview

The Grill Stats project consists of a main application and several microservices. Each component has its own dedicated build pipeline that is triggered when changes are made to the relevant files. We also have separate pipelines for testing and end-to-end testing.

## Pipeline Structure

### Build Pipelines

Each microservice has its own dedicated build pipeline that:
1. Builds a Docker image using Kaniko
2. Tags it appropriately based on git branch, tag, or commit hash
3. Pushes it to the Gitea container registry

The following build pipelines are available:

| Pipeline File | Service | Trigger Paths |
|---------------|---------|---------------|
| `main-app-build.yml` | Main Grill Stats app | Root app files, templates, models, auth, forms |
| `device-service-build.yml` | Device Service | `services/device-service/**` |
| `temperature-service-build.yml` | Temperature Service | `services/temperature-service/**` |
| `historical-data-service-build.yml` | Historical Data Service | `services/historical-data-service/**` |
| `data-pipeline-build.yml` | Data Pipeline | `services/data-pipeline/**` |
| `alert-service-build.yml` | Alert Service | `services/alert-service/**` |
| `web-ui-build.yml` | Web UI | `services/web-ui/**` |

### Test Pipelines

We have two types of test pipelines:

1. `test-workflow.yml`: Runs linting and unit tests for the main app and all microservices
2. `e2e-test-workflow.yml`: Runs end-to-end tests with supporting services (PostgreSQL, Redis)

## How It Works

### Kubernetes-Based Workflows

All workflows are configured to run on Kubernetes-based Gitea runners:

- Build pipelines use a Kaniko container to build and push images without requiring Docker-in-Docker
- Test pipelines run in dedicated Python containers
- E2E tests utilize Kubernetes service containers for dependencies

### Build Process

Each build pipeline follows these steps:

1. **Checkout**: Retrieves the latest code from the repository
2. **Kaniko Setup**: Sets up Docker credentials for the Gitea registry
3. **Tag Calculation**: Generates appropriate tags based on git context
4. **Build and Push**: Uses Kaniko to build the Docker image and push it to the registry

### Image Tagging Strategy

Images are tagged using the following scheme:

- For git tags (e.g., v1.0.0): Tagged with the version number and latest
- For main branch: Tagged with 'main' and a short git SHA (e.g., sha-abc123)
- For other branches: Tagged with the branch name and a short git SHA

### Caching Strategy

To speed up builds, we implement a caching strategy using Kaniko's caching features:

- Each build uses the `--cache=true` flag
- Cache TTL is set to 168 hours (7 days)
- This significantly speeds up subsequent builds

## Configuration

### Registry Configuration

The pipelines are configured to use the Gitea registry at `gitea-internal`. Images are pushed to repositories named:

- `gitea-internal/lordmuffin/grill-stats` (main app)
- `gitea-internal/lordmuffin/grill-stats-{service-name}` (microservices)

### Required Secrets

The following secrets must be configured in your Gitea repository:

- `DOCKER_AUTH`: Base64-encoded string containing your Docker Hub credentials in format `username:password` or `username:token`

Creating the DOCKER_AUTH secret:

```bash
# Generate the base64-encoded auth string
echo -n "yourusername:yourtoken" | base64
# Example output: eW91cnVzZXJuYW1lOnlvdXJ0b2tlbg==
```

To add the secret:
1. Go to your repository settings in Gitea
2. Navigate to "Secrets"
3. Add a new secret named `DOCKER_AUTH` with the base64-encoded value
4. Make sure the secret is available to the workflows

#### Security Best Practices

- **Use tokens instead of passwords**: Create a Docker Hub Personal Access Token with minimal permissions rather than using your account password
- **Limit token scope**: Restrict the token to only what's needed (usually just `read:packages`, `write:packages`)
- **Set token expiration**: Use tokens with expirations and rotate them regularly
- **Monitor usage**: Regularly review access logs for unusual activity

## Pipeline Triggers

### Automatic Triggers

Pipelines are automatically triggered on:

- Pushes to the `main` branch
- Creating git tags starting with `v` (e.g., v1.0.0)
- Pull requests to `main` (for test pipelines only)

Each build pipeline has path filters to only trigger when relevant files are changed.

### Manual Triggers

The E2E test pipeline can also be triggered manually through the Gitea Actions interface.

## Deployment Process

After the images are built and pushed to the registry, deployment is handled separately through Kubernetes and ArgoCD:

1. The Kustomize configuration in your homelab repository references these container images
2. ArgoCD monitors the homelab repository for changes
3. When changes are detected, ArgoCD applies them to your Kubernetes cluster

## Kubernetes Compatibility

These workflows are specifically designed to work in a Kubernetes environment:

1. **Kaniko for Container Building**: No need for Docker-in-Docker or privileged containers
2. **Container-Based Execution**: All jobs run in specific containers
3. **Service Containers**: Test jobs utilize Kubernetes service containers for dependencies
4. **Resource Efficiency**: Jobs are designed to minimize resource usage

## Troubleshooting

If a pipeline fails, you can:

1. Check the build logs in Gitea Actions for error messages
2. Verify that the required secrets are properly configured
3. Ensure the Gitea registry is accessible from your Kubernetes runners
4. Check that the Kaniko executor can access the internet to pull base images

Common issues and solutions:

- **Authentication Failures**: Check your registry credentials
- **Missing Runners**: Ensure you have Kubernetes runners registered for the `kubernetes` label
- **Network Issues**: Check that pods can communicate with each other and the Gitea instance
- **Storage Issues**: Ensure there's enough ephemeral storage for build operations

## Extending the Pipelines

To add a new microservice to the CI/CD system:

1. Create a new workflow file in `.gitea/workflows/` following the existing patterns
2. Update the path triggers to match your new service's directory
3. Adjust the image name and context path
4. Add the service to the microservice test matrix if it includes tests

## Monitoring and Maintenance

Regularly check:

1. Build times - If they're increasing, consider adjusting cache settings
2. Image sizes - Look for unexpected increases that might indicate issues
3. Test coverage - Ensure new code is adequately tested
4. Pipeline success rates - Address recurring failures promptly
