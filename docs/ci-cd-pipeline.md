# CI/CD Pipeline Documentation

This document describes the Continuous Integration and Continuous Deployment pipeline implemented for the Grill Stats project using Gitea Actions.

## Overview

The pipeline consists of two main jobs:

1. **Test**: Handles code quality, testing, and validation
2. **Build**: Handles image building, scanning, and deployment

These jobs run in sequence - the build job only runs if the test job succeeds.

## Workflow Triggers

The pipeline is triggered on:
- Push to `main` branch
- Push to `develop` branch
- Pull requests to `main` branch

## Test Job

The test job performs comprehensive code quality and testing tasks:

### Environment Setup
- Uses Ubuntu latest runner
- Sets up Python 3.11
- Installs dependencies from:
  - requirements.txt
  - requirements-test.txt
  - Dev dependencies (flake8, black, isort, mypy)

### Testing Steps

1. **Syntax Checks**
   - Uses flake8 to check for critical errors
   - Fails the build if critical syntax errors are found

2. **Code Style Checks**
   - flake8 with complexity and line length checks
   - black formatting validation
   - isort import ordering validation
   - Reports style issues but doesn't fail the build

3. **Type Checking**
   - mypy static type checking on core files
   - Reports type issues but doesn't fail the build (gradual adoption)

4. **Unit Tests**
   - Runs pytest on unit test directory
   - Tests are required to pass

5. **Alert System Tests**
   - Runs specialized alert system tests
   - Tests are required to pass

## Build Job

The build job handles container image building, scanning, and deployment:

### Environment Setup
- Uses Ubuntu latest runner
- Sets up Python 3.11
- Sets Docker registry and image name environment variables

### Build Steps

1. **Security Scanning**
   - Scans Python dependencies for vulnerabilities using safety
   - Reports issues but doesn't fail the build

2. **Kaniko Setup**
   - Sets up Kaniko executor for containerized builds
   - Configures for Docker Hub connectivity

3. **Image Building**
   - Determines version tags based on branch
   - Creates Docker image with semantic versioning
   - Builds image using Kaniko
   - Supports different tag formats for main/develop/feature branches

4. **Image Pushing**
   - Pushes built image to Docker Hub
   - Uses crane for efficient image uploads
   - Adds appropriate tags based on branch and version

5. **Vulnerability Scanning**
   - Scans built Docker image for vulnerabilities using Trivy
   - Reports issues but doesn't fail the build

6. **Container Verification**
   - Loads the image locally
   - Runs a test container to verify startup
   - Validates container health
   - Fails if container doesn't start successfully

## Tag Strategy

The pipeline uses a semantic versioning strategy for image tags:

- **Main Branch**
  - `<version>` (e.g., 1.0.4)
  - `latest`
  - `v<version>` (e.g., v1.0.4)

- **Develop Branch**
  - `<version>-dev` (e.g., 1.0.4-dev)
  - `dev`

- **Feature Branches**
  - `<version>-<branch>-<sha>` (e.g., 1.0.4-feature-login-a1b2c3d)
  - `<branch>` (e.g., feature-login)

## Security Considerations

The pipeline implements several security best practices:

1. **Dependency Scanning**: Uses safety to scan Python dependencies
2. **Image Scanning**: Uses Trivy to scan container images
3. **Testing First**: Prevents pushing vulnerable code by testing before building
4. **Verification**: Ensures container starts correctly before finishing

## Adding Tests

To add new tests to the pipeline:

1. Add test files to the appropriate directory:
   - Unit tests: `tests/unit/`
   - Integration tests: `tests/integration/`
   - E2E tests: `tests/e2e/`

2. Update the pipeline if needed by modifying `.gitea/workflows/build.yaml`

## Troubleshooting

Common issues and solutions:

1. **Failed Syntax Check**: Run `flake8 . --count --select=E9,F63,F7,F82` locally to identify issues
2. **Failed Unit Tests**: Run `python -m pytest tests/unit -v` locally to debug
3. **Container Build Failures**: Check Dockerfile for errors or incompatible dependencies
4. **Push Failures**: Verify Docker Hub credentials and connectivity
