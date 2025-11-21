# Charity Care Compliance Portal

Web application for healthcare compliance report generation and file validation. Includes user authentication, role-based access control, and multi-tenant support.

## Architecture

- **Backend**: FastAPI (Python) with PostgreSQL on Supabase
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Authentication**: JWT tokens with bcrypt password hashing
- **Database**: SQLAlchemy ORM with multi-tenant design

## Setup

### Prerequisites
- Python 3.13+
- Node.js 18+
- PostgreSQL connection string (Supabase)

### 1. Backend Setup

```bash
cd compliance-backend

# Create .env file (copy .env template and add your credentials)
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend will be available at**: `http://localhost:8000`

### 2. Frontend Setup

```bash
cd compliance-frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

**Frontend will be available at**: `http://localhost:5173`

## User Flow

### Admin User
1. Login with admin credentials: `admin@charity.local` / `admin123`
2. See Admin Dashboard
3. Create new users (sends temp password via email)
4. Manage user accounts

### Regular User
1. Receive temp password from admin via email
2. Login with email and temp password
3. Forced to change password on first login
4. Access Upload/Validation dashboard
5. Upload compliance files for processing

## Environment Variables

Create a `.env` file in the root directory:

```
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Security
SECRET_KEY=your-secret-key-change-in-production

# Email (optional for local testing)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with email/password
- `POST /api/auth/create-user` - Create new user (admin only)
- `POST /api/auth/change-password` - Change password (requires Bearer token)

## Database Models

- **User** - User accounts with roles (admin/user)
- **Tenant** - Multi-tenant organization isolation
- **ValidationRun** - File processing runs and history
- **ValidationError** - Detailed validation error tracking
- **AuditLog** - Audit trail of all actions

## Development

### Running Tests
```bash
pytest compliance-backend/tests
```

### Database Migrations
SQLAlchemy models auto-create tables on startup via `init_db()`

## Deployment

Environment variables are set via the hosting platform (AWS, Heroku, Docker, etc.). The `os.getenv()` pattern works everywhere - just set environment variables in your platform's dashboard instead of using .env files.

