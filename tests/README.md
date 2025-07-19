# Test Suite Documentation

This directory contains the test suite for the Grill Stats application. It includes various utilities and helpers for effective testing.

## Isolated Database Testing

One of the key challenges in testing this application is handling circular dependencies between SQLAlchemy models. The following approach has been implemented to solve this issue:

### Problem: Circular Dependencies

The application's models have circular dependencies:
- `User` model references `Device` model via relationships
- `Device` model references `User` model via relationships
- Both reference `TemperatureAlert` model
- etc.

This creates problems during testing when we need to create a subset of models for a specific test.

### Solution: Isolated Test Models

We've implemented an isolation strategy with the following components:

1. **IsolatedTestDatabase**: Creates a test database with isolated model definitions that don't have circular dependencies.
2. **Isolated Model Classes**: Wrappers around the isolated database models that implement the same API as the real models.
3. **Test Utilities**: Helper functions for working with isolated test models.

### How to Use Isolated Testing

#### 1. Basic Isolated Test

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from tests.isolated import IsolatedUser

# Create Flask app and database
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
db = SQLAlchemy(app)

# Use isolated user model
with app.app_context():
    user_manager = IsolatedUser(db)
    db.create_all()

    # Create test user
    user = user_manager.create_user("test@example.com", "password_hash")

    # Use the user model as needed
    assert user.email == "test@example.com"
```

#### 2. Using IsolatedTestDatabase Directly

```python
from flask import Flask
from tests.utils import IsolatedTestDatabase

# Create Flask app
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

# Create isolated test database
with app.app_context():
    test_db = IsolatedTestDatabase(app)
    db = test_db.get_db()

    # Access isolated models
    UserModel = test_db.UserModel
    DeviceModel = test_db.DeviceModel

    # Create and work with models
    user = UserModel(email="test@example.com", password="hash")
    db.session.add(user)
    db.session.commit()
```

#### 3. Complete Example

See `tests/unit/auth/isolated_auth_test.py` for a complete example of isolated testing.

### Architecture

The isolation approach consists of the following components:

1. **tests/utils/isolated_db.py**: Contains `IsolatedTestDatabase` class for creating isolated test models.
2. **tests/utils/db_helpers.py**: Utility functions for working with databases in tests.
3. **tests/isolated/models/**: Isolated model classes that implement the same API as the real models.

### Benefits

- Tests run faster by using SQLite in-memory databases
- No circular dependencies during testing
- Better isolation between tests
- Simplified test setup and teardown
- Improved test reliability

## Test Structure

The test suite is organized as follows:

- **unit/**: Unit tests for individual components
- **integration/**: Integration tests that test component interactions
- **e2e/**: End-to-end tests that test the entire application
- **mocks/**: Mock versions of classes for testing
- **utils/**: Utilities for testing
- **isolated/**: Isolated model classes for testing
- **fixtures/**: Test data and fixtures

## Running Tests

To run the tests:

```bash
# Run all tests
python -m pytest

# Run specific tests
python -m pytest tests/unit/

# Run isolated tests
python -m pytest tests/unit/auth/isolated_auth_test.py

# Run tests with coverage
python -m pytest --cov=.
```

## Adding New Tests

When adding new tests:

1. For tests that interact with models, use the isolated testing approach to avoid circular dependencies.
2. Create a new test file in the appropriate directory (unit/, integration/, e2e/).
3. For unit tests, use pytest fixtures when possible to set up dependencies.
4. For integration tests, ensure proper teardown to avoid test contamination.

## Test Utilities

Several test utilities are available:

- **tests/utils/test_models.py**: Create isolated model definitions.
- **tests/utils/test_db.py**: Set up isolated test databases.
- **tests/utils/db_helpers.py**: Helper functions for database operations.
- **tests/isolated/models/**: Isolated model classes that implement the same API as real models.

## Troubleshooting

### Common Issues

1. **"RuntimeError: A 'SQLAlchemy' instance has already been registered on this Flask app"**
   - Use `existing_db` parameter when creating `IsolatedTestDatabase`
   - Example: `test_db = IsolatedTestDatabase(app, existing_db=db)`

2. **"KeyError: 'DeviceModel'"**
   - Ensure all required models are defined in `IsolatedTestDatabase`
   - Check for typos in model names

3. **"sqlalchemy.exc.InvalidRequestError: When initializing mapper..."**
   - This usually indicates circular dependencies
   - Use isolated models to avoid this issue

### Adding New Isolated Models

If you need to add a new isolated model:

1. Create a new file in `tests/isolated/models/` with your model class.
2. Add your model to `tests/isolated/models/__init__.py`.
3. Add your model to `tests/isolated/__init__.py`.
4. Add a new model definition method in `IsolatedTestDatabase`.
