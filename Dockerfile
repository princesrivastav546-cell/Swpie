# Use a lightweight Python base image
FROM python:3.10-slim

# Install PHP and system utilities
RUN apt-get update && apt-get install -y \
    php \
    php-cli \
    php-curl \
    php-json \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the bot
CMD ["python", "bot.py"]
