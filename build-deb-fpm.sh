#!/bin/bash
set -e

# Tank Monitoring - Debian Package Builder with FPM
# Creates a .deb package for Raspberry Pi installation

VERSION="0.1.0"
ARCH="arm64"  # for RPI 64-bit (Debian Bookworm), or "armhf" for 32-bit
PACKAGE_NAME="tank-monitoring"

echo "=== Tank Monitoring Debian Package Builder (FPM) ==="
echo "Version: $VERSION"
echo "Architecture: $ARCH"
echo ""

# Check if fpm is installed
if ! command -v fpm &> /dev/null; then
    echo "ERROR: fpm is not installed!"
    echo ""
    echo "Installation:"
    echo "  sudo apt-get install ruby ruby-dev rubygems build-essential"
    echo "  sudo gem install --no-document fpm"
    echo ""
    exit 1
fi

# Cleanup
rm -rf build-fpm
mkdir -p build-fpm

# Create temporary directory structure
echo "Creating temporary structure..."
STAGING="build-fpm/staging"
mkdir -p "$STAGING/opt/tank"
mkdir -p "$STAGING/etc/systemd/system"
mkdir -p "$STAGING/etc/tank"
mkdir -p "$STAGING/usr/bin"

# Copy application files
echo "Copying application files..."
rsync -av --exclude='.git' \
          --exclude='__pycache__' \
          --exclude='*.pyc' \
          --exclude='.venv' \
          --exclude='build' \
          --exclude='build-fpm' \
          --exclude='*.deb' \
          --exclude='*.db' \
          --exclude='*.png' \
          --exclude='output' \
          --exclude='dev_data' \
          rpi/ "$STAGING/opt/tank/rpi/"

# Create systemd service files
echo "Creating systemd services..."

# Tank Subscriber Service
cat > "$STAGING/etc/systemd/system/tank-subscriber.service" << 'EOF'
[Unit]
Description=Tank MQTT Subscriber
After=network.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
User=tank
WorkingDirectory=/opt/tank/rpi/src
ExecStartPre=/usr/bin/mkdir -p /opt/tank/rpi/db
ExecStart=/opt/tank/rpi/.venv/bin/python3 run_subscriber.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Tank Telegram Service
cat > "$STAGING/etc/systemd/system/tank-telegram.service" << 'EOF'
[Unit]
Description=Tank Telegram Bot
After=network.target tank-subscriber.service
Wants=tank-subscriber.service

[Service]
Type=simple
User=tank
WorkingDirectory=/opt/tank/rpi/src
ExecStartPre=/usr/bin/mkdir -p /opt/tank/rpi/db
ExecStartPre=/usr/bin/mkdir -p /opt/tank/rpi/output/telegram
ExecStart=/opt/tank/rpi/.venv/bin/python3 run_telegram_bot.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Tank Dashboard Service
cat > "$STAGING/etc/systemd/system/tank-dashboard.service" << 'EOF'
[Unit]
Description=Tank Dashboard
After=network.target

[Service]
Type=simple
User=tank
WorkingDirectory=/opt/tank/rpi/src
ExecStart=/opt/tank/rpi/.venv/bin/python3 run_dashboard.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF


# Helper script to manage services
cat > "$STAGING/usr/bin/tank-ctl" << 'EOF'
#!/bin/bash
# Tank Monitoring Control Script

case "$1" in
    start)
        sudo systemctl start tank-subscriber tank-telegram
        echo "✓ Tank services started"
        ;;
    stop)
        sudo systemctl stop tank-subscriber tank-telegram tank-dashboard
        echo "✓ Tank services stopped"
        ;;
    restart)
        sudo systemctl restart tank-subscriber tank-telegram
        echo "✓ Tank services restarted"
        ;;
    status)
        echo "=== Tank Services Status ==="
        sudo systemctl status tank-subscriber --no-pager -l
        echo ""
        sudo systemctl status tank-telegram --no-pager -l
        echo ""
        sudo systemctl status tank-dashboard --no-pager -l
        ;;
    logs)
        case "$2" in
            mqtt|subscriber)
                sudo journalctl -u tank-subscriber -f
                ;;
            bot|telegram)
                sudo journalctl -u tank-telegram -f
                ;;
            dashboard|dash)
                sudo journalctl -u tank-dashboard -f
                ;;
            *)
                echo "Available logs: mqtt, bot, dashboard"
                echo "Example: tank-ctl logs mqtt"
                ;;
        esac
        ;;
    enable)
        sudo systemctl enable tank-subscriber tank-telegram
        echo "✓ Tank services enabled (autostart)"
        ;;
    disable)
        sudo systemctl disable tank-subscriber tank-telegram tank-dashboard
        echo "✓ Tank services disabled"
        ;;
    *)
        echo "Tank Monitoring Control"
        echo ""
        echo "Usage: tank-ctl {start|stop|restart|status|logs|enable|disable}"
        echo ""
        echo "Commands:"
        echo "  start       - Start all services"
        echo "  stop        - Stop all services"
        echo "  restart     - Restart all services"
        echo "  status      - Show status of all services"
        echo "  logs <srv>  - Show logs (mqtt|bot|dashboard)"
        echo "  enable      - Enable autostart"
        echo "  disable     - Disable autostart"
        echo ""
        echo "Examples:"
        echo "  tank-ctl start"
        echo "  tank-ctl status"
        echo "  tank-ctl logs mqtt"
        exit 1
        ;;
