#!/bin/bash
# Script to fix workflow files with duplicate environment sections and remove hardcoded credentials

set -e

echo "========================================================"
echo "  Workflow File Fix Script"
echo "========================================================"
echo "This script will fix the workflow files with duplicate environment sections and remove hardcoded credentials"
echo

# Identify workflow files
WORKFLOW_FILES=$(find ./.gitea/workflows -name "*.yml")

# Fix each file
for FILE in $WORKFLOW_FILES; do
  echo "Processing $FILE..."

  # Create backup
  cp "$FILE" "$FILE.bak"

  # Step 1: Fix duplicate env sections by removing the second one
  # This uses sed to find the 'env:' line that comes after 'IMAGE_NAME' and remove that env section
  sed -i '/IMAGE_NAME:/,/env:/{//!d;/env:/d;}' "$FILE"

  # Step 2: Remove the hardcoded credentials completely
  sed -i '/AUTH_STRING="bG9yZG11ZmZpbjpkY2tyX3BhdF9nSWJScjBsRnZ6LTlxMFFZVDVKc01FQ0p5VDQ="/,/          }/ {
    /AUTH_STRING="bG9yZG11ZmZpbjpkY2tyX3BhdF9nSWJScjBsRnZ6LTlxMFFZVDVKc01FQ0p5VDQ="/d
    /echo "Docker Hub auth configured with valid credentials"/d
    /cat > ~\/.docker\/config.json << EOF/,/EOF/d
  }' "$FILE"

  # Step 3: Fix duplicate Docker config creation
  sed -i '/# Create Docker config for crane/{n;/mkdir -p ~\/.docker/{n;/echo "Setting up Docker Hub authentication..."/{N;d;}}}' "$FILE"

  echo "✅ Fixed $FILE"
done

# Verify fix worked
REMAINING_CREDS=$(grep -l "AUTH_STRING=\"bG9yZG11ZmZpbjpkY2tyX3BhdF9nSWJScjBsRnZ6LTlxMFFZVDVKc01FQ0p5VDQ=\"" --include="*.yml" ./.gitea/workflows/ | wc -l)

if [ "$REMAINING_CREDS" -gt 0 ]; then
  echo -e "\n\033[1;31m❌ WARNING: Some credential strings still remain in workflow files!\033[0m"
  grep -l "AUTH_STRING=\"bG9yZG11ZmZpbjpkY2tyX3BhdF9nSWJScjBsRnZ6LTlxMFFZVDVKc01FQ0p5VDQ=\"" --include="*.yml" ./.gitea/workflows/
  echo "Please check these files manually."
else
  echo -e "\n\033[1;32m✅ All hardcoded credentials successfully removed from workflow files!\033[0m"
fi

echo
echo "Backups of the original files were created with .bak extension."
echo "========================================================"
