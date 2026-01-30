FROM python:3.12-slim

# Install system fonts required for image rendering (DejaVu, Liberation)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py document_generator.py ./
COPY templates/ templates/

# Copy default data (named volumes inherit these on first run)
COPY form_images/ form_images/
COPY presets/ presets/
COPY test_data/ test_data/

# Create runtime directories
RUN mkdir -p output test_outputs static

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
