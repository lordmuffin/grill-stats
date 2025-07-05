#!/bin/bash

# Multi-Agent Container Testing Script
# Tests all three services simultaneously using Podman

set -e

echo "🤖 Multi-Agent Container Testing System"
echo "========================================"

# Check dependencies
echo "🔍 Checking dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is required but not installed"
    exit 1
fi

# Check Podman
if ! command -v podman &> /dev/null; then
    echo "❌ Podman is required but not installed"
    exit 1
fi

echo "✅ Python3: $(python3 --version)"
echo "✅ Podman: $(podman --version)"
echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install --user requests
echo ""

# Make test script executable
chmod +x tests/multi-agent-test.py

# Run the multi-agent test
echo "🚀 Starting Multi-Agent Test..."
echo "This will:"
echo "  1️⃣  Build and test the original monolithic Flask app (port 5000)"
echo "  2️⃣  Build and test the Device Management Service (port 8080)"
echo "  3️⃣  Build and test the Temperature Data Service (port 8081)"
echo ""
echo "⏱️  Expected runtime: 2-3 minutes"
echo "📊 Results will be displayed and saved to files"
echo ""

# Create tests directory if it doesn't exist
mkdir -p tests

# Run the test
python3 tests/multi-agent-test.py

echo ""
echo "✅ Multi-Agent Test Complete!"
echo ""
echo "📄 Check the following files for detailed results:"
echo "   • multi-agent-test.log (detailed logs)"
echo "   • multi-agent-test-report.json (structured results)"
echo ""
echo "🔧 If any tests failed due to missing dependencies:"
echo "   • Monolithic app failure is expected without valid API keys"
echo "   • Microservices failures are expected without databases"
echo "   • Container build/start success indicates working architecture"