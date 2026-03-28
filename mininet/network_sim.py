#!/usr/bin/env python3
"""
SDN Mininet Simulation - Layer 3 Enterprise Edge Topology (Loop-Free)
Uses a simple tree-like spine-leaf fabric WITHOUT redundant cross-links,
so no STP is needed and Ryu LLDP can discover all links immediately.

Topology:
         r1 (LinuxRouter, 10.0.0.254/8)
          |
         s1 (Spine 1) ─── s2 (Spine 2)
        / |  \\              |
      s3  s4  s5            |
      |   |   |  \\──────────/
    h1,h2 h3,h4 h5,h6

  h_ext (192.168.1.100/24) ─── r1 ─── s1
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch, Node
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time


class LinuxRouter(Node):
    """A Node that acts as an IP router by enabling ip_forward."""
    def config(self, **params):
        super().config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


def create_topology():
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch,
                  link=TCLink, autoSetMacs=True)

    # ── Controller ─────────────────────────────────────────────────────────
    info('*** Adding remote controller (Ryu)\n')
    c0 = net.addController('c0', controller=RemoteController,
                            ip='127.0.0.1', port=6653)

    # ── Spine switches ──────────────────────────────────────────────────────
    info('*** Adding spine switches\n')
    s1 = net.addSwitch('s1', dpid='0000000000000001')
    s2 = net.addSwitch('s2', dpid='0000000000000002')

    # ── Leaf switches ───────────────────────────────────────────────────────
    info('*** Adding leaf switches\n')
    s3 = net.addSwitch('s3', dpid='0000000000000003')
    s4 = net.addSwitch('s4', dpid='0000000000000004')
    s5 = net.addSwitch('s5', dpid='0000000000000005')

    # ── Internal hosts ──────────────────────────────────────────────────────
    info('*** Adding internal hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1/8', defaultRoute='via 10.0.0.254')
    h2 = net.addHost('h2', ip='10.0.0.2/8', defaultRoute='via 10.0.0.254')
    h3 = net.addHost('h3', ip='10.0.0.3/8', defaultRoute='via 10.0.0.254')
    h4 = net.addHost('h4', ip='10.0.0.4/8', defaultRoute='via 10.0.0.254')
    h5 = net.addHost('h5', ip='10.0.0.5/8', defaultRoute='via 10.0.0.254')
    h6 = net.addHost('h6', ip='10.0.0.6/8', defaultRoute='via 10.0.0.254')

    # ── Linux Layer-3 Router ────────────────────────────────────────────────
    info('*** Adding Linux router r1\n')
    r1 = net.addHost('r1', cls=LinuxRouter, ip='10.0.0.254/8')

    # ── External WAN host ───────────────────────────────────────────────────
    info('*** Adding WAN host h_ext\n')
    h_ext = net.addHost('h_ext', ip='192.168.1.100/24',
                         defaultRoute='via 192.168.1.1')

    # ── Spine <-> Spine link ────────────────────────────────────────────────
    info('*** Wiring spine interconnect\n')
    net.addLink(s1, s2)

    # ── Leaf <-> Spine links (each leaf to ONE spine to stay loop-free) ────
    info('*** Wiring leaves to spines\n')
    net.addLink(s3, s1)
    net.addLink(s4, s1)
    net.addLink(s5, s2)

    # ── Host <-> Leaf links ─────────────────────────────────────────────────
    info('*** Wiring hosts to leaves\n')
    net.addLink(h1, s3)
    net.addLink(h2, s3)
    net.addLink(h3, s4)
    net.addLink(h4, s4)
    net.addLink(h5, s5)
    net.addLink(h6, s5)

    # ── Router uplink into fabric ───────────────────────────────────────────
    info('*** Wiring r1 uplink to spine s1\n')
    net.addLink(r1, s1, intfName1='r1-eth0')

    # ── WAN link ────────────────────────────────────────────────────────────
    info('*** Wiring WAN: h_ext <-> r1\n')
    net.addLink(h_ext, r1, intfName2='r1-eth1',
                params2={'ip': '192.168.1.1/24'})

    # ── Start network ───────────────────────────────────────────────────────
    info('*** Starting network\n')
    net.build()
    c0.start()
    for sw in [s1, s2, s3, s4, s5]:
        sw.start([c0])

    # Wait for Ryu to install flows (no STP — convergence is near-instant)
    info('*** Waiting 5 seconds for Ryu flow installation...\n')
    time.sleep(5)
    info('*** Network ready - starting traffic\n')

    h1, h2, h3, h4, h5, h6 = net.get('h1', 'h2', 'h3', 'h4', 'h5', 'h6')

    # ── Traffic automation ──────────────────────────────────────────────────
    info('*** [1/4] iperf UDP server on h6\n')
    h6.cmd('iperf -s -u > /dev/null 2>&1 &')

    info('*** [2/4] iperf UDP h1 -> h6 (East-West, 10 Mbps)\n')
    h1.cmd('iperf -c 10.0.0.6 -u -b 10M -t 3600 > /dev/null 2>&1 &')

    info('*** [3/4] ping h2 -> h_ext 192.168.1.100 (North-South WAN)\n')
    h2.cmd('ping 192.168.1.100 -i 0.5 > /tmp/ping_wan.log 2>&1 &')

    info('*** [4/4] ping h3 -> h4 (baseline latency)\n')
    h3.cmd('ping 10.0.0.4 -i 0.5 > /tmp/ping_internal.log 2>&1 &')

    info('*** All traffic generators running. Press Ctrl+C to stop.\n')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        info('\n*** Shutting down...\n')
    finally:
        for host in net.get('h1', 'h2', 'h3', 'h6'):
            host.cmd('killall -9 iperf ping 2>/dev/null')
        net.stop()
        info('*** Stopped cleanly\n')


if __name__ == '__main__':
    setLogLevel('info')
    create_topology()
