#!/bin/bash
# Run from project root
export PYTHONPATH=$PYTHONPATH:$(pwd)
echo "Starting Backend Server..."
python -m backend.app.main
