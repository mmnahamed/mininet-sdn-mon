#!/usr/bin/env python3
"""
SDN Research — Hybrid Topology (network_sim.py)
=================================================
A single topology that covers all four study types:

  Single Switch  → s1 acts as the sole core spine (isolated scenario)
  Linear         → s1 — s2 — s3 spine chain
  Fat-Tree/Tree  → dual-aggregation (s2,s3) + 4 leaf switches (s4-s7)
  Multi-Path     → s2 ↔ s3 cross-link enables ECMP / alternate routing

Full layout:

                         [h_ext]  192.168.1.100/24
                            |  (WAN: 10 Mbps, 20 ms delay, 0.5% loss)
                           [r1]  LinuxRouter
                            |  r1-eth0 → s1  (100 Mbps, 10 ms)
               ┌────────[s1 CORE SPINE]────────┐
               │         dpid=0001              │
           [s2 AGG-W]                       [s3 AGG-E]
            dpid=0002                        dpid=0003
            /       \          ←cross→       /       \
       [s4 Leaf]  [s5 Leaf]            [s6 Leaf]  [s7 Leaf]
        dpid=4     dpid=5               dpid=6     dpid=7
        /   \       /   \               /   \       /   \
       h1   h2    h3   h4             h5   h6    h7   h8

Link bandwidths (TCLink):
  Spine ↔ Aggregation : 1000 Mbps, 1 ms
  Cross  s2 ↔ s3      :  100 Mbps, 1 ms   ← multi-path / ECMP
  Agg  ↔ Leaf         :  100 Mbps, 2 ms
  Leaf ↔ Host         :   10 Mbps, 5 ms
  Router uplink       :  100 Mbps, 10 ms
  WAN  h_ext ↔ r1     :   10 Mbps, 20 ms, 0.5% loss

Scenario coverage:
  Baseline    : h1 ↔ h2  (same leaf, intra-rack)
  East-West   : h1 ↔ h5  (cross agg, two possible paths via s1 or s2↔s3)
  North-South : h1 ↔ h_ext (via r1, WAN path)
  Heavy load  : all 4 leaf-pairs simultaneously
  Link failure: s1-s2 down → traffic re-routes through s2↔s3↔s3
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch, Node
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time
import os

LOG_DIR = "/tmp/sdn_logs"
os.makedirs(LOG_DIR, exist_ok=True)

CONTROLLER_IP   = "127.0.0.1"
CONTROLLER_PORT = 6653


class LinuxRouter(Node):
    """A Mininet host with IP forwarding — acts as a Layer-3 router."""

    def config(self, **params):
        super().config(**params)
        self.cmd("sysctl -w net.ipv4.ip_forward=1")

    def terminate(self):
        self.cmd("sysctl -w net.ipv4.ip_forward=0")
        super().terminate()


def create_topology():
    net = Mininet(
        controller=RemoteController,
        switch=OVSKernelSwitch,
        link=TCLink,
        autoSetMacs=True,
    )

    # ── Controller ────────────────────────────────────────────────────────────
    info("*** Adding Ryu remote controller\n")
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip=CONTROLLER_IP,
        port=CONTROLLER_PORT,
    )

    # ── Spine (core) ──────────────────────────────────────────────────────────
    info("*** Adding core spine: s1\n")
    s1 = net.addSwitch("s1", dpid="0000000000000001")

    # ── Aggregation ───────────────────────────────────────────────────────────
    info("*** Adding aggregation switches: s2, s3\n")
    s2 = net.addSwitch("s2", dpid="0000000000000002")
    s3 = net.addSwitch("s3", dpid="0000000000000003")

    # ── Leaf ──────────────────────────────────────────────────────────────────
    info("*** Adding leaf switches: s4-s7\n")
    s4 = net.addSwitch("s4", dpid="0000000000000004")
    s5 = net.addSwitch("s5", dpid="0000000000000005")
    s6 = net.addSwitch("s6", dpid="0000000000000006")
    s7 = net.addSwitch("s7", dpid="0000000000000007")

    # ── Internal hosts ────────────────────────────────────────────────────────
    info("*** Adding internal hosts: h1-h8\n")
    h1 = net.addHost("h1", ip="10.0.0.1/8", defaultRoute="via 10.0.0.254")
    h2 = net.addHost("h2", ip="10.0.0.2/8", defaultRoute="via 10.0.0.254")
    h3 = net.addHost("h3", ip="10.0.0.3/8", defaultRoute="via 10.0.0.254")
    h4 = net.addHost("h4", ip="10.0.0.4/8", defaultRoute="via 10.0.0.254")
    h5 = net.addHost("h5", ip="10.0.0.5/8", defaultRoute="via 10.0.0.254")
    h6 = net.addHost("h6", ip="10.0.0.6/8", defaultRoute="via 10.0.0.254")
    h7 = net.addHost("h7", ip="10.0.0.7/8", defaultRoute="via 10.0.0.254")
    h8 = net.addHost("h8", ip="10.0.0.8/8", defaultRoute="via 10.0.0.254")

    # ── Router + WAN host ─────────────────────────────────────────────────────
    info("*** Adding Linux router r1\n")
    r1 = net.addHost("r1", cls=LinuxRouter, ip="10.0.0.254/8")

    info("*** Adding WAN host h_ext\n")
    h_ext = net.addHost(
        "h_ext",
        ip="192.168.1.100/24",
        defaultRoute="via 192.168.1.1",
    )

    # ── Links: Spine ↔ Aggregation (1 Gbps) ──────────────────────────────────
    info("*** Wiring spine ↔ aggregation\n")
    net.addLink(s1, s2, bw=1000, delay="1ms", loss=0)
    net.addLink(s1, s3, bw=1000, delay="1ms", loss=0)

    # ── Link: Cross-aggregation s2 ↔ s3  (multi-path) ────────────────────────
    # info("*** Wiring cross-agg link s2 ↔ s3 (multi-path)\n")
    # net.addLink(s2, s3, bw=100, delay="1ms", loss=0)

    # ── Links: Aggregation ↔ Leaf (100 Mbps) ─────────────────────────────────
    info("*** Wiring aggregation ↔ leaf\n")
    net.addLink(s2, s4, bw=100, delay="2ms", loss=0)
    net.addLink(s2, s5, bw=100, delay="2ms", loss=0)
    net.addLink(s3, s6, bw=100, delay="2ms", loss=0)
    net.addLink(s3, s7, bw=100, delay="2ms", loss=0)

    # ── Links: Leaf ↔ Host (10 Mbps) ─────────────────────────────────────────
    info("*** Wiring leaf ↔ hosts\n")
    net.addLink(h1, s4, bw=10, delay="5ms", loss=0)
    net.addLink(h2, s4, bw=10, delay="5ms", loss=0)
    net.addLink(h3, s5, bw=10, delay="5ms", loss=0)
    net.addLink(h4, s5, bw=10, delay="5ms", loss=0)
    net.addLink(h5, s6, bw=10, delay="5ms", loss=0)
    net.addLink(h6, s6, bw=10, delay="5ms", loss=0)
    net.addLink(h7, s7, bw=10, delay="5ms", loss=0)
    net.addLink(h8, s7, bw=10, delay="5ms", loss=0)

    # ── Link: Router uplink r1 → s1 (100 Mbps) ───────────────────────────────
    info("*** Wiring router uplink r1 → s1\n")
    net.addLink(r1, s1, intfName1="r1-eth0", bw=100, delay="10ms", loss=0)

    # ── Link: WAN h_ext ↔ r1 (10 Mbps, 20 ms, 0.5% loss) ────────────────────
    info("*** Wiring WAN: h_ext ↔ r1\n")
    net.addLink(
        h_ext, r1,
        intfName2="r1-eth1",
        params2={"ip": "192.168.1.1/24"},
        bw=10, delay="20ms", loss=0.5,
    )

    # ── Start network ─────────────────────────────────────────────────────────
    info("*** Starting network\n")
    net.build()
    c0.start()
    for sw in [s1, s2, s3, s4, s5, s6, s7]:
        sw.start([c0])

    info("*** Waiting 8 s for Ryu flow installation…\n")
    time.sleep(8)

    # ── Background traffic generators ─────────────────────────────────────────
    info("*** Starting background traffic generators\n")

    # iperf servers
    h6.cmd(f"iperf -s -u > {LOG_DIR}/iperf_server_h6.log 2>&1 &")
    h8.cmd(f"iperf -s    > {LOG_DIR}/iperf_server_h8.log 2>&1 &")

    # East-West UDP stream: h1 → h6 @ 5 Mbps  (crosses agg layer)
    h1.cmd(f"iperf -c 10.0.0.6 -u -b 5M -t 3600 > {LOG_DIR}/iperf_h1_h6.log 2>&1 &")

    # East-West TCP stream: h3 → h8  (throughput baseline)
    h3.cmd(f"iperf -c 10.0.0.8 -t 3600 > {LOG_DIR}/iperf_h3_h8.log 2>&1 &")

    # Intra-rack latency baseline: h2 → h5
    h2.cmd(f"ping 10.0.0.5 -i 0.5 > {LOG_DIR}/ping_internal.log 2>&1 &")

    # WAN latency: h1 → h_ext (North-South)
    h1.cmd(f"ping 192.168.1.100 -i 0.5 > {LOG_DIR}/ping_wan.log 2>&1 &")

    info("*** Hybrid topology ready — background traffic running\n")
    info("*** Press Ctrl+C to stop\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        info("\n*** Shutting down…\n")
    finally:
        for host in [h1, h2, h3, h6, h8]:
            host.cmd("killall -9 iperf ping 2>/dev/null")
        net.stop()
        info("*** Stopped cleanly\n")


if __name__ == "__main__":
    setLogLevel("info")
    create_topology()
