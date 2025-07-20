# Device Service Tests

This directory contains tests for the Device Service, including unit tests, integration tests, and database tests.

## Test Organization

The tests are organized into several files, each testing a specific aspect of the service:

- `test_device_endpoints.py`: Tests for basic device API endpoints
- `test_device_management.py`: Tests for device update and delete endpoints
- `test_probe_management.py`: Tests for probe management functionality
- `test_thermoworks_client.py`: Tests for the ThermoWorks API client, including rate limiting
- `test_webhook_handler.py`: Tests for webhook handling functionality
- `test_database.py`: Tests for database models, migrations, and audit logging

## Running Tests

### Using the Test Runner

The easiest way to run tests is using the provided `run_tests.py` script:

```bash
# Run all tests
./run_tests.py

# Run specific test files
./run_tests.py tests/test_thermoworks_client.py

# Run with verbose output
./run_tests.py -v
```

### Using pytest Directly

You can also run tests directly with pytest:

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_thermoworks_client.py

# Run with coverage
pytest --cov=. tests/
```

## Test Coverage

The tests aim to provide at least 80% code coverage for all modules. Coverage reports can be generated using:

```bash
pytest --cov=. --cov-report=html tests/
```

Then open `htmlcov/index.html` in your browser to view the coverage report.

## Test Dependencies

Tests require the following dependencies:

- pytest
- pytest-cov (for coverage reports)
- SQLAlchemy
- Flask

Install testing dependencies with:

```bash
pip install pytest pytest-cov
```

## Mocking Strategy

The tests use a combination of:

1. **Mocks**: For external dependencies like the ThermoWorks API
2. **In-memory databases**: For testing database models and operations
3. **Flask test client**: For testing API endpoints

## Adding New Tests

When adding new tests:

1. Choose the appropriate test file based on functionality
2. Use the existing test patterns and fixtures
3. Ensure tests are isolated and don't depend on each other
4. Run the tests to verify they pass
5. Check coverage to ensure new code is covered

## Continuous Integration

These tests are run automatically in the CI/CD pipeline on every push and pull request. All tests must pass for the pipeline to succeed.
