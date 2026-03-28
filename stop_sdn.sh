#!/bin/bash

# stop_sdn.sh
# Tears down the remote SDN environment completely.

HOST="192.168.233.141"
USER="test"

echo "Connecting to target to tear down SDN environment..."

ssh -T "$USER@$HOST" << 'EOF'
echo ">>> Killing 'sdn_data' and 'sdn_control' tmux sessions..."
tmux kill-session -t sdn_data 2>/dev/null || true
tmux kill-session -t sdn_control 2>/dev/null || true

echo ">>> Wiping Open vSwitch rules and network namespaces..."
echo test | sudo -S mn -c 2>/dev/null

echo ">>> SDN Environment successfully torn down!"
EOF
