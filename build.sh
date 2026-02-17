#!/bin/bash
set -e

echo "Installing aiohttp pre-built wheel to avoid compilation..."
pip install --upgrade pip
pip install aiohttp==3.8.6 --only-binary :all:
pip install -r fastfood_bot/requirements.txt
