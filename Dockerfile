# Use a lightweight Python image as the base
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install required system libraries (audio processing and Python dependencies)
# --no-install-recommends avoids  installing unnecessary packages
RUN apt-get update && apt-get install -y --no-install-recommends \
	ffmpeg \
	libffi-dev \
	&& rm -rf /var/lib/apt/lists/*

# Copy the Python dependencies file and install dependencies
# This layer will be cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and required files
COPY PaulBot.py .

# Ensure Python output is not buffered (useful for logs)
ENV PYTHONUNBUFFERED=1

# Add a health check to ensure the bot is running correctly
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
	CMD pgrep -f "python PaulBot.py" || exit 1

# Command to run the bot when the container starts
CMD ["python", "PaulBot.py"]