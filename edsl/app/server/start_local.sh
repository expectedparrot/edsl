#!/bin/bash

# Start EDSL App Server locally (without Docker)

echo "Starting EDSL App Server..."
echo ""
echo "Make sure you have installed dependencies:"
echo "  pip install 'edsl[services]'"
echo "  cd frontend && npm install"
echo ""

# Start backend in background
echo "Starting backend on http://localhost:8000..."
python server.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "Starting frontend on http://localhost:3000..."
cd frontend && npm run dev

# Cleanup on exit
trap "kill $BACKEND_PID" EXIT
