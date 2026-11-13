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
