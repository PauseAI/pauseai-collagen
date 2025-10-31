#!/bin/bash
# Sync git-tracked collagen code to EC2
# Usage: ./tools/sync_to_ec2.sh [--dry-run]

set -e

EC2_HOST="ubuntu@3.85.173.169"
KEY="$HOME/.ssh/collagen-server-key.pem"

# Get list of git-tracked files in relevant directories
FILES=$(git ls-files lib/ scripts/ tools/ schema/)

rsync -avz $1 \
  -e "ssh -i $KEY" \
  --files-from=<(echo "$FILES") \
  ./ \
  "$EC2_HOST:~/collagen/"
