#!/bin/bash
# Script to clean up workflow files by fixing duplicate lines and syntax errors

set -e

echo "========================================================"
echo "  Workflow File Cleanup Script"
echo "========================================================"
echo "This script will clean up the workflow files by fixing duplicate lines and syntax errors"
echo

# Identify workflow files
WORKFLOW_FILES=$(find ./.gitea/workflows -name "*.yml")

# Clean up each file
for FILE in $WORKFLOW_FILES; do
  echo "Processing $FILE..."

  # Create backup
  cp "$FILE" "$FILE.cleanup.bak"

  # Fix duplicate mkdir and echo lines
  sed -i 's/# Create Docker config for crane\n          mkdir -p ~\/\.docker\n          # Create Docker config for crane\n          mkdir -p ~\/\.docker/# Create Docker config for crane\n          mkdir -p ~\/\.docker/g' "$FILE"

  # Fix duplicate EOF blocks
  sed -i '/EOF\n          \n          echo "Docker Hub auth configured with secure credentials"\n\n            }/,/EOF/{/EOF\n          \n          echo "Docker Hub auth configured with secure credentials"/!d;}' "$FILE"
  sed -i 's/EOF\n          \n          echo "Docker Hub auth configured with secure credentials"\n\n            }/EOF\n          \n          echo "Docker Hub auth configured with secure credentials"/g' "$FILE"

  # Remove any remaining duplicate } lines
  sed -i '/^          }/d' "$FILE"

  echo "✅ Cleaned up $FILE"
done

echo -e "\n\033[1;32m✅ All workflow files cleaned up!\033[0m"
echo
echo "Backups of the original files were created with .cleanup.bak extension."
echo "========================================================"
