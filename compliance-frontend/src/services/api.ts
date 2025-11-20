/**
 * API Service
 *
 * This file handles all communication between the React frontend and the Python FastAPI backend.
 * Every request to the backend should go through functions in this file.
 *
 * The API server should be running at http://localhost:8000
 */

const API_BASE_URL = 'http://localhost:8000/api';

// =============================================================================
// AUTHENTICATION ENDPOINTS
// =============================================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  // TODO: Define what the backend returns after successful login
  // Usually: { access_token, token_type, user_info, etc. }
}

export const authLogin = async (credentials: LoginRequest): Promise<LoginResponse> => {
  // TODO: Implement login API call
  // POST to /api/auth/login with email and password
  // Return the response (usually contains a JWT token)
  throw new Error('Not implemented');
};

// =============================================================================
// VALIDATION ENDPOINTS
// =============================================================================

export interface ValidationRequest {
  file: File;
  tenant: string;
  state: string;
}

export interface ValidationResponse {
  // TODO: Define what the backend returns from validation
  // Based on MVP: { id, status, validation_results, control_totals, etc. }
}

export const validateFile = async (request: ValidationRequest): Promise<ValidationResponse> => {
  // TODO: Implement file upload and validation
  // POST to /api/validate as multipart/form-data with:
  //   - file: the CSV/Excel file
  //   - tenant: tenant_id
  //   - state: state_code
  // Return validation results from backend
  throw new Error('Not implemented');
};

// =============================================================================
// TENANT ENDPOINTS
// =============================================================================

export interface Tenant {
  // TODO: Define tenant structure based on your YAML config
  // Usually: { id, name, state, etc. }
}

export const getTenants = async (): Promise<Tenant[]> => {
  // TODO: Implement getting list of tenants
  // GET from /api/tenants
  // Return list of available tenants from backend
  throw new Error('Not implemented');
};

// =============================================================================
// STATE ENDPOINTS
// =============================================================================

export interface State {
  // TODO: Define state structure
  // Usually: { code, name, etc. }
}

export const getStates = async (): Promise<State[]> => {
  // TODO: Implement getting list of supported states
  // GET from /api/states
  // Return list of states the system supports (NJ, NY, etc.)
  throw new Error('Not implemented');
};
