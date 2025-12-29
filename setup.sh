#!/bin/bash
# Setup script for Strava Kudos Bot

echo "🚀 Setting up Strava Kudos Bot..."
echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Python dependencies"
    exit 1
fi

echo "✓ Python dependencies installed"
echo ""

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium chrome

if [ $? -ne 0 ]; then
    echo "❌ Failed to install Playwright browsers"
    exit 1
fi

echo "✓ Playwright Chromium browser installed"
echo ""

echo ""
echo "✅ Setup complete!"
