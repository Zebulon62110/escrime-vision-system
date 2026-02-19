#!/usr/bin/env bash
set -euo pipefail

# Simple helper to download and run rtsp-simple-server locally (no Docker)
# Usage: ./run_rtsp_server.sh [VERSION]
# Default VERSION can be overridden; change ARCH if needed for your CPU.

VERSION=${1:-v0.19.6}
ARCH=${2:-linux_amd64}
TMPDIR=$(mktemp -d)
DESTDIR="$(pwd)/tools/rtsp-simple-server"
LOGDIR="$(pwd)/logs"

echo "Using version: $VERSION, arch: $ARCH"
URL="https://github.com/aler9/rtsp-simple-server/releases/download/${VERSION}/rtsp-simple-server_${VERSION}_${ARCH}.tar.gz"

mkdir -p "$DESTDIR" "$LOGDIR"
echo "Attempting download: $URL..."
if ! curl -fL "$URL" -o "$TMPDIR/rtsp.tar.gz"; then
  echo "Direct download failed — querying GitHub API for latest release..."
  ASSET_URL=$(curl -sL https://api.github.com/repos/aler9/rtsp-simple-server/releases/latest | grep "browser_download_url" | grep "linux_amd64" | head -n1 | cut -d '"' -f4 || true)
  if [ -z "$ASSET_URL" ]; then
    echo "Could not determine latest asset URL from GitHub API. Please provide a valid VERSION or check network."
    exit 1
  fi
  echo "Found asset: $ASSET_URL"
  curl -fL "$ASSET_URL" -o "$TMPDIR/rtsp.tar.gz"
fi
echo "Extracting..."
tar -xzf "$TMPDIR/rtsp.tar.gz" -C "$TMPDIR"
# find the binary inside extracted dir
BINPATH=$(find "$TMPDIR" -type f -perm /111 -print -quit)
if [ -z "$BINPATH" ]; then
  echo "No executable binary found in archive"
  exit 1
fi
echo "Found binary: $BINPATH"
cp "$BINPATH" "$DESTDIR/rtsp-simple-server"
chmod +x "$DESTDIR/rtsp-simple-server"

echo "Starting rtsp-simple-server (logs: $LOGDIR/rtsp.log)"
nohup "$DESTDIR/rtsp-simple-server" > "$LOGDIR/rtsp.log" 2>&1 &
echo $! > "$LOGDIR/rtsp.pid"
echo "rtsp-simple-server started with PID $(cat $LOGDIR/rtsp.pid)"

echo "Tail last 10 log lines:"
tail -n 10 "$LOGDIR/rtsp.log" || true
