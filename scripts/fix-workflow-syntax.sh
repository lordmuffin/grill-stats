#!/bin/bash
# Script to fix syntax errors in workflow files

set -e

echo "========================================================"
echo "  Workflow Syntax Fix Script"
echo "========================================================"
echo "This script will fix syntax errors in the workflow files"
echo

# Identify workflow files
WORKFLOW_FILES=$(find ./.gitea/workflows -name "*.yml")

# Fix each file
for FILE in $WORKFLOW_FILES; do
  echo "Processing $FILE..."

  # Create backup
  cp "$FILE" "$FILE.syntax.bak"

  # Fix missing closing brace in heredoc section
  sed -i 's/          EOF/          }\n          EOF/g' "$FILE"

  # Remove duplicate closing brace
  sed -i '/^            }/d' "$FILE"

  echo "✅ Fixed $FILE"
done

echo -e "\n\033[1;32m✅ All workflow syntax errors fixed!\033[0m"
echo
echo "Backups of the original files were created with .syntax.bak extension."
echo "========================================================"
