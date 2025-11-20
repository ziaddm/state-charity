# API Architecture Guide - Real World Patterns

## Directory Structure in Professional Settings

```
state-charity/                          # Monorepo root
├── backend/                            # Python FastAPI server
│   ├── app/
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── auth.py            # POST /api/auth/login, /api/auth/logout, etc
│   │   │       ├── validation.py      # POST /api/validation/submit
│   │   │       ├── tenants.py         # GET /api/tenants
│   │   │       └── states.py          # GET /api/states
│   │   ├── models/                    # Domain models (Patient, ValidationResult, etc)
│   │   ├── services/                  # Business logic (validation, auth, etc)
│   │   ├── adapters/                  # Your existing ReportAdapter lives here
│   │   └── schemas/                   # Pydantic request/response schemas
│   ├── tests/
│   ├── requirements.txt
│   └── docker-compose.yml
│
├── frontend/                           # React/TypeScript app
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/                  # ← API client library (where api.ts lives)
│   │   │   └── api.ts                 # Thin wrapper around HTTP calls
│   │   ├── hooks/                     # Custom React hooks for API calls
│   │   │   └── useValidation.ts       # Example: hook that calls validateFile()
│   │   ├── types/                     # TypeScript interfaces (mirrors backend schemas)
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── docs/                              # Shared documentation
│   ├── API.md                         # OpenAPI spec or endpoint documentation
│   └── ARCHITECTURE.md
│
└── README.md
```

## What is `services/api.ts`?

It's a **thin HTTP client layer** that:
- Knows about your backend endpoints
- Handles request/response serialization
- Manages authentication tokens
- Provides TypeScript types for API calls

**It is NOT a full REST client library** - it's specific to YOUR app.

### Bad Pattern (Don't Do This):
```typescript
// ❌ Making HTTP calls directly in components
export default function UploadValidation() {
  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch('http://localhost:8000/api/validate', {
      method: 'POST',
      body: formData
    });
    // ... handle response
  }
}
```
**Why bad:**
- URL hardcoded everywhere
- No reusability
- Duplicated error handling
- Hard to change API later

### Good Pattern (What You're Doing):
```typescript
// ✅ api.ts is your single source of truth
export const validateFile = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return fetch(`${API_BASE_URL}/validate`, {
    method: 'POST',
    body: formData
  });
}

// ✅ Components just call the function
export default function UploadValidation() {
  const handleUpload = async (file: File) => {
    const result = await validateFile(file);
  }
}
```

---

## Implementation Order in Real Projects

### **Phase 1: Backend First (Weeks 1-2)**
Why? Because:
1. Frontend needs API contracts to know what to call
2. Can test backend independently
3. Frontend can use mock/stub data while backend is built
4. Easier to parallelize work (one person on backend, one on frontend)

**What gets built:**
- ✅ FastAPI app with all endpoints
- ✅ Request/Response Pydantic schemas
- ✅ Documentation (OpenAPI/Swagger)
- ✅ Basic tests

### **Phase 2: API Contract Definition (Week 2)**
Backend team writes OpenAPI spec:
```yaml
# openapi.yaml - Single source of truth
paths:
  /api/validation/submit:
    post:
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                tenant_id:
                  type: string
                state:
                  type: string
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ValidationResult'
```

**Frontend reads this spec and:**
- Knows exact endpoint URLs
- Knows request/response shapes
- Can auto-generate TypeScript types
- Can mock responses while waiting for backend

### **Phase 3: Frontend Implementation (Weeks 2-3, in parallel with Phase 2)**
```typescript
// ✅ From OpenAPI spec, frontend generates TypeScript types
export interface ValidationResult {
  id: string;
  status: 'ready' | 'errors' | 'warnings';
  // ... etc
}

// ✅ api.ts matches the spec exactly
export const validateFile = async (request: ValidationRequest): Promise<ValidationResult> => {
  const response = await fetch(`${API_BASE_URL}/validation/submit`, {
    method: 'POST',
    body: formData
  });
  return response.json();
}

// ✅ Components use the types and functions
export default function UploadValidation() {
  const [results, setResults] = useState<ValidationResult[]>([]);
  // ...
}
```

### **Phase 4: Integration Testing (Week 3-4)**
- Spin up backend + frontend together
- Run end-to-end tests
- Find contract mismatches
- Fix and iterate

---

## Where Does `api.ts` Live?

### Option A: In Frontend (What You're Doing)
```
frontend/src/services/api.ts
```
✅ Pros:
- Frontend can be developed/tested independently
- Easier to mock for testing
- Clear separation: frontend owns its HTTP logic

❌ Cons:
- If you have multiple frontends (web, mobile, desktop), you duplicate api.ts logic

### Option B: Shared Package (Enterprise Pattern)
```
packages/
├── api-client/                # Shared package (npm module)
│   ├── src/
│   │   ├── api.ts
│   │   └── types.ts
│   ├── package.json
│   └── tsconfig.json
│
├── frontend/
│   └── package.json           # depends on @company/api-client
│
└── mobile/
    └── package.json           # depends on @company/api-client
```

✅ Pros:
- Code reused across multiple frontends
- Single source of truth for API contract

❌ Cons:
- Extra build complexity
- Overkill for small projects

**Use Option B only if you have:** 3+ frontends, or your API client is >500 lines.

---

## In YOUR Project Right Now

You're in the right place:
```
compliance-frontend/src/services/api.ts  ✅ Correct location
```

**Reasoning:**
- Single frontend (React web app)
- Early stage
- Clear backend/frontend separation
- Easy to test independently

Later, if you add a mobile app, you can:
1. Extract api.ts into shared package
2. Both frontends depend on it
3. Update once, deploy everywhere

---

## Real-World Timeline

| Week | Backend | Frontend | Notes |
|------|---------|----------|-------|
| 1 | FastAPI scaffold, auth endpoints, OpenAPI spec | Waiting on spec | Backend publishes OpenAPI early |
| 2 | Validation endpoint, tests | api.ts + Login component | Parallel work possible |
| 3 | Upload handler, storage | Upload component | Integration work starts |
| 4 | Performance tuning | Polish UI, error handling | Bug fixes, edge cases |
| 5 | Deployment setup | Testing in staging | Both teams together |

---

## Key Principles

1. **Backend defines the contract first** (OpenAPI/Swagger)
2. **Frontend implements to the contract** (api.ts mirrors the spec)
3. **Never hardcode URLs in components** (always go through api.ts)
4. **Keep api.ts thin** (just HTTP calls, no business logic)
5. **Use TypeScript interfaces** (catches mismatches at compile time, not runtime)
6. **Mock API responses for frontend testing** (don't need backend running)
7. **Test backend independently** (unit tests, integration tests)

---

## What api.ts Should NOT Do

❌ Business logic (validation rules, transformations)
❌ State management (that's Redux/Zustand/Context)
❌ Routing (that's React Router)
❌ Error recovery (that's in the component)

What it SHOULD do:

✅ Make HTTP requests
✅ Serialize/deserialize data
✅ Handle auth tokens
✅ Provide TypeScript types
✅ Document endpoints with comments

---

## Next Steps for YOUR Project

1. **Define Backend Endpoints** (create app/api/main.py in backend/)
2. **Write OpenAPI Spec** (even simple one in comments)
3. **Implement Backend Routes** (validation.py, auth.py, etc)
4. **Fill in api.ts Functions** (match the backend endpoints)
5. **Test Backend** (curl commands or Postman)
6. **Connect Frontend** (update components to use api.ts)
7. **Integration Test** (both running together)

You're starting at step 1. Want to build the backend FastAPI server next?
