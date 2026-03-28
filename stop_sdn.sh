#!/bin/bash

# stop_sdn.sh
# Tears down the remote SDN environment completely:
#   • Kills the sdn_data (Mininet) tmux session
#   • Kills the sdn_control (Ryu) tmux session
#   • Runs sudo mn -c to wipe OVS state and network namespaces

HOST="192.168.233.141"
USER="test"

echo "============================================================"
echo "  SDN Research Platform — Teardown"
echo "============================================================"

echo "Connecting to $USER@$HOST to tear down…"

ssh -T "$USER@$HOST" << 'EOF'

echo "  → Stopping Mininet (sdn_data)…"
tmux kill-session -t sdn_data    2>/dev/null || true

echo "  → Stopping Ryu controller (sdn_control)…"
tmux kill-session -t sdn_control 2>/dev/null || true

echo "  → Wiping OVS rules and network namespaces (sudo mn -c)…"
echo test | sudo -S mn -c 2>/dev/null

echo "  ✓ SDN environment torn down cleanly"
EOF

echo "Done."
echo "============================================================"