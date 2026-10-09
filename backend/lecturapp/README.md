# Lecturapp - Reading App

This Django app provides a custom authentication system for reading operators with encrypted passwords and token-based authentication.

## Features

- **ReadingOperator Model**: Custom user model with name, surname, username, and encrypted password
- **Token-Based Authentication**: Secure token-based authentication system
- **Custom Authentication**: All endpoints are secured with custom token authentication
- **Password Encryption**: Passwords are automatically encrypted using Django's password hashing
- **REST API**: Full CRUD operations for reading operators
- **Admin Interface**: Django admin integration for managing operators and tokens

## Models

### ReadingOperator
- `name`: First name of the operator
- `surname`: Last name of the operator  
- `username`: Unique username for authentication
- `password`: Encrypted password
- `is_active`: Whether the operator is active
- `created_at`: Timestamp when the operator was created
- `updated_at`: Timestamp when the operator was last updated

### Token
- `operator`: Foreign key to ReadingOperator
- `token`: Unique authentication token (UUID)
- `created_at`: Timestamp when the token was created

## Authentication Flow

1. **Login**: Send username/password to `/lecturapp/auth/login/`
2. **Receive Token**: Server returns a unique token
3. **Use Token**: Include token in subsequent requests
4. **Logout**: Call `/lecturapp/auth/logout/` to invalidate token

## Token Usage

Tokens can be provided in several ways:

1. **Headers**:
```
X-App-Token: your-token-here
```

2. **Authorization Header** (Bearer token):
```
Authorization: Bearer your-token-here
```

3. **POST Body** (JSON):
```json
{
    "token": "your-token-here"
}
```

4. **GET Parameters** (for testing):
```
?token=your-token-here
```

## API Endpoints

### Authentication
- `POST /lecturapp/auth/login/` - Authenticate operator and get token
- `GET /lecturapp/auth/validate-token/` - Validate a token
- `POST /lecturapp/auth/password-change/` - Change password (requires authentication)
- `POST /lecturapp/auth/logout/` - Logout and invalidate token (requires authentication)
- `GET /lecturapp/auth/profile/` - Get current operator profile (requires authentication)

### Operators Management
- `GET /lecturapp/operators/` - List all operators (requires authentication)
- `POST /lecturapp/operators/` - Create new operator (requires authentication)
- `GET /lecturapp/operators/{id}/` - Get specific operator (requires authentication)
- `PUT /lecturapp/operators/{id}/` - Update operator (requires authentication)
- `DELETE /lecturapp/operators/{id}/` - Delete operator (requires authentication)

### Protected Endpoints
- `GET /lecturapp/protected/` - Example protected endpoint (requires authentication)

## Usage Examples

### Creating a Super Operator
```bash
python3 manage.py createsuperoperator --username admin --password secret123 --name Admin --surname User
```

### Authentication via API
```bash
# Login and get token
curl -X POST http://localhost:8000/lecturapp/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret123"}'

# Response will include a token:
# {
#   "success": true,
#   "message": "Authentication successful",
#   "token": "550e8400-e29b-41d4-a716-446655440000",
#   "operator": {...}
# }
```

### Accessing Protected Endpoints with Token
```bash
# Using X-Token header
curl -X GET http://localhost:8000/lecturapp/protected/ \
  -H "X-Token: 550e8400-e29b-41d4-a716-446655440000"

# Using Authorization header
curl -X GET http://localhost:8000/lecturapp/protected/ \
  -H "Authorization: Bearer 550e8400-e29b-41d4-a716-446655440000"

# Using GET parameter
curl -X GET "http://localhost:8000/lecturapp/protected/?token=550e8400-e29b-41d4-a716-446655440000"
```

### Validating a Token
```bash
curl -X GET http://localhost:8000/lecturapp/auth/validate-token/ \
  -H "X-Token: 550e8400-e29b-41d4-a716-446655440000"
```

### Logout (Invalidate Token)
```bash
curl -X POST http://localhost:8000/lecturapp/auth/logout/ \
  -H "X-Token: 550e8400-e29b-41d4-a716-446655440000"
```

## Security Features

- **Token-Based Authentication**: No need to send username/password with every request
- **Unique Tokens**: Each login generates a new unique token
- **Token Invalidation**: Logout immediately invalidates the token
- **Password Encryption**: Passwords are automatically encrypted using Django's `make_password()` function
- **Username Validation**: Alphanumeric and underscore only
- **Minimum Username Length**: 3 characters required
- **Password Confirmation**: Required for creation and updates
- **Active/Inactive Status**: Operators can be deactivated

## Custom Decorator

The app provides a custom decorator `@lecturapp_auth_required` that can be used to protect any view:

```python
from lecturapp.decorators import lecturapp_auth_required

@lecturapp_auth_required
def my_protected_view(request):
    operator = get_authenticated_operator(request)
    return JsonResponse({'message': f'Hello {operator.name}!'})
```

## Database

The app creates two tables:
- `lecturapp_reading_operator` - Stores operator information
- `lecturapp_token` - Stores authentication tokens

Make sure to run migrations:

```bash
python3 manage.py makemigrations lecturapp
python3 manage.py migrate
```