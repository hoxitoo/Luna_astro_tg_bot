FROM python:3.11-slim

# Prevent .pyc files and enable real-time stdout/stderr logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies in a separate layer (better build cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Run as non-root user for security
RUN adduser --disabled-password --gecos "" botuser
USER botuser

# Apply DB migrations, then start the bot.
# Alembic is the single source of truth for schema (no create_all in code).
CMD ["sh", "-c", "alembic upgrade head && python -m bot.main"]
