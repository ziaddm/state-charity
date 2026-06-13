# Technology Stack

## Frontend

### Core Framework
- **React 18** - UI library
- **TypeScript** - Type-safe JavaScript
- **Vite** - Build tool and dev server

### UI & Styling
- **Tailwind CSS** - Utility-first CSS framework
- **Radix UI** - Headless UI components
- **Lucide React** - Icon library
- **Recharts** - Data visualization and charting

### State & Data Fetching
- **React Hooks** - Built-in state management (useState, useEffect)
- **Fetch API** - HTTP client for backend communication
- **LocalStorage** - Client-side authentication token storage

## Backend

### Core Framework
- **FastAPI** - Modern Python web framework
- **Python 3.9+** - Programming language
- **Uvicorn** - ASGI server

### Database
- **PostgreSQL** - Relational database
- **SQLAlchemy** - ORM and database toolkit
- **Alembic** - Database migration tool

### Data Processing
- **Pandas** - Data manipulation and analysis
- **NumPy** - Numerical computing

### Authentication & Security
- **PyJWT** - JSON Web Token implementation
- **Passlib** - Password hashing (bcrypt)
- **python-dotenv** - Environment variable management

### File Processing
- **Python CSV** - CSV file parsing
- **Custom fixed-width writer** - 212-byte record format

## Architecture Patterns

### Backend Architecture
- **Multi-tenant** - Single database, tenant-isolated data
- **Adapter Pattern** - ReportAdapter for validation pipeline
- **Service Layer** - Separated business logic (ingestion, validation)
- **Repository Pattern** - Database models abstracted via SQLAlchemy

### Validation Pipeline
1. **Extraction** - Parse CSV/fixed-width files
2. **Pre-validation** - File structure and format checks
3. **Mapping** - Transform to canonical format
4. **Coercion** - Type conversion and data cleaning
5. **Field Validation** - Schema compliance checking
6. **Control Totals** - Cross-record validation and duplicate detection
7. **Fail-Closed** - ALL warnings converted to errors, zero-tolerance policy

### Frontend Architecture
- **Component-based** - Reusable UI components
- **Page-based routing** - Manual routing via conditional rendering
- **Token-based auth** - JWT stored in localStorage
- **Role-based access** - Admin vs User views

## Data Flow

```
User Upload (CSV)
    ↓
FastAPI Endpoint (/api/validation/upload)
    ↓
ReportAdapter (Validation Pipeline)
    ↓
Field Validator + Control Totals Validator
    ↓
IF valid → Background Ingestion Task
    ↓
PostgreSQL (canonical_charity_care table)
    ↓
Analytics API (/api/analytics/*)
    ↓
React Frontend (Charts & Tables)
```

## Development Tools

### Backend Dev
- **pytest** - Testing framework
- **Black** - Code formatter
- **pylint** - Code linter

### Frontend Dev
- **ESLint** - JavaScript linter
- **Prettier** - Code formatter (if configured)
- **TypeScript Compiler** - Type checking

## Deployment

### Containerization
- **Docker** - Container platform
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Reverse proxy for frontend

### Cloud Infrastructure (AWS)
- **ECS Fargate** - Container orchestration
- **RDS PostgreSQL** - Managed database
- **Application Load Balancer** - Traffic distribution
- **ECR** - Container registry
- **VPC** - Network isolation
- **CloudWatch** - Logging and monitoring

## Security Features

- **JWT Authentication** - Token-based auth with expiration
- **Password Hashing** - Bcrypt with salting
- **CORS** - Cross-origin resource sharing configuration
- **SQL Injection Protection** - Parameterized queries via SQLAlchemy
- **Role-based Access Control** - Admin/User permissions
- **Tenant Isolation** - Data segregation by tenant_id

## Error Codes System

### Error Categories
- **E001-E099** - Required field and length violations
- **E100-E199** - Custom validation rule failures
- **E200-E299** - Financial/amount validation errors
- **E300-E399** - Duplicate and uniqueness violations
- **E400-E499** - Date/time validation errors
- **E500-E599** - Cross-field validation errors
- **E600-E699** - File structure errors

### Legacy Warning Codes (Converted to Errors)
- **W001-W699** - Originally warnings, now treated as blocking errors via fail-closed policy

## Performance Considerations

- **Background Tasks** - Async ingestion to prevent blocking
- **Batch Processing** - Pandas DataFrames for bulk operations
- **Database Indexing** - Tenant_id, record_id, file_hash indexes
- **Connection Pooling** - SQLAlchemy connection pool
- **Duplicate Detection** - In-memory hash checking before DB insert
