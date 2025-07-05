#!/bin/bash

# Video Subtitle Generator Docker Runner Script
# This script makes it easy to run the video subtitle generator in Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Video Subtitle Generator Docker Runner"
    echo ""
    echo "Usage: $0 <video_file> [language]"
    echo ""
    echo "Arguments:"
    echo "  video_file    Path to the video file (MP4 or MKV)"
    echo "  language      Language code (optional, default: en)"
    echo ""
    echo "Supported languages:"
    echo "  en - English (default)"
    echo "  es - Spanish"
    echo "  fr - French"
    echo "  de - German"
    echo "  it - Italian"
    echo "  pt - Portuguese"
    echo "  ru - Russian"
    echo "  zh - Chinese"
    echo ""
    echo "Examples:"
    echo "  $0 video.mp4"
    echo "  $0 video.mp4 es"
    echo "  $0 /path/to/video.mkv fr"
    echo ""
    echo "Note: Make sure your video file is in the ./videos directory"
    echo "      or use an absolute path that will be mounted to the container."
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    print_info "Note: Docker Compose is usually included with Docker Desktop."
    exit 1
fi

# Check arguments
if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

VIDEO_FILE="$1"
LANGUAGE="${2:-en}"

# Validate video file
if [ ! -f "$VIDEO_FILE" ]; then
    print_error "Video file not found: $VIDEO_FILE"
    exit 1
fi

# Get absolute path of video file
VIDEO_ABSOLUTE_PATH=$(realpath "$VIDEO_FILE")
VIDEO_FILENAME=$(basename "$VIDEO_FILE")

# Create videos directory if it doesn't exist
mkdir -p ./videos

# Copy video file to videos directory if it's not already there
if [ "$VIDEO_ABSOLUTE_PATH" != "$(realpath ./videos/$VIDEO_FILENAME)" ]; then
    print_info "Copying video file to ./videos directory..."
    cp "$VIDEO_FILE" "./videos/$VIDEO_FILENAME"
fi

print_info "Running video subtitle generation..."
print_info "Video: $VIDEO_FILENAME"
print_info "Language: $LANGUAGE"

# Stop any running containers and build fresh
print_info "Stopping any running containers..."
docker-compose down -v --remove-orphans 2>/dev/null || true

# Force kill any remaining containers with the same name
print_info "Ensuring clean state..."
docker rm -f video-subtitle-generator 2>/dev/null || true

print_info "Building Docker image..."
docker-compose build --no-cache

# Run the container using docker-compose
docker-compose run --rm video-subtitle-generator "$VIDEO_FILENAME" "$LANGUAGE"

# Check if SRT file was created
SRT_FILE="./videos/${VIDEO_FILENAME%.*}.srt"
if [ -f "$SRT_FILE" ]; then
    print_success "Subtitles generated successfully!"
    
    # Copy SRT file to the original video location
    ORIGINAL_SRT_PATH="${VIDEO_FILE%.*}.srt"
    if [ "$VIDEO_ABSOLUTE_PATH" != "$(realpath ./videos/$VIDEO_FILENAME)" ]; then
        print_info "Copying SRT file to original video location..."
        cp "$SRT_FILE" "$ORIGINAL_SRT_PATH"
        print_info "SRT file: $ORIGINAL_SRT_PATH"
    else
        print_info "SRT file: $SRT_FILE"
    fi
    
    # Show file size
    FILE_SIZE=$(du -h "$SRT_FILE" | cut -f1)
    print_info "File size: $FILE_SIZE"
    
    # Clean up the copy in videos directory if it was copied there
    if [ "$VIDEO_ABSOLUTE_PATH" != "$(realpath ./videos/$VIDEO_FILENAME)" ]; then
        print_info "Cleaning up temporary files..."
        rm "$SRT_FILE"
        rm "./videos/$VIDEO_FILENAME"
    fi
else
    print_error "Failed to generate subtitles. Check the output above for errors."
    exit 1
fi
