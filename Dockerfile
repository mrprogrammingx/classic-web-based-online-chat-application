# Use slim Python base (adjust Python version if needed)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system deps required by some packages (adjust as needed)
# Use netcat-openbsd (netcat virtual package has no candidate in some suites)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# Copy project files
COPY . /app

# Copy entrypoint and make it executable
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create a non-root user 'app' to run the application. We keep the
# creation lightweight and use a system user so it doesn't collide with
# typical host UIDs. The entrypoint still runs as root so it can perform
# initialization (DB init, chown), then drops privileges before exec.
RUN groupadd -r app || true && useradd -r -g app -d /app -s /bin/sh app || true

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
