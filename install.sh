#!/bin/bash
set -e

# ============================================================
# RGB Matrix Python API Server - Install & Enable systemd Service
# ============================================================
# Run this script with sudo on your Raspberry Pi:
#   sudo bash install.sh
# ============================================================

APP_NAME="rgb-matrix-server"
INSTALL_DIR="/opt/${APP_NAME}"
SERVICE_FILE="${APP_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# --- Pre-flight checks ---
if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo bash install.sh"
fi

info "Starting installation of ${APP_NAME}..."

# --- Install system dependencies ---
info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-dev python3-pip \
    fonts-dejavu-core libopenjp2-7 libtiff6 2>/dev/null || \
apt-get install -y -qq python3 python3-venv python3-dev python3-pip \
    fonts-dejavu-core libopenjp2-7 libtiff5 2>/dev/null || true

# --- Stop existing service if running ---
if systemctl is-active --quiet "${APP_NAME}"; then
    info "Stopping existing ${APP_NAME} service..."
    systemctl stop "${APP_NAME}"
fi

# --- Copy application files ---
info "Copying application files to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
cp "${SCRIPT_DIR}/pi_server.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/weather_service.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/weather_icons.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"

# Copy any other .py files that might exist
for f in "${SCRIPT_DIR}"/*.py; do
    [ -f "$f" ] && cp "$f" "${INSTALL_DIR}/"
done

# --- Create virtual environment ---
if [ ! -d "${INSTALL_DIR}/venv" ]; then
    info "Creating Python virtual environment..."
    python3 -m venv "${INSTALL_DIR}/venv"
else
    info "Virtual environment already exists, reusing..."
fi

# --- Install Python dependencies ---
info "Installing Python dependencies..."
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip -q
"${INSTALL_DIR}/venv/bin/pip" install Pillow requests -q

# Install rgbmatrix - try the real library first, fall back to emulator
if "${INSTALL_DIR}/venv/bin/python3" -c "import rgbmatrix" 2>/dev/null; then
    info "rgbmatrix library already available."
else
    # Check if the C library is installed system-wide
    if python3 -c "import rgbmatrix" 2>/dev/null; then
        info "Linking system rgbmatrix into venv..."
        SYSTEM_SITE=$(python3 -c "import site; print(site.getsitepackages()[0])")
        VENV_SITE=$("${INSTALL_DIR}/venv/bin/python3" -c "import site; print(site.getsitepackages()[0])")
        # Link rgbmatrix .so files
        for f in "${SYSTEM_SITE}"/rgbmatrix*; do
            [ -e "$f" ] && ln -sf "$f" "${VENV_SITE}/"
        done
        info "Linked rgbmatrix into virtual environment."
    else
        warn "rgbmatrix C library not found system-wide."
        warn "You may need to build and install rpi-rgb-led-matrix manually."
        warn "See: https://github.com/hzeller/rpi-rgb-led-matrix"
        warn "Installing RGBMatrixEmulator as fallback..."
        "${INSTALL_DIR}/venv/bin/pip" install RGBMatrixEmulator -q
    fi
fi

# --- Install systemd service ---
info "Installing systemd service..."
cp "${SCRIPT_DIR}/${SERVICE_FILE}" "/etc/systemd/system/${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable "${APP_NAME}"

# --- Start the service ---
info "Starting ${APP_NAME} service..."
systemctl start "${APP_NAME}"

# --- Done ---
echo ""
info "============================================"
info "  Installation complete!"
info "============================================"
echo ""
info "Service status:"
systemctl status "${APP_NAME}" --no-pager -l || true
echo ""
info "Useful commands:"
echo "  sudo systemctl status ${APP_NAME}    # Check status"
echo "  sudo systemctl restart ${APP_NAME}   # Restart"
echo "  sudo systemctl stop ${APP_NAME}      # Stop"
echo "  sudo systemctl start ${APP_NAME}     # Start"
echo "  sudo journalctl -u ${APP_NAME} -f    # View live logs"
echo ""
info "Server is running on http://0.0.0.0:9191"
