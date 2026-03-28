#!/usr/bin/env python3
"""
SDN Experiment Runner
======================
Runs all 5 research scenarios against the live Mininet network and
collects CSV metrics for analysis.

Usage (from inside Mininet CLI or as a standalone script):
  sudo python3 experiment_runner.py

Outputs in /tmp/sdn_logs/:
  scenario_1_baseline.csv
  scenario_2_heavy.csv
  scenario_3_scalability.csv
  scenario_4_multipath.csv
  scenario_5_link_failure.csv
  experiment_summary.json
"""

import subprocess
import time
import os
import csv
import json
import re
import socket
from datetime import datetime

LOG_DIR = "/tmp/sdn_logs"
os.makedirs(LOG_DIR, exist_ok=True)

HOSTS = {
    "h1": "10.0.0.1", "h2": "10.0.0.2", "h3": "10.0.0.3", "h4": "10.0.0.4",
    "h5": "10.0.0.5", "h6": "10.0.0.6", "h7": "10.0.0.7", "h8": "10.0.0.8",
    "h_ext": "192.168.1.100",
}

IPERF_DURATION = 30    # seconds per iperf test
PING_COUNT     = 50    # pings per latency test
RYU_BASE       = "http://127.0.0.1:8080"


# ─── Low-level helpers ─────────────────────────────────────────────────────────

