FROM python:3.13-slim

WORKDIR /app

# System dependencies for lightkurve, scikit-learn, etc.
RUN apt-get update && apt-get install -y \\
    build-essential \\
    libgomp1 \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose standard port
EXPOSE 8000

# Start server honoring $PORT environment variable (Render / Railway / Cloud Run default)
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"

