# User Authentication System

This module provides user authentication capabilities for the Grill Stats application, allowing users to log in securely to access their personalized grilling dashboard and data.

## Features

### Core Authentication
- Email and password-based authentication
- Session management with Flask-Login
- Secure password hashing with Bcrypt
- Configurable session security

### Security Features
- Account lockout after multiple failed attempts (default: 5)
- Empty field validation
- Secure storage of user credentials
- Protection of all API routes requiring authentication

### User Experience
- Clear error messages for various login scenarios
- Redirect to intended page after login
- Welcoming dashboard upon successful login
- Responsive design for all screens

## Components

### Models
- `User` - User model with SQLAlchemy integration
  - Email, password, name, account status
  - Failed login tracking
  - Account locking mechanism

### Forms
- `LoginForm` - Form for email/password login
  - Input validation
  - Custom error messages

### Routes
- `/login` - Login page and authentication
- `/logout` - User logout
- `/dashboard` - User dashboard (protected)
- All API routes now protected with `@login_required`

### Templates
- `login.html` - Login form with Bootstrap styling
- `dashboard.html` - User dashboard
- `layout.html` - Base template with navigation
- `index.html` - Home page with app information

## Environment Setup

### Required Configuration
```python
SECRET_KEY = "your-secret-key"  # Used for session security
DATABASE_URL = "sqlite:///grill_stats.db"  # SQLite database for user storage
```

### Docker Configuration
Additional environment variables in docker-compose.yml:
```yaml
SECRET_KEY: ${SECRET_KEY:-default-dev-secret-key}
DATABASE_URL: ${DATABASE_URL:-sqlite:///grill_stats.db}
FLASK_ENV: ${FLASK_ENV:-development}
```

## Usage Examples

### Login Process
1. User navigates to `/login`
2. Enters email and password
3. System validates credentials:
   - If valid: redirects to dashboard with welcome message
   - If invalid: shows appropriate error message
   - If account locked: shows locked account message

### Development Testing
For testing purposes, a default test user is created:
- Email: `test@example.com`
- Password: `password`

## Testing

### Unit Tests
- Test successful login
- Test invalid credentials
- Test empty fields
- Test locked accounts
- Test failed login counting

### Integration Tests
- Test login/logout flow
- Test protected route access
- Test redirect after login
- Test session persistence

## Implementation Details

### Authentication Flow
1. User submits login form
2. System checks if user exists
3. If user exists, checks if account is locked
4. If not locked, verifies password
5. On success, creates session and redirects to dashboard
6. On failure, increments failed login count
7. If failures reach threshold, locks account

### Security Considerations
- Password hashing with Bcrypt
- Account lockout prevents brute force attacks
- Clear error messages without exposing sensitive info
- Protected routes with login_required decorator