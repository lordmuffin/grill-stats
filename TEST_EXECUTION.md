# Parallel Testing Execution Guide

This document provides instructions for executing the parallel test plan for the Grill-Stats application in production at grill-stats.lab.apj.dev.

## Prerequisites

Before beginning the tests, ensure you have the following:

1. SSH access to test execution environment
2. Required test credentials:
   - Test user email and password
   - ThermoWorks API key
   - Home Assistant long-lived access token
3. Required tools:
   - bash
   - curl
   - jq
   - openssl (for TLS testing)
   - nmap (optional, for port scanning)
   - Firefox, Chrome, or Chromium (optional, for UI screenshots)

## Test Script Setup

1. Download all test scripts to your test environment:
   ```bash
   git clone https://github.com/your-org/grill-stats.git
   cd grill-stats
   ```

2. Make all scripts executable:
   ```bash
   chmod +x TRACK*.sh FINAL_INTEGRATION_TEST.sh
   ```

3. Set up environment variables (or modify scripts directly):
   ```bash
   # Required credentials
   export TEST_EMAIL=$(op item get "op://HomeLab/grill-stats-prod-creds-1password/ADMIN_USER")
   export TEST_PASSWORD=$(op item get "op://HomeLab/grill-stats-prod-creds-1password/ADMIN_PASSWORD")
   export HA_TOKEN=$(op item get "op://HomeLab/grill-stats home assistant token/password")

   # Test parameters (optional)
   export TEST_DURATION=12   # Long-running test duration in hours
   export CONCURRENCY=10     # Number of concurrent users for load test
   ```

## Parallel Execution Plan

The tests are designed to be run in parallel by different agents (people or processes). Each track focuses on different aspects of the application and can be executed independently.

### Agent Assignments

| Track | Description | Script | Agent |
|-------|-------------|--------|-------|
| 1 | API & Core Functionality | TRACK1_API_CORE.sh | Agent 1 |
| 2 | ThermoWorks Integration | TRACK2_THERMOWORKS.sh | Agent 2 |
| 3 | Home Assistant & Data Storage | TRACK3_HA_STORAGE.sh | Agent 3 |
| 4 | Performance & Reliability | TRACK4_PERFORMANCE.sh | Agent 4 |
| 5 | Security, Deployment & UI | TRACK5_SECURITY_UI.sh | Agent 5 |

### Coordination Requirements

Some tests have dependencies that require coordination between agents:

1. **ThermoWorks Device Discovery → Home Assistant Sensor Creation**
   - Agent 2 should complete device discovery before Agent 3 tests sensor creation
   - Agent 2 should share discovered device IDs with Agent 3

2. **Data Collection → Data Storage Testing**
   - Agent 2 should collect temperature data before Agent 3 tests data storage
   - Agent 2 should confirm to Agent 3 when data has been collected

3. **Load Testing → UI Testing**
   - Agents 4 and 5 should coordinate when running performance tests
   - Agent 5 should schedule UI testing outside of peak load testing times

## Execution Instructions

### For Each Agent

1. **Review your assigned script** to understand the tests you'll be performing

2. **Update the script with required credentials** if not using environment variables:
   ```bash
   # Example: Edit the script to update credentials
   nano TRACK1_API_CORE.sh

   # Find and update these lines:
   TEST_EMAIL="test@example.com"
   TEST_PASSWORD="password"
   ```

3. **Execute your assigned script**:
   ```bash
   # Example for Agent 1
   ./TRACK1_API_CORE.sh
   ```

4. **Monitor and document the progress** of your tests

5. **Communicate with other agents** when reaching coordination points

6. **Document any issues** encountered during testing

### Track-Specific Notes

#### Track 1: API & Core Functionality
- Focuses on basic connectivity and API endpoints
- Usually completes in 15-30 minutes
- No special requirements beyond basic credentials

#### Track 2: ThermoWorks Integration
- Tests ThermoWorks API authentication and device discovery
- Usually completes in 30-45 minutes
- Requires active ThermoWorks devices to be available
- **Coordination point**: Share discovered device IDs with Agent 3

#### Track 3: Home Assistant Integration & Data Storage
- Tests data flow from devices to Home Assistant
- Usually completes in 45-60 minutes
- Requires Home Assistant token and connection to HA instance
- **Coordination point**: Wait for Agent 2 to confirm data collection

#### Track 4: Performance & Reliability
- Tests system under load and over extended periods
- Takes longer (1-12 hours depending on TEST_DURATION setting)
- Can be resource-intensive; ensure test environment can handle it
- **Coordination point**: Notify Agent 5 when running peak load tests

#### Track 5: Security, Deployment & UI
- Tests security measures and UI functionality
- Usually completes in 45-60 minutes
- Optional tools (openssl, nmap, browser) enhance test coverage
- **Coordination point**: Schedule UI testing outside of peak load times

## Final Integration Testing

After all individual tracks are completed, a final integration test should be performed:

1. Ensure all individual track tests have completed
2. Collect and review all track logs
3. Execute the final integration test script:
   ```bash
   ./FINAL_INTEGRATION_TEST.sh
   ```
4. The final script will:
   - Process results from all tracks
   - Perform end-to-end tests across all components
   - Verify system recovery capabilities
   - Generate a final go/no-go recommendation

## Reporting Results

After all tests are completed:

1. Collect all log files:
   ```bash
   mkdir -p test-results
   cp /tmp/grill-stats-*.log test-results/
   cp /tmp/grill-stats-screenshots/* test-results/ 2>/dev/null
   ```

2. Archive the results:
   ```bash
   tar -czf grill-stats-test-results-$(date +%Y%m%d).tar.gz test-results
   ```

3. Review the final integration test report to determine if the system is ready for production

## Troubleshooting

If any script fails during execution:

1. Check the log file for specific error messages
2. Verify that all prerequisites are met
3. Ensure correct credentials are being used
4. Check connectivity to the target environment
5. If the issue persists, document the exact error and consult with the development team

## Contact Information

For questions or issues during testing:

- **ThermoWorks Integration:** Contact [thermoworks-team@example.com](mailto:thermoworks-team@example.com)
- **Home Assistant Integration:** Contact [ha-team@example.com](mailto:ha-team@example.com)
- **Performance Issues:** Contact [ops-team@example.com](mailto:ops-team@example.com)
- **Test Coordination:** Contact [qa-lead@example.com](mailto:qa-lead@example.com)
