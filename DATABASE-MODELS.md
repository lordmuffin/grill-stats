# Database Models Architecture

## Current Architecture

The current database model architecture in the Grill Stats application uses a pattern where SQLAlchemy models are defined as nested classes within manager classes. This approach has several issues:

### Issues with Current Architecture

1. **Circular Import Problems**: The models reference each other (e.g., GrillingSession has a relationship to User), but the models are defined as nested classes, making it difficult for SQLAlchemy to resolve these relationships.

2. **Mapper Initialization Errors**: SQLAlchemy has trouble initializing mappers when models are defined as nested classes, particularly when relationships are involved.

3. **Error Encountered**: We're seeing the error: `When initializing mapper Mapper[GrillingSessionModel(grilling_sessions)], expression 'User' failed to locate a name ('User')`.

## Recommended Architecture

For better compatibility with SQLAlchemy, we recommend restructuring the models as follows:

### 1. Define Models as Top-Level Classes

```python
# models/user.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import db

class User(db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(120), unique=True, nullable=False)
    # ... other fields ...

    # Relationships
    grilling_sessions = relationship("GrillingSession", back_populates="user")
    temperature_alerts = relationship("TemperatureAlert", back_populates="user")
```

```python
# models/grilling_session.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship
from database import db

class GrillingSession(db.Model):
    __tablename__ = "grilling_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # ... other fields ...

    # Relationships
    user = relationship("User", back_populates="grilling_sessions")
```

### 2. Create Manager Classes for Business Logic

```python
# services/user_manager.py
from models.user import User

class UserManager:
    def __init__(self, db):
        self.db = db

    def create_user(self, email, password_hash, name=None):
        user = User(email=email, password=password_hash, name=name)
        self.db.session.add(user)
        self.db.session.commit()
        return user

    # ... other methods ...
```

```python
# services/session_manager.py
from models.grilling_session import GrillingSession

class SessionManager:
    def __init__(self, db):
        self.db = db

    def create_session(self, user_id, start_time=None, devices=None, session_type=None):
        # ... implementation ...

    # ... other methods ...
```

### 3. Initialize Models and Managers in a Central Place

```python
# database.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
```

```python
# app.py
from flask import Flask
from database import db, init_db
from models.user import User
from models.grilling_session import GrillingSession
from services.user_manager import UserManager
from services.session_manager import SessionManager

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
init_db(app)

# Initialize managers
user_manager = UserManager(db)
session_manager = SessionManager(db)
```

## Benefits of New Architecture

1. **Clear Separation of Concerns**: Models define data structure, managers define business logic
2. **Improved SQLAlchemy Compatibility**: Standard pattern that SQLAlchemy recognizes
3. **Easier Relationship Management**: Relationships between models are more straightforward
4. **Better Testing**: Models and managers can be tested independently

## Migration Strategy

To migrate to the new architecture:

1. Define models as top-level classes in separate files
2. Move business logic to manager classes
3. Update imports and initialization in app.py
4. Update references throughout the codebase

This change will require careful testing to ensure all functionality works as expected.
