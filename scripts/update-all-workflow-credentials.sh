#!/bin/bash
# Script to update credentials in all workflow files
# This script replaces hardcoded credentials with secure secrets in all CI/CD workflow files

set -e

echo "========================================================"
echo "  Workflow Credential Update Script"
echo "========================================================"
echo "This script will update all workflow files to use secure credential management"
echo

# Find all workflow files with hardcoded credentials
WORKFLOW_FILES=$(grep -l "AUTH_STRING=\"bG9yZG11ZmZpbjpkY2tyX3BhdF9nSWJScjBsRnZ6LTlxMFFZVDVKc01FQ0p5VDQ=\"" --include="*.yaml" --include="*.yml" ./.gitea/workflows/*.yml)

# Check if any files were found
if [ -z "$WORKFLOW_FILES" ]; then
    echo "No workflow files with hardcoded credentials found. Nothing to update."
    exit 0
fi

echo "Found $(echo "$WORKFLOW_FILES" | wc -l) workflow files with hardcoded credentials:"
echo "$WORKFLOW_FILES" | sed 's/^/  - /'
echo

# Update each file
echo "Updating workflow files..."
for FILE in $WORKFLOW_FILES; do
    echo "Processing $FILE..."

    # Create backup of original file
    cp "$FILE" "$FILE.bak"

    # Replace the credential block with secure implementation
    sed -i '
    /# Use Docker Hub credentials/,/}/ {
        # Match the start of the block
        /# Use Docker Hub credentials/ {
            c\
          # Create Docker config for crane\
          mkdir -p ~/.docker\
          echo "Setting up Docker Hub authentication..."\
\
          # Check if Docker auth is available\
          if [ -z "$DOCKER_AUTH" ]; then\
            echo "\\u274c ERROR: DOCKER_AUTH secret is not set"\
            echo "Please configure the DOCKER_AUTH secret in your repository settings"\
            echo "Format should be: username:password or username:token encoded in base64"\
            exit 1\
          fi\
\
          # Use Docker Hub credentials from secrets\
          cat > ~/.docker/config.json << EOF\
          {\
            "auths": {\
              "https://index.docker.io/v1/": {\
                "auth": "${DOCKER_AUTH}"\
              }\
            }\
          }\
          EOF\
          \
          echo "Docker Hub auth configured with secure credentials"
            # Skip all lines until the end of the current block
            :a
            n
            /}/!ba
        }
    }
    ' "$FILE"

    # Add env section with the secret
    sed -i '/    steps:/i\
    env:\
      # Use secure repository secrets instead of hardcoded values\
      DOCKER_AUTH: ${{ secrets.DOCKER_AUTH }}' "$FILE"

    echo "✅ Updated $FILE"
done

echo
echo -e "\033[1;32mAll workflow files updated successfully!\033[0m"
echo "Please review the changes and commit them to the repository."
echo "Remember to add the DOCKER_AUTH secret to your repository settings."
echo
echo "Backups of the original files were created with .bak extension."
echo "You can remove them after verifying the changes with:"
echo "  rm ./.gitea/workflows/*.bak"
echo
echo "========================================================"
