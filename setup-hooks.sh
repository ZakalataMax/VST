#!/bin/sh
set -e
cd "$(dirname "$0")"
git config core.hooksPath .githooks
chmod +x .githooks/pre-push
echo "Git hooks path set to .githooks"
echo "pre-push will run backend parser tests before each push."
