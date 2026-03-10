# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for some python packages like psycopg2 if used)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    clamav \
    && rm -rf /var/lib/apt/lists/* \
    && freshclam

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
# Assumes app/main.py is the entry point and 'app' is the FastAPI instance
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
