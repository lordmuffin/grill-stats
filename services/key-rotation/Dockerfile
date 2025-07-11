FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r keyrotation && useradd -r -g keyrotation keyrotation

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY key-rotation-automation.py .

# Create necessary directories
RUN mkdir -p /var/backups/vault-keys /tmp && \
    chown -R keyrotation:keyrotation /var/backups/vault-keys /tmp

# Set permissions
RUN chmod +x key-rotation-automation.py

# Switch to non-root user
USER keyrotation

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Default command
CMD ["python3", "key-rotation-automation.py"]