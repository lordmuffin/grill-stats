#!/bin/bash
# Script to assist with rotating exposed credentials
# This script helps identify and rotate any exposed credentials in the codebase

set -e

echo "========================================================"
echo "  Credential Rotation Assistant"
echo "========================================================"
echo "This script will help you rotate exposed credentials in the CI/CD pipeline"
echo

# Step 1: Identify the exposed credential
echo -e "\033[1;36m[STEP 1] Identifying exposed credentials\033[0m"
echo "The following credential has been identified as exposed:"
echo -e "  - \033[1;31mDOCKER_AUTH\033[0m (Docker Hub authentication)"
echo "  - Location: .gitea/workflows/build.yaml"
echo "  - Type: Base64-encoded Docker Hub credential"
echo

# Step 2: Check if credential is still in codebase
echo -e "\033[1;36m[STEP 2] Checking if credential is still in codebase\033[0m"
CREDENTIAL_STILL_PRESENT=$(grep -r "bG9yZG11ZmZpbjpkY2tyX3BhdF9nSWJScjBsRnZ6LTlxMFFZVDVKc01FQ0p5VDQ=" --include="*.yaml" --include="*.yml" . | wc -l)

if [ "$CREDENTIAL_STILL_PRESENT" -gt 0 ]; then
  echo -e "\033[1;31m❌ WARNING: The exposed credential is still present in the codebase!\033[0m"
  echo "Please update the following files to use proper secret management:"
  grep -r "bG9yZG11ZmZpbjpkY2tyX3BhdF9nSWJScjBsRnZ6LTlxMFFZVDVKc01FQ0p5VDQ=" --include="*.yaml" --include="*.yml" .
  echo
  echo "Recommended action: Replace hardcoded credentials with \${{ secrets.DOCKER_AUTH }}"
else
  echo -e "\033[1;32m✅ Credential has been removed from the codebase\033[0m"
fi

# Step 3: Generate new credential
echo -e "\033[1;36m[STEP 3] Generating new Docker Hub credentials\033[0m"
echo "Please follow these steps to create a new Docker Hub Personal Access Token:"
echo "1. Log in to Docker Hub (https://hub.docker.com)"
echo "2. Go to Account Settings > Security > Access Tokens"
echo "3. Click 'New Access Token'"
echo "4. Name: grill-stats-ci-token-$(date +%Y%m)"
echo "5. Access permissions: Read & Write"
echo "6. Set an expiration date (recommended: 180 days)"
echo

# Step 4: Create encoded credential
echo -e "\033[1;36m[STEP 4] Creating encoded credential\033[0m"
echo "After creating your new token, encode it using the following command:"
echo "  echo -n \"yourusername:yourtoken\" | base64"
echo
echo "This will output a string like:"
echo "  eW91cnVzZXJuYW1lOnlvdXJ0b2tlbg=="
echo

# Step 5: Add to repository secrets
echo -e "\033[1;36m[STEP 5] Adding to repository secrets\033[0m"
echo "Add the new credential to your repository secrets:"
echo "1. Go to your repository on Gitea"
echo "2. Navigate to Settings > Secrets"
echo "3. Add a new secret named 'DOCKER_AUTH'"
echo "4. Paste the base64-encoded string as the value"
echo "5. Click 'Add Secret'"
echo

# Step 6: Revoke old credential
echo -e "\033[1;36m[STEP 6] Revoking old credential\033[0m"
echo "IMPORTANT: After confirming the new credential works, revoke the old token:"
echo "1. Go to Docker Hub > Account Settings > Security > Access Tokens"
echo "2. Find the old token"
echo "3. Click 'Delete' to revoke it"
echo

# Step 7: Update git history (optional but recommended)
echo -e "\033[1;36m[STEP 7] Updating git history (optional)\033[0m"
echo "Consider using git filter-repo to remove the credential from git history:"
echo "  pip install git-filter-repo"
echo "  git filter-repo --replace-text credential-replacements.txt"
echo
echo "Where credential-replacements.txt contains:"
echo "  bG9yZG11ZmZpbjpkY2tyX3BhdF9nSWJScjBsRnZ6LTlxMFFZVDVKc01FQ0p5VDQ==>REDACTED_CREDENTIAL"
echo
echo "WARNING: This rewrites git history. Only do this if absolutely necessary"
echo "and after coordinating with all repository contributors."
echo

# Step 8: Credential Rotation Plan
echo -e "\033[1;36m[STEP 8] Implementing a credential rotation plan\033[0m"
echo "Implement a regular credential rotation schedule:"
echo "1. Create a calendar reminder to rotate credentials every 3-6 months"
echo "2. Document the rotation process in your team's documentation"
echo "3. Ensure multiple team members know how to rotate credentials"
echo

# Final summary
echo -e "\033[1;32mCredential Rotation Plan Complete\033[0m"
echo "Follow the steps above to secure your CI/CD pipeline"
echo "Refer to docs/secret-management.md for ongoing best practices"
echo
echo "========================================================"
