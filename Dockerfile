FROM python:3.11-slim

WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else (filtered by .dockerignore)
COPY . .

# Default entrypoint — interactive TUI
CMD ["python", "src/main.py"]