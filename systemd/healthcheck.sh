#!/bin/bash
# Health check for abfahrt.service
# Called by abfahrt-watchdog.timer every 60 seconds.

SERVICE="abfahrt.service"

if ! systemctl is-active --quiet "$SERVICE"; then
    logger -t abfahrt-watchdog "$SERVICE is not active, restarting..."
    systemctl restart "$SERVICE"
    logger -t abfahrt-watchdog "$SERVICE restarted"
fi
