# Systemd Setup (Raspberry Pi)

## Install

```bash
cd /home/pi/abfahrt
pip install -e ".[hardware]"
```

## Deploy service files

```bash
sudo cp systemd/abfahrt.service /etc/systemd/system/
sudo cp systemd/abfahrt-watchdog.service /etc/systemd/system/
sudo cp systemd/abfahrt-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

## Enable and start

```bash
# Main service (auto-start on boot)
sudo systemctl enable abfahrt.service
sudo systemctl start abfahrt.service

# Health check timer (restarts service if it dies)
sudo systemctl enable abfahrt-watchdog.timer
sudo systemctl start abfahrt-watchdog.timer
```

## Check status

```bash
sudo systemctl status abfahrt.service
sudo systemctl list-timers abfahrt-watchdog.timer
```

## View logs

```bash
# Follow live logs
journalctl -u abfahrt.service -f

# Last 100 lines
journalctl -u abfahrt.service -n 100

# Watchdog logs
journalctl -t abfahrt-watchdog
```

## Stop / restart

```bash
sudo systemctl stop abfahrt.service
sudo systemctl restart abfahrt.service
```
