#!/bin/bash

# Simple validation script for grill-stats namespace change
echo "=== Grill Stats Namespace Validation ==="
echo "Checking that all references have been updated from 'grill-monitoring' to 'grill-stats'"

# Check for any remaining grill-monitoring references
echo "Searching for remaining 'grill-monitoring' references..."
if grep -r "grill-monitoring" . --exclude-dir=.git --exclude="*.log" 2>/dev/null; then
    echo "❌ Found remaining 'grill-monitoring' references that need to be updated"
    exit 1
else
    echo "✅ No remaining 'grill-monitoring' references found"
fi

# Check that grill-stats references exist
echo "Verifying 'grill-stats' references exist..."
if grep -r "grill-stats" . --exclude-dir=.git --exclude="*.log" >/dev/null 2>&1; then
    echo "✅ Found 'grill-stats' references - namespace change appears successful"
else
    echo "❌ No 'grill-stats' references found - something may be wrong"
    exit 1
fi

echo "✅ Namespace validation completed successfully"