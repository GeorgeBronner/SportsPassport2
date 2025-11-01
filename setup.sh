#!/bin/bash

# College Football Game Tracker - Setup Script

set -e

echo "🏈 College Football Game Tracker - Setup"
echo "========================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f backend/.env ]; then
    echo "📝 Creating .env file from template..."
    cp backend/.env.example backend/.env

    # Generate a secure secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)

    # Update the secret key in .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" backend/.env
    else
        # Linux
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" backend/.env
    fi

    echo "✅ Created backend/.env file with generated SECRET_KEY"
    echo "⚠️  Please edit backend/.env and add your CFB_API_KEY if you have one"
    echo ""
else
    echo "✅ backend/.env file already exists"
    echo ""
fi

# Ask if user wants to start the application
read -p "Do you want to start the application now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Building and starting the application..."
    docker-compose up -d

    echo ""
    echo "✅ Application started successfully!"
    echo ""
    echo "📍 API is available at: http://localhost:8000"
    echo "📖 API Documentation: http://localhost:8000/docs"
    echo ""
    echo "Next steps:"
    echo "1. Register a user at http://localhost:8000/docs (POST /api/auth/register)"
    echo "2. Set them as admin by editing the database:"
    echo "   sqlite3 college_football.db"
    echo "   UPDATE users SET is_admin = 1 WHERE email = 'your@email.com';"
    echo "3. Import game data (POST /api/admin/refresh-data?season=2023)"
    echo "4. Start tracking your attended games!"
    echo ""
    echo "To view logs: docker-compose logs -f"
    echo "To stop: docker-compose down"
else
    echo ""
    echo "Setup complete! To start the application later, run:"
    echo "  docker-compose up -d"
fi