def mn_cmd(host: str, cmd: str, bg: bool = False) -> str:
    """Run a command on a Mininet host via 'mn' API or direct namespace exec."""
    ns_cmd = ["ip", "netns", "exec", host] + cmd.split()
    if bg:
        subprocess.Popen(ns_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ""
    try:
        result = subprocess.run(ns_cmd, capture_output=True, text=True, timeout=60)
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def ryu_get(endpoint: str) -> dict:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{RYU_BASE}{endpoint}", timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return {}


# ─── Metric parsers ────────────────────────────────────────────────────────────

def parse_ping(output: str) -> dict:
    """Extract latency and packet loss from ping output."""
    result = {"min_ms": None, "avg_ms": None, "max_ms": None, "loss_pct": None, "jitter_ms": None}
    loss_m = re.search(r"(\d+)% packet loss", output)
    if loss_m:
        result["loss_pct"] = float(loss_m.group(1))
    rtt_m = re.search(r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", output)
    if rtt_m:
        result["min_ms"]    = float(rtt_m.group(1))
        result["avg_ms"]    = float(rtt_m.group(2))
        result["max_ms"]    = float(rtt_m.group(3))
        result["jitter_ms"] = float(rtt_m.group(4))   # mdev ≈ jitter
    return result


def parse_iperf_udp(output: str) -> dict:
    """Parse iperf UDP output for bandwidth, jitter, loss."""
    result = {"bw_mbps": None, "jitter_ms": None, "loss_pct": None}
    m = re.search(r"([\d.]+) Mbits/sec\s+([\d.]+) ms\s+\d+/\d+ \(([\d.]+)%\)", output)
    if m:
        result["bw_mbps"]    = float(m.group(1))
        result["jitter_ms"]  = float(m.group(2))
        result["loss_pct"]   = float(m.group(3))
    return result


def parse_iperf_tcp(output: str) -> dict:
    """Parse iperf TCP output for bandwidth."""
    result = {"bw_mbps": None}
    m = re.search(r"([\d.]+) Mbits/sec", output)
    if m:
        result["bw_mbps"] = float(m.group(1))
    return result


def save_csv(filename: str, rows: list, headers: list):
    path = os.path.join(LOG_DIR, filename)
    write_header = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(headers)
        w.writerows(rows)
    print(f"  → Saved {len(rows)} rows to {path}")


# ─── Scenario implementations ──────────────────────────────────────────────────

def scenario_1_baseline():
    """Latency, throughput, jitter – same leaf (h1↔h2)."""
    print("\n" + "="*60)
    print("SCENARIO 1: Baseline Performance (h1 ↔ h2, same leaf)")
    print("="*60)
    ts = datetime.utcnow().isoformat()
    rows = []

    # Ping latency
    print("  [1/3] Ping latency h1→h2…")
    out = mn_cmd("h1", f"ping -c {PING_COUNT} -i 0.2 10.0.0.2")
    ping = parse_ping(out)
    with open(f"{LOG_DIR}/s1_ping_raw.txt", "w") as f:
        f.write(out)

    # iperf UDP (jitter + loss)
    print("  [2/3] iperf UDP h1→h2…")
    mn_cmd("h2", "iperf -s -u -D")
    time.sleep(1)
    out_udp = mn_cmd("h1", f"iperf -c 10.0.0.2 -u -b 10M -t {IPERF_DURATION}")
    udp = parse_iperf_udp(out_udp)
    with open(f"{LOG_DIR}/s1_iperf_udp.txt", "w") as f:
        f.write(out_udp)

    # iperf TCP (throughput)
    print("  [3/3] iperf TCP h1→h2…")
    mn_cmd("h2", "iperf -s -D")
    time.sleep(1)
    out_tcp = mn_cmd("h1", f"iperf -c 10.0.0.2 -t {IPERF_DURATION}")
    tcp = parse_iperf_tcp(out_tcp)
    with open(f"{LOG_DIR}/s1_iperf_tcp.txt", "w") as f:
        f.write(out_tcp)

    rows.append([ts, "h1", "h2", "same_leaf",
                 ping["avg_ms"], ping["min_ms"], ping["max_ms"], ping["jitter_ms"], ping["loss_pct"],
                 udp["bw_mbps"], udp["jitter_ms"], udp["loss_pct"],
                 tcp["bw_mbps"]])

    save_csv("scenario_1_baseline.csv", rows, [
        "timestamp","src","dst","path_type",
        "ping_avg_ms","ping_min_ms","ping_max_ms","ping_jitter_ms","ping_loss_pct",
        "udp_bw_mbps","udp_jitter_ms","udp_loss_pct","tcp_bw_mbps"
    ])
    print(f"  Results: ping_avg={ping['avg_ms']}ms  tcp={tcp['bw_mbps']}Mbps  udp_jitter={udp['jitter_ms']}ms")
    return rows


def scenario_2_heavy_traffic():
    """4 parallel TCP streams across topology – stress test."""
    print("\n" + "="*60)
    print("SCENARIO 2: Heavy Traffic Load (4 parallel cross-leaf streams)")
    print("="*60)
    ts = datetime.utcnow().isoformat()
    rows = []
    pairs = [("h1","h5"), ("h2","h6"), ("h3","h7"), ("h4","h8")]

    # Start servers
    for _, dst in pairs:
        mn_cmd(dst, "iperf -s -D")
    time.sleep(1)

    # Launch all clients simultaneously
    print(f"  Launching {len(pairs)} parallel iperf streams for {IPERF_DURATION}s…")
    procs = []
    for src, dst in pairs:
        dst_ip = HOSTS[dst]
        log    = f"{LOG_DIR}/s2_{src}_{dst}.txt"
        p = subprocess.Popen(
            f"ip netns exec {src} iperf -c {dst_ip} -t {IPERF_DURATION} -P 2".split(),
            stdout=open(log, "w"), stderr=subprocess.STDOUT
        )
        procs.append((src, dst, log, p))

    # Wait for completion
    for src, dst, log, p in procs:
        p.wait()
        with open(log) as f:
            out = f.read()
        tcp = parse_iperf_tcp(out)
        rows.append([ts, src, dst, "cross_leaf_heavy", tcp["bw_mbps"]])
        print(f"  {src}→{dst}: {tcp['bw_mbps']} Mbps")

    save_csv("scenario_2_heavy.csv", rows, ["timestamp","src","dst","type","tcp_bw_mbps"])
    return rows


def scenario_3_scalability(host_list=None):
    """Measure latency as we ping from h1 to increasing number of destinations."""
    print("\n" + "="*60)
    print("SCENARIO 3: Scalability (increasing destinations from h1)")
    print("="*60)
    ts = datetime.utcnow().isoformat()
    rows = []
    targets = host_list or ["h2","h3","h4","h5","h6","h7","h8"]

    for i, dst in enumerate(targets, 1):
        dst_ip = HOSTS[dst]
        print(f"  [{i}/{len(targets)}] Ping h1→{dst} ({dst_ip})…")
        out = mn_cmd("h1", f"ping -c 20 -i 0.1 {dst_ip}")
        ping = parse_ping(out)
        rows.append([ts, i, "h1", dst, ping["avg_ms"], ping["jitter_ms"], ping["loss_pct"]])
        print(f"    avg={ping['avg_ms']}ms  jitter={ping['jitter_ms']}ms")

    save_csv("scenario_3_scalability.csv", rows, [
        "timestamp","hop_count","src","dst","ping_avg_ms","jitter_ms","loss_pct"
    ])
    return rows


def scenario_4_multipath():
    """Compare single-path vs multi-path (East-West via s2 or s1)."""
    print("\n" + "="*60)
    print("SCENARIO 4: Multi-Path Routing Comparison (h1→h5)")
    print("="*60)
    ts = datetime.utcnow().isoformat()
    rows = []

    # Run 3 rounds to check path stability / variation
    mn_cmd("h5", "iperf -s -u -D")
    mn_cmd("h5", "iperf -s -D")
    time.sleep(1)

    for run in range(1, 4):
        print(f"  Run {run}/3 – UDP h1→h5 @ 5Mbps…")
        out_udp = mn_cmd("h1", f"iperf -c {HOSTS['h5']} -u -b 5M -t 15")
        udp = parse_iperf_udp(out_udp)
        print(f"    bw={udp['bw_mbps']}Mbps  jitter={udp['jitter_ms']}ms  loss={udp['loss_pct']}%")

        print(f"  Run {run}/3 – TCP h1→h5…")
        out_tcp = mn_cmd("h1", f"iperf -c {HOSTS['h5']} -t 15")
        tcp = parse_iperf_tcp(out_tcp)
        print(f"    bw={tcp['bw_mbps']}Mbps")

        ping = parse_ping(mn_cmd("h1", f"ping -c 20 -i 0.2 {HOSTS['h5']}"))
        rows.append([ts, run, "h1","h5","cross_agg",
                     ping["avg_ms"], ping["jitter_ms"], ping["loss_pct"],
                     udp["bw_mbps"], udp["jitter_ms"], udp["loss_pct"],
                     tcp["bw_mbps"]])
        time.sleep(2)

    save_csv("scenario_4_multipath.csv", rows, [
        "timestamp","run","src","dst","path",
        "ping_avg_ms","ping_jitter_ms","ping_loss_pct",
        "udp_bw_mbps","udp_jitter_ms","udp_loss_pct","tcp_bw_mbps"
    ])
    return rows


def scenario_5_link_failure():
    """Detect rerouting latency when the s1-s2 link is taken down."""
    print("\n" + "="*60)
    print("SCENARIO 5: Link Failure & Recovery (s1↔s2)")
    print("="*60)
    ts = datetime.utcnow().isoformat()
    rows = []

    def _ping_sample(label):
        out = mn_cmd("h1", f"ping -c 10 -i 0.2 {HOSTS['h5']}")
        p = parse_ping(out)
        rows.append([ts, label, p["avg_ms"], p["loss_pct"], p["jitter_ms"]])
        print(f"  [{label}] avg={p['avg_ms']}ms  loss={p['loss_pct']}%")
        return p

    print("  Pre-failure baseline ping h1→h5…")
    pre = _ping_sample("pre_failure")

    print("  Simulating link failure: s1-eth1 (s1↔s2) DOWN…")
    subprocess.run("ip link set s1-eth1 down".split(), stderr=subprocess.DEVNULL)
    time.sleep(2)   # allow controller to react

    print("  Post-failure ping h1→h5 (traffic re-routes via s2↔s3)…")
    post = _ping_sample("post_failure")

    print("  Restoring link s1↔s2…")
    subprocess.run("ip link set s1-eth1 up".split(), stderr=subprocess.DEVNULL)
    time.sleep(3)

    print("  Recovery ping h1→h5…")
    rec = _ping_sample("post_recovery")

    save_csv("scenario_5_link_failure.csv", rows, [
        "timestamp","phase","ping_avg_ms","loss_pct","jitter_ms"
    ])
    degradation = None
    if pre["avg_ms"] and post["avg_ms"]:
        degradation = round(post["avg_ms"] - pre["avg_ms"], 2)
    print(f"  Latency degradation during failure: {degradation}ms")
    return rows


# ─── Summary ───────────────────────────────────────────────────────────────────

def collect_controller_snapshot():
    """Pull a summary from the Ryu REST API."""
    summary = ryu_get("/api/stats/summary")
    topo_sw = ryu_get("/v1.0/topology/switches")
    n_links = ryu_get("/v1.0/topology/links")
    return {
        "switches": len(topo_sw) if isinstance(topo_sw, list) else 0,
        "links":    len(n_links) if isinstance(n_links, list) else 0,
        "flows_installed": summary.get("flows_installed", "N/A"),
        "rps": summary.get("requests_per_sec", "N/A"),
    }


def run_all():
    print("\n" + "★"*60)
    print("  SDN Research – Full Experiment Suite")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("★"*60)

    summary = {"start": datetime.utcnow().isoformat(), "scenarios": {}}

    s1 = scenario_1_baseline()
    summary["scenarios"]["1_baseline"] = len(s1)

    s2 = scenario_2_heavy_traffic()
    summary["scenarios"]["2_heavy"] = len(s2)

    s3 = scenario_3_scalability()
    summary["scenarios"]["3_scalability"] = len(s3)

    s4 = scenario_4_multipath()
    summary["scenarios"]["4_multipath"] = len(s4)

    s5 = scenario_5_link_failure()
    summary["scenarios"]["5_link_failure"] = len(s5)

    summary["controller"] = collect_controller_snapshot()
    summary["end"] = datetime.utcnow().isoformat()

    out_path = f"{LOG_DIR}/experiment_summary.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "="*60)
    print(f"All experiments complete! Summary: {out_path}")
    print(f"CSV results in: {LOG_DIR}/")
    print("="*60)
    return summary


if __name__ == "__main__":
    import sys
    setLogLevel("info")
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        summary = {"start": datetime.utcnow().isoformat(), "scenarios": {}}
        if arg == "1": scenario_1_baseline()
        elif arg == "2": scenario_2_heavy_traffic()
        elif arg == "3": scenario_3_scalability()
        elif arg == "4": scenario_4_multipath()
        elif arg == "5": scenario_5_link_failure()
        else:
            print(f"Unknown scenario: {arg}")
            sys.exit(1)
    else:
        run_all()