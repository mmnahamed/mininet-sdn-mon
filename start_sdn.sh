#!/bin/bash

# start_sdn.sh
# Pushes the Mininet topology AND the research Ryu controller to the Ubuntu
# Server, then boots both planes inside dedicated tmux sessions.
#
# Local project layout expected:
#   ./mininet/network_sim.py     ← hybrid topology (replaces old network_sim.py)
#   ./mininet/sdn_controller.py  ← research Ryu app
#
# Remote layout after push:
#   /home/test/network_sim.py
#   /home/test/sdn_controller.py

HOST="192.168.233.141"
USER="test"
REMOTE_DIR="/home/test"

echo "============================================================"
echo "  SDN Research Platform — Deploy & Start"
echo "============================================================"

# ── 1. Push both scripts ──────────────────────────────────────────────────────
echo "[1/3] Uploading scripts to $USER@$HOST…"

scp -q "mininet/network_sim.py"    "$USER@$HOST:$REMOTE_DIR/network_sim.py"
scp -q "mininet/sdn_controller.py" "$USER@$HOST:$REMOTE_DIR/sdn_controller.py"
scp -q "mininet/experiment_runner.py" "$USER@$HOST:$REMOTE_DIR/experiment_runner.py"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to SCP research scripts"
    echo "Check that files exist in ./mininet/ and SSH is configured."
    exit 1
fi

echo "  ✓ network_sim.py    → $REMOTE_DIR/network_sim.py"
echo "  ✓ sdn_controller.py → $REMOTE_DIR/sdn_controller.py"

# ── 2. Prepare remote environment ────────────────────────────────────────────
echo "[2/3] Preparing remote environment…"

# Using 'EOF' (quoted) to prevent local variable expansion inside the heredoc
ssh -T "$USER@$HOST" << 'EOF'

echo "  → Cleaning any existing Mininet state…"
echo test | sudo -S mn -c 2>/dev/null

echo "  → Killing stale tmux sessions (sdn_control, sdn_data)…"
tmux kill-session -t sdn_control 2>/dev/null || true
tmux kill-session -t sdn_data    2>/dev/null || true

echo "  → Creating log directory and clearing ALL stale logs…"
sudo rm -rf /tmp/sdn_logs/*
mkdir -p /tmp/sdn_logs
sudo chmod 777 /tmp/sdn_logs
export TZ_REMOTE=$(cat /etc/timezone)

# ── Boot Control Plane (Ryu) ──────────────────────────────────────────────
# Uses the research controller instead of the stock simple_switch_13.
# ofctl_rest  → /stats/port/<dpid>  (port counters used by the backend)
# rest_topology → /v1.0/topology/*  (switches, links, hosts)
echo "  → Booting Control Plane (Ryu + research controller)…"
tmux new-session -d -s sdn_control \
  "bash -c 'export TZ=$TZ_REMOTE && source ~/ryu-env/bin/activate && \
   ryu-manager \
     /home/test/sdn_controller.py \
     ryu.app.ofctl_rest \
     ryu.app.rest_topology \
   2>&1 | tee /tmp/sdn_logs/controller.log'"

echo "  → Waiting 6 s for Ryu WSGI server to bind…"
sleep 6

# ── Boot Data Plane (Mininet) ─────────────────────────────────────────────
echo "  → Booting Data Plane (Mininet hybrid topology)…"
tmux new-session -d -s sdn_data \
  "bash -c 'export TZ=$TZ_REMOTE && echo test | sudo -S python3 /home/test/network_sim.py \
   2>&1 | tee /tmp/sdn_logs/mininet.log'"

echo "  ✓ Remote SDN environment initialised"
EOF

# ── 3. Done ───────────────────────────────────────────────────────────────────
echo "[3/3] Deployment complete."
echo ""
echo "  Monitor controller : ssh $USER@$HOST -t 'tmux attach -t sdn_control'"
echo "  Monitor topology   : ssh $USER@$HOST -t 'tmux attach -t sdn_data'"
echo "  View logs          : ssh $USER@$HOST 'ls /tmp/sdn_logs/'"
echo ""
echo "  Dashboard (local)  : http://localhost:3000"
echo "============================================================"