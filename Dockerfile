# Use slim Python base (adjust Python version if needed)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system deps required by some packages (adjust as needed)
# Use netcat-openbsd (netcat virtual package has no candidate in some suites)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# Copy project files
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
