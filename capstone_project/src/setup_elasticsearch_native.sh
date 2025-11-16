#!/bin/bash
# Setup Elasticsearch without Docker - Native installation via Homebrew

set -e

echo "🔍 Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew is not installed"
    echo ""
    echo "📋 Install Homebrew first:"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

echo "✓ Homebrew is installed"
echo ""

echo "🔍 Checking if Elasticsearch is already installed..."
if brew list elasticsearch &> /dev/null; then
    echo "✓ Elasticsearch is already installed"
    
    # Check if it's running
    if brew services list | grep -q "elasticsearch.*started"; then
        echo "✓ Elasticsearch service is already running"
    else
        echo "Starting Elasticsearch service..."
        brew services start elasticsearch
        echo "✓ Started Elasticsearch service"
    fi
else
    echo "Installing Elasticsearch..."
    brew install elasticsearch
    
    echo "Starting Elasticsearch service..."
    brew services start elasticsearch
    echo "✓ Installed and started Elasticsearch"
fi

echo ""
echo "⏳ Waiting for Elasticsearch to be ready (this may take 10-20 seconds)..."
for i in {1..30}; do
    if curl -s http://localhost:9200 > /dev/null 2>&1; then
        echo "✓ Elasticsearch is ready and responding!"
        
        VERSION=$(curl -s http://localhost:9200 | grep -o '"number":"[^"]*' | cut -d'"' -f4)
        echo "  Version: $VERSION"
        echo ""
        echo "✅ Elasticsearch is ready to use!"
        echo ""
        echo "📍 Connection details:"
        echo "   URL: http://localhost:9200"
        echo "   Index name: sec_filings (will be created when you index documents)"
        echo ""
        echo "💡 To stop Elasticsearch later:"
        echo "   brew services stop elasticsearch"
        echo ""
        exit 0
    fi
    echo "   Waiting... ($i/30)"
    sleep 1
done

echo "⚠️  Elasticsearch started but is not responding yet."
echo "   This is normal - it can take 10-20 seconds to fully start."
echo "   Check status with: brew services list"
echo "   Or test with: curl http://localhost:9200"
exit 1

