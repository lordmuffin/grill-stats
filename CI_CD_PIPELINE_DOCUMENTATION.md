# Grill Stats CI/CD Pipeline Documentation

This document explains how the CI/CD pipelines are set up for the Grill Stats project, using Gitea Actions for continuous integration and container image building.

## Overview

The Grill Stats project consists of a main application and several microservices. Each component has its own dedicated build pipeline that is triggered when changes are made to the relevant files. We also have separate pipelines for testing and end-to-end testing.

## Pipeline Structure

### Build Pipelines

Each microservice has its own dedicated build pipeline that:
1. Builds a Docker image
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

### Build Process

Each build pipeline follows these steps:

1. **Checkout**: Retrieves the latest code from the repository
2. **Setup Docker Buildx**: Prepares the Docker build environment
3. **Login to Registry**: Authenticates with the Gitea container registry
4. **Extract Metadata**: Generates appropriate tags based on git context
5. **Build and Push**: Builds the Docker image and pushes it to the registry

### Image Tagging Strategy

Images are tagged using the following scheme:

- For git tags (e.g., v1.0.0): Tagged with the version number
- For branches: Tagged with the branch name (e.g., main, develop)
- For all builds: Tagged with a short git SHA (e.g., abc123)

### Caching Strategy

To speed up builds, we implement a caching strategy:

- Each service has a dedicated `:cache` tag in the registry
- The build process uses this cache for subsequent builds
- This significantly speeds up the build process

## Configuration

### Registry Configuration

The pipelines are configured to use the Gitea registry at `gitea.lab.apj.dev`. Images are pushed to repositories named:

- `gitea.lab.apj.dev/lordmuffin/grill-stats` (main app)
- `gitea.lab.apj.dev/lordmuffin/grill-stats-{service-name}` (microservices)

### Required Secrets

The following secrets must be configured in your Gitea repository:

- `REGISTRY_USERNAME`: Your Gitea username with access to the container registry
- `REGISTRY_PASSWORD`: Your Gitea password or token with registry write permissions

To add these secrets:
1. Go to your repository settings in Gitea
2. Navigate to "Secrets"
3. Add the secrets with the appropriate values

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

## Troubleshooting

If a pipeline fails, you can:

1. Check the build logs in Gitea Actions for error messages
2. Verify that the required secrets are properly configured
3. Ensure the Gitea registry is accessible and properly configured
4. Check that your Gitea Actions runners are correctly set up and have internet access

## Extending the Pipelines

To add a new microservice to the CI/CD system:

1. Create a new workflow file in `.gitea/workflows/` following the existing patterns
2. Update the path triggers to match your new service's directory
3. Adjust the image name and context as needed
4. Add the service to the microservice test matrix if it includes tests

## Monitoring and Maintenance

Regularly check:

1. Build times - If they're increasing, your caches might not be working effectively
2. Image sizes - Look for unexpected increases that might indicate issues
3. Test coverage - Ensure new code is adequately tested
4. Pipeline success rates - Address recurring failures promptly