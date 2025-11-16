#!/bin/bash
# Script to set up and start Elasticsearch for the SEC Cybersecurity Agent

set -e

echo "🔍 Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo ""
    echo "📋 Please start Docker Desktop:"
    echo "   1. Open Docker Desktop from Applications"
    echo "   2. Wait for Docker to fully start (whale icon in menu bar should be steady)"
    echo "   3. Run this script again: ./setup_elasticsearch.sh"
    exit 1
fi

echo "✓ Docker is running"
echo ""

echo "🔍 Checking for existing Elasticsearch container..."
EXISTING=$(docker ps -a --filter "name=elasticsearch" --format "{{.Names}}")

if [ -n "$EXISTING" ]; then
    echo "Found existing container: $EXISTING"
    
    # Check if it's running
    if docker ps --filter "name=elasticsearch" --format "{{.Names}}" | grep -q elasticsearch; then
        echo "✓ Elasticsearch container is already running"
    else
        echo "Starting existing container..."
        docker start elasticsearch
        echo "✓ Started existing Elasticsearch container"
    fi
else
    echo "Creating new Elasticsearch container..."
    docker run -d \
        -p 9200:9200 \
        -e 'discovery.type=single-node' \
        -e 'xpack.security.enabled=false' \
        --name elasticsearch \
        elasticsearch:8.11.0
    
    echo "✓ Created and started new Elasticsearch container"
    echo "⏳ Waiting for Elasticsearch to be ready (this may take 10-20 seconds)..."
fi

# Wait for Elasticsearch to be ready
echo ""
echo "🔍 Checking Elasticsearch connection..."
for i in {1..30}; do
    if curl -s http://localhost:9200 > /dev/null 2>&1; then
        echo "✓ Elasticsearch is ready and responding!"
        
        # Test the connection with a simple request
        VERSION=$(curl -s http://localhost:9200 | grep -o '"number":"[^"]*' | cut -d'"' -f4)
        echo "  Version: $VERSION"
        echo ""
        echo "✅ Elasticsearch is ready to use!"
        echo ""
        echo "📍 Connection details:"
        echo "   URL: http://localhost:9200"
        echo "   Index name: sec_filings (will be created when you index documents)"
        echo ""
        exit 0
    fi
    echo "   Waiting... ($i/30)"
    sleep 1
done

echo "⚠️  Elasticsearch container started but is not responding yet."
echo "   This is normal - it can take 10-20 seconds to fully start."
echo "   Run this script again in a few seconds, or check with:"
echo "   curl http://localhost:9200"
exit 1


