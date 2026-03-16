#!/bin/bash

# 1. Validation
if [ "$1" != "capitec-fraud-engine" ]; then
    echo "❌ Usage: ./startup.sh capitec-fraud-engine"
    exit 1
fi

echo "🚀 Initializing Capitec Fraud Engine..."

# 2. Clean and Build
# Using -v ensures the 'Big List' in init.sql is re-applied
echo "🧹 Cleaning old data and rebuilding containers..."
docker-compose down -v
docker-compose up --build -d

echo "⏳ Waiting for engine to be healthy..."

# 3. Health Check Loop
MAX_RETRIES=15
COUNT=0
while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/docs > /dev/null; then
        echo ""
        echo "------------------------------------------------"
        echo "✅ SUCCESS: Capitec Fraud Engine is ONLINE"
        echo "🌐 API Portal:  http://localhost:8000/docs"
        echo "📊 Database:    Postgres (Port 5432)"
        echo "🚫 Logs:        docker logs -f worker-blacklist"
        echo "------------------------------------------------"
        exit 0
    else
        echo -n "."
        sleep 2
        COUNT=$((COUNT+1))
    fi
done

echo -e "\n⚠️  Startup is slow. Check 'docker-compose logs' for details."