esac
EOF

chmod 755 "$STAGING/usr/bin/tank-ctl"

# Create post-install script
cat > build-fpm/postinst.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Tank Monitoring - Post Installation ==="

# Create user if not exists
if ! id -u tank >/dev/null 2>&1; then
    echo "Creating user 'tank'..."
    useradd -r -s /bin/bash -d /opt/tank -m tank
fi

# Create directories
mkdir -p /opt/tank/rpi/db
mkdir -p /opt/tank/rpi/output/telegram
chown -R tank:tank /opt/tank

# Create Python venv
if [ ! -d /opt/tank/rpi/.venv ]; then
    echo "Creating Python Virtual Environment..."
    cd /opt/tank/rpi
    sudo -u tank python3 -m venv .venv
    sudo -u tank .venv/bin/pip install --upgrade pip

    # Install dependencies
    if [ -f requirements.txt ]; then
        echo "Installing Python dependencies..."
        sudo -u tank .venv/bin/pip install -r requirements.txt
    fi
fi

# Register systemd services
echo "Registering systemd services..."
systemctl daemon-reload

# Do NOT automatically start services
# User must first adjust configuration
echo ""
echo "✓ Installation complete!"
echo ""
echo "IMPORTANT: Configuration required!"
echo "========================================="
echo ""
echo "1. Configure Telegram Bot:"
echo "   sudo nano /etc/tank/bot.conf"
echo "   Add:"
echo "     TELEGRAM_BOT_TOKEN=your-bot-token"
echo "     TELEGRAM_MY_ID=your-telegram-user-id"
echo ""
echo "2. Enable and start services:"
echo "   sudo systemctl enable tank-subscriber"
echo "   sudo systemctl enable tank-telegram"
echo "   sudo systemctl enable tank-dashboard  # optional"
echo ""
echo "   sudo systemctl start tank-subscriber"
echo "   sudo systemctl start tank-telegram"
echo "   sudo systemctl start tank-dashboard"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status tank-subscriber"
echo "   sudo systemctl status tank-telegram"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u tank-subscriber -f"
echo "   sudo journalctl -u tank-telegram -f"
echo ""

exit 0
EOF

# Create pre-remove script
cat > build-fpm/prerm.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Tank Monitoring - Uninstallation ==="

# Stop services
systemctl stop tank-subscriber || true
systemctl stop tank-telegram || true
systemctl stop tank-dashboard || true

# Disable services
systemctl disable tank-subscriber || true
systemctl disable tank-telegram || true
systemctl disable tank-dashboard || true

exit 0
EOF

# Create post-remove script
cat > build-fpm/postrm.sh << 'EOF'
#!/bin/bash
set -e

if [ "$1" = "purge" ]; then
    echo "=== Tank Monitoring - Purge ==="

    # Do NOT delete user (keep data)
    # rm -rf /opt/tank  # Optional: uncomment for complete removal

    echo "Database and configuration kept in /opt/tank"
    echo "For complete removal: sudo rm -rf /opt/tank"
fi

exit 0
EOF

chmod 755 build-fpm/*.sh

# Build package with FPM
echo ""
echo "Building Debian package with FPM..."
fpm -s dir -t deb \
    -n "$PACKAGE_NAME" \
    -v "$VERSION" \
    -a "$ARCH" \
    --description "Tank Monitoring System with Telegram Bot
Monitors heating temperatures and tank levels.
Sends alarms via Telegram Bot for critical values.

Includes:
 - MQTT Subscriber for sensor data
 - Telegram Bot for notifications
 - Web Dashboard for visualization" \
    --maintainer "Tank Team <tank@example.com>" \
    --url "https://github.com/your-repo/tank" \
    --license "MIT" \
    --vendor "Tank Team" \
    --category "utils" \
    --depends "python3 >= 3.9" \
    --depends "python3-pip" \
    --depends "python3-venv" \
    --depends "mosquitto" \
    --after-install build-fpm/postinst.sh \
    --before-remove build-fpm/prerm.sh \
    --after-remove build-fpm/postrm.sh \
    --deb-no-default-config-files \
    -C "$STAGING" \
    .

echo ""
echo "=== ✓ Package created ==="
echo "File: ${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
echo ""
echo "Installation:"
echo "  sudo dpkg -i ${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
echo "  sudo apt-get install -f  # If dependencies are missing"
echo ""
echo "Uninstallation:"
echo "  sudo dpkg -r $PACKAGE_NAME"
echo ""
echo "Complete removal (including data):"
echo "  sudo dpkg --purge $PACKAGE_NAME"
echo "  sudo rm -rf /opt/tank"
echo ""
