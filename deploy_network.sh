#!/bin/bash

# =================================================================
# SDN Monitor - Automation Pipeline
# Usage: ./deploy_network.sh
# =================================================================

HOST="192.168.233.141"
USER="test"
REMOTE_DIR="/home/test"
SCRIPT_NAME="network_sim.py"

echo "================================================================="
echo "[1/3] Pushing Mininet payload ($SCRIPT_NAME) to $USER@$HOST..."
echo "================================================================="
scp ./$SCRIPT_NAME $USER@$HOST:$REMOTE_DIR/

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================================="
    echo "[2/3] Payload successfully uploaded. Orchestrating Remote Server..."
    echo "================================================================="
    
    ssh -t $USER@$HOST << EOF
        echo ">>> Cleaning previous Mininet environment zombies..."
        sudo mn -c
        
        echo ">>> Destroying any existing 'mininet_sim' tmux sessions..."
        tmux kill-session -t mininet_sim 2>/dev/null || true
        
        echo ">>> Launching $SCRIPT_NAME in a detached tmux session..."
        tmux new-session -d -s mininet_sim 'sudo python3 $REMOTE_DIR/$SCRIPT_NAME'
        
        echo ">>> Remote Configuration Completed!"
        exit
EOF

    echo ""
    echo "================================================================="
    echo "[3/3] Deployment complete."
    echo "The Spine-Leaf Mininet simulation is now running on the target in the background."
    echo "You can monitor the live traffic flow through your FastAPI/React SDN dashboard."
    echo "To view raw Mininet output on the target node, run:"
    echo "    ssh test@192.168.233.141 -t 'tmux attach -t mininet_sim'"
    echo "================================================================="
else
    echo "================================================================="
    echo "ERROR: Failed to SCP $SCRIPT_NAME to the target node."
    echo "Please check your network and SSH configuration."
    echo "================================================================="
    exit 1
fi
