#!/bin/bash
set -e

cd /home/site/repository

echo "Using Python:"
which python

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd worker

echo "Starting worker..."
python worker.py 