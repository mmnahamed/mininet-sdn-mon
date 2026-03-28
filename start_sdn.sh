#!/bin/bash

# start_sdn.sh
# Automates the deployment of the SDN Control Plane (Ryu) and Data Plane (Mininet)

HOST="192.168.233.141"
USER="test"
REMOTE_DIR="/home/test"
PAYLOAD="mininet/network_sim.py"

echo "Deploying Mininet payload to $USER@$HOST..."
scp -q "./$PAYLOAD" "$USER@$HOST:$REMOTE_DIR/network_sim.py"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to SCP $PAYLOAD to target."
    echo "Please ensure the file exists and SSH is configured."
    exit 1
fi

echo "Payload uploaded. Initiating remote SDN environment..."

# Using 'EOF' to prevent local variable expansion
ssh -T "$USER@$HOST" << 'EOF'
echo ">>> Cleaning existing Mininet instances..."
echo test | sudo -S mn -c 2>/dev/null

echo ">>> Killing any existing 'sdn_control' or 'sdn_data' tmux sessions..."
tmux kill-session -t sdn_control 2>/dev/null || true
tmux kill-session -t sdn_data 2>/dev/null || true

echo ">>> Booting Control Plane (Ryu with simple_switch_13, OFCTL REST, and Topology modules)..."
tmux new-session -d -s sdn_control "bash -c 'source ~/ryu-env/bin/activate && ryu-manager ryu.app.simple_switch_13 ryu.app.ofctl_rest ryu.app.rest_topology'"

echo ">>> Waiting 5 seconds for Ryu WSGI server to bind..."
sleep 5

echo ">>> Booting Data Plane (Mininet Simulation)..."
tmux new-session -d -s sdn_data "echo test | sudo -S python3 /home/test/network_sim.py"

echo ">>> SDN Environment successfully initialized!"
EOF
