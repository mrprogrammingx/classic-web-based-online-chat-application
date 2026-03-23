#!/usr/bin/env bash
# Usage: ./scripts/add_admin.sh email username password
if [ "$#" -ne 3 ]; then
  echo "usage: $0 email username password"
  exit 1
fi
EMAIL="$1"
USER="$2"
PASS="$3"
python3 scripts/manage_users.py create --email "$EMAIL" --username "$USER" --password "$PASS" --admin
