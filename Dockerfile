FROM python:3.13-slim

WORKDIR /app

# System dependencies for lightkurve, scikit-learn, etc.
RUN apt-get update && apt-get install -y \\
    build-essential \\
    libgomp1 \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# We explicitly need Jinja2 for our new HTML templates
RUN pip install --no-cache-dir jinja2

COPY . .

# Expose port 8000
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
