#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
import time

def create_topology():
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch, link=TCLink)

    info('*** Adding controller\n')
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    info('*** Adding spine switches\n')
    s1 = net.addSwitch('s1', dpid='0000000000000001')
    s2 = net.addSwitch('s2', dpid='0000000000000002')

    info('*** Adding leaf switches\n')
    s3 = net.addSwitch('s3', dpid='0000000000000003')
    s4 = net.addSwitch('s4', dpid='0000000000000004')
    s5 = net.addSwitch('s5', dpid='0000000000000005')

    info('*** Adding hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1/8')
    h2 = net.addHost('h2', ip='10.0.0.2/8')
    h3 = net.addHost('h3', ip='10.0.0.3/8')
    h4 = net.addHost('h4', ip='10.0.0.4/8')
    h5 = net.addHost('h5', ip='10.0.0.5/8')
    h6 = net.addHost('h6', ip='10.0.0.6/8')

    info('*** Creating links (Leaf to Spine)\n')
    # Connect leaves to both spines
    net.addLink(s3, s1)
    net.addLink(s3, s2)
    net.addLink(s4, s1)
    net.addLink(s4, s2)
    net.addLink(s5, s1)
    net.addLink(s5, s2)

    info('*** Creating links (Hosts to Leaf)\n')
    # Connect hosts to leaves (2 hosts per leaf)
    net.addLink(h1, s3)
    net.addLink(h2, s3)
    net.addLink(h3, s4)
    net.addLink(h4, s4)
    net.addLink(h5, s5)
    net.addLink(h6, s5)

    info('*** Starting network\n')
    net.build()
    c0.start()
    s1.start([c0])
    s2.start([c0])
    s3.start([c0])
    s4.start([c0])
    s5.start([c0])

    info('*** Delaying traffic start to allow convergence\n')
    time.sleep(3)

    info('*** Starting background traffic\n')
    h1, h2, h3, h4, h5, h6 = net.get('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
    
    # iperf setup
    info('*** Starting iperf UDP server on h6\n')
    h6.cmd('iperf -s -u > /dev/null 2>&1 &')
    
    info('*** Starting iperf UDP client on h1 pushing 10M to h6\n')
    # Connect h1 to h6 IP
    h1.cmd('iperf -c 10.0.0.6 -u -b 10M -t 3600 > /dev/null 2>&1 &')

    # Continuous ping loops
    info('*** Starting continuous baseline ping traffic\n')
    h2.cmd('ping 10.0.0.5 -i 0.5 > /dev/null 2>&1 &')
    h3.cmd('ping 10.0.0.4 -i 0.5 > /dev/null 2>&1 &')

    info('*** Network and traffic automated. Press Ctrl+C to stop the simulation.\n')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        info('*** Received KeyboardInterrupt, stopping network...\n')
    finally:
        # Cleanup background processes on hosts to make sure no zombies are left
        info('*** Cleaning up traffic processes\n')
        h1.cmd('killall -9 iperf ping')
        h2.cmd('killall -9 iperf ping')
        h3.cmd('killall -9 iperf ping')
        h6.cmd('killall -9 iperf ping')
        net.stop()
        info('*** Network cleanly stopped\n')

if __name__ == '__main__':
    setLogLevel('info')
    create_topology()
