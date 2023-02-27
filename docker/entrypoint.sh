#!/bin/bash

# Start logging in background
tail -f /var/log/pasjonsfrukt.log &

echo "Installing crontab..."
crontab -r
crontab /etc/cron.d/pasjonsfrukt-crontab
cat /etc/cron.d/pasjonsfrukt-crontab

echo "Starting cron service..."
cron

echo "Starting server..."
pasjonsfrukt serve "$@"
