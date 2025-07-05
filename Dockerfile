# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv
RUN pip install uv

# Copy only dependency definition first for better layer caching
COPY pyproject.toml .

# Install dependencies using uv without virtual environment
RUN uv pip install --system -e .

# Copy source code
COPY src/ ./src/

# Create a volume for input/output files
VOLUME /app/videos

# Set the working directory to videos where the files will be mounted
WORKDIR /app/videos

# Set the entrypoint to run the Python module from the app directory
ENTRYPOINT ["sh", "-c", "cd /app && python -m src.main \"$@\"", "--"]

# Set the default command to show help
CMD ["--help"]
