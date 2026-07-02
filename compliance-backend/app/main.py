"""
Charity Care Compliance Portal - FastAPI Backend
==================================================

This is the web API server for the compliance analytics system.
It provides REST endpoints for:
  - User authentication (login, create account)
  - File validation (upload, process, get results)
  - Run history and management

The app also includes legacy CLI support for batch processing.

To run the server:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

To use CLI (legacy):
    python -m app.main <tenant_id> <state_code> <source_file>
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys
import os
from pathlib import Path
import argparse

# Import database initialization
from app.database.connection import init_db

# Import the ReportAdapter for legacy CLI support
from app.adapters.report_adapter import ReportAdapter

# ============================================================================
# FASTAPI APP SETUP
# ============================================================================
from app.api import auth, validation, analytics, admin
# Create FastAPI app
app = FastAPI(
    title="Charity Care Compliance Portal",
    description="REST API for healthcare compliance reporting",
    version="0.1.0"
)

app.include_router(auth.router)
app.include_router(validation.router)
app.include_router(analytics.router)
app.include_router(admin.router)

# Add CORS middleware so frontend can call the API
# Get allowed origins from environment variable or use defaults for development
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
allowed_origins = ["http://localhost:5173", "http://localhost:3000"]  # Development defaults

# Add production frontend URL if configured
if FRONTEND_URL:
    allowed_origins.append(FRONTEND_URL)
    # Also allow CloudFront HTTPS variant
    if FRONTEND_URL.startswith("http://"):
        allowed_origins.append(FRONTEND_URL.replace("http://", "https://"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # lets the frontend name downloads
)


# CSRF protection: browsers attach an Origin header to cross-site (and most
# same-origin) state-changing requests. Reject any mutating request whose
# Origin is present but not one of ours. This holds even if the session
# cookie is configured with SameSite=None for cross-domain deployments.
@app.middleware("http")
async def enforce_origin(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin and origin not in allowed_origins:
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-origin request rejected"},
            )
    return await call_next(request)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('compliance_reports.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# STARTUP EVENT
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting up - initializing database")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.get("/")
def read_root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Charity Care Compliance Portal API",
        "version": "0.1.0"
    }

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

# ============================================================================
# LEGACY CLI SUPPORT
# ============================================================================

def cli_main():
    """
    Legacy CLI function for batch processing.
    Allows running: python -m app.main <tenant_id> <state_code> <source_file>
    """
    parser = argparse.ArgumentParser(
        description="Generate state compliance reports from tenant data"
    )

    parser.add_argument("tenant_id", help="Tenant identifier (e.g., acme_health)")
    parser.add_argument("state_code", help="State code (e.g., NJ, NY)")
    parser.add_argument("source_file", help="Path to tenant's input CSV/Excel file")
    parser.add_argument("--run-id", help="Optional run identifier")
    parser.add_argument("--config-dir", default=None, help="Configuration directory (default: <backend>/config)")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: <backend>/output)")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't write output")

    args = parser.parse_args()

    if not Path(args.source_file).exists():
        logger.error(f"Source file not found: {args.source_file}")
        sys.exit(1)

    try:
        adapter = ReportAdapter(
            config_dir=args.config_dir,
            output_dir=args.output_dir
        )

        logger.info(f"Generating {args.state_code} report for {args.tenant_id}")

        artifact = adapter.generate(
            tenant_id=args.tenant_id,
            state_code=args.state_code,
            source_file=args.source_file,
            run_id=args.run_id,
            params={"dry_run": args.dry_run}
        )

        print("\n" + "="*60)
        print("REPORT GENERATION SUMMARY")
        print("="*60)
        print(f"Run ID:           {artifact.run_id}")
        print(f"Tenant:           {artifact.tenant_id}")
        print(f"State:            {artifact.state_code}")
        print(f"Status:           {artifact.status}")
        print(f"Records:          {artifact.control_totals.row_count if artifact.control_totals else 0}")

        if artifact.validation:
            print(f"Validation:       {'PASSED' if artifact.validation.passed else 'FAILED'}")
            print(f"Errors:           {len(artifact.validation.errors)}")
            print(f"Warnings:         {len(artifact.validation.warnings)}")

        if artifact.submission_file_path:
            print(f"Output File:      {artifact.submission_file_path}")
            print(f"Checksum:         {artifact.submission_file_checksum}")

        if artifact.generation_time_seconds:
            print(f"Generation Time:  {artifact.generation_time_seconds:.2f}s")

        print("="*60)

        if artifact.status == "errors":
            print("\nValidation errors detected. Review validation.json")
            sys.exit(2)
        elif artifact.status == "failed":
            print("\nReport generation failed")
            sys.exit(1)
        else:
            print("\nReport generated successfully")
            sys.exit(0)

    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        sys.exit(1)

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # If running as CLI (not via uvicorn), run the CLI
    cli_main()
