# Dockerfile for Compliance Report Dashboard
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for layer caching)
COPY requirements.txt requirements-dashboard.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-dashboard.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp_uploads output logs

# Expose port
EXPOSE 8050

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DASH_DEBUG=False

# Run with gunicorn for production
CMD ["gunicorn", "-b", "0.0.0.0:8050", "--workers", "4", "--timeout", "120", "dashboard.app:server"]
