#!/usr/bin/env bash
# Oracle reclaims Always Free instances idle for 7 days (95th-percentile CPU under 20%).
# This burns a short, deliberate burst of CPU every 20 minutes to stay above that line.
# Install:  crontab -e   →   */20 * * * * /home/ubuntu/dogar-api/keepalive.sh

curl -fsS http://localhost/api/health > /dev/null 2>&1

# ~45 seconds of load on both cores
for i in 1 2; do
  timeout 45 sh -c 'while :; do :; done' &
done
wait
