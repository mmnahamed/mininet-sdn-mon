# Mininet SDN Monitor (mininet-sdn-mon)

A lightweight Software-Defined Networking (SDN) monitoring framework built on top of [Mininet](http://mininet.org/). This project provides real-time network topology emulation and traffic monitoring, allowing researchers and developers to extract network statistics, observe traffic flows, and manage OpenFlow switches dynamically.

## Features

* **Custom Topology Emulation:** Easily deploy tree, linear, or custom network topologies using Mininet.
* **Traffic Monitoring & Statistics:** Periodically poll OpenFlow switches for port statistics, flow entries, and bandwidth utilization.
* **SDN Controller Integration:** Compatible with popular SDN controllers (e.g., Ryu, POX, ONOS, OpenDaylight).
* **Automated Traffic Generation:** Built-in scripts to generate background traffic (ICMP, TCP, UDP) using tools like `iperf` and `ping`.
* **Logging & Exporting:** Log network metrics for analysis, graphing, or exporting to time-series databases.

## Prerequisites

Before running this project, ensure you have the following installed on your Linux environment (Ubuntu 20.04/22.04 recommended):

* **Python 3.x**
* **Mininet** (`sudo apt-get install mininet`)
* **Open vSwitch** (`sudo apt-get install openvswitch-switch`)
* **SDN Controller** (e.g., Ryu: `pip install ryu`)
* **xterm** (optional, for Mininet CLI windows)
  
##  Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/mmnahamed/mininet-sdn-mon.git](https://github.com/mmnahamed/mininet-sdn-mon.git)
   cd mininet-sdn-mon

Install dependencies:
```bash
pip3 install -r requirements.txt
sudo mn --test pingall
```
   
1. Start the Remote SDN Environment
Run the setup script from your workspace. This will securely SSH into the target node, start the Ryu controller, and launch your Mininet data plane.

```bash
cd /home/shaan/sdn-mininet-mon
./start_sdn.sh
```
##  Usage

2. Start the Monitoring Platform (Local)
You'll need two separate terminal windows on your local Ubuntu desktop.

Terminal 1 (Backend API):

```bash
cd /home/shaan/sdn-mininet-mon/backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

Terminal 2 (Frontend UI):

```bash
cd /home/shaan/sdn-mininet-mon/frontend
npm run dev
You can now open your browser and navigate to http://localhost:3000 to view the dashboard!
```
------------------------------------------------------------------------------------

3. Stop the Remote SDN Environment
When you are done testing, you must run the teardown script. This kills the background Ryu and Mininet processes and securely runs sudo mn -c to wipe out the network namespaces to prevent corruption on your next run.

```bash
cd /home/shaan/sdn-mininet-mon
./stop_sdn.sh
```

4. Stop the Monitoring Platform (Local)
Go to Terminal 1 and Terminal 2 and simply press Ctrl + C to stop the Python backend and the React development server.
