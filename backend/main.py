"""
SDN Monitor Backend — main.py (Updated for Hybrid Topology)
=============================================================
Serves:
  GET /api/network/graph    → nodes + links (full hybrid topology)
  GET /api/network/metrics  → per-switch port stats with bps + latency
  GET /api/network/flows    → flow-setup time stats from CSV
  GET /api/network/scenarios → cached experiment scenario results
  GET /api/network/controller → controller efficiency stats
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import asyncio.subprocess
import re
import time
import csv
import os
import json
from pathlib import Path
from collections import defaultdict

app = FastAPI(title="SDN Monitor API — Research Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RYU_BASE_URL = "http://192.168.233.141:8080"
SDN_HOST     = "test@192.168.233.141"
LOG_DIR      = "/tmp/sdn_logs"   # adjust if running locally

# ── SSH Helpers ──────────────────────────────────────────────────────────────
async def _ssh_cat(filename: str) -> str:
    """Fetch a file's content from the remote Mininet host."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4",
            SDN_HOST, f"cat {filename}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8)
        return stdout.decode()
    except Exception:
        return ""

async def _ssh_run(cmd: str, bg: bool = False) -> bool:
    """Run a command on the remote host."""
    final_cmd = f"nohup {cmd} > /tmp/remote_exec.log 2>&1 &" if bg else cmd
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4",
            SDN_HOST, final_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if not bg:
            await asyncio.wait_for(proc.communicate(), timeout=10)
        return True
    except Exception:
        return False

# ── DPID helpers ──────────────────────────────────────────────────────────────
def _dpid_int(dpid_hex: str) -> str:
    try:
        # Ryu DPIDs can be strings or ints, hex or decimal. Handle them robustly.
        if isinstance(dpid_hex, str):
            if dpid_hex.startswith('0x'):
                return str(int(dpid_hex, 16))
            try:
                return str(int(dpid_hex, 16)) # attempt hex
            except ValueError:
                return dpid_hex # assume already decimal string
        return str(dpid_hex)
    except (ValueError, TypeError):
        return str(dpid_hex)


# ── Topology graph ─────────────────────────────────────────────────────────────
@app.get("/api/network/graph")
async def get_network_graph():
    """
    Return graph data for the hybrid topology.
    Switch nodes come from Ryu; hosts from Ryu topology/hosts.
    Router (r1) and WAN host (h_ext) are synthesised via SSH ip-link scrape.
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            sw_res, link_res, host_res = await asyncio.gather(
                client.get(f"{RYU_BASE_URL}/v1.0/topology/switches"),
                client.get(f"{RYU_BASE_URL}/v1.0/topology/links"),
                client.get(f"{RYU_BASE_URL}/v1.0/topology/hosts"),
            )
            switches  = sw_res.json()  if sw_res.status_code  == 200 else []
            ryu_links = link_res.json() if link_res.status_code == 200 else []
            ryu_hosts = host_res.json() if host_res.status_code == 200 else []

        # ── Switch nodes ──────────────────────────────────────────────────────
        switch_roles = {
            "1": ("Core Spine", "spine"),
            "2": ("Agg-West",   "aggregation"),
            "3": ("Agg-East",   "aggregation"),
            "4": ("Leaf-W1",    "leaf"),
            "5": ("Leaf-W2",    "leaf"),
            "6": ("Leaf-E1",    "leaf"),
            "7": ("Leaf-E2",    "leaf"),
        }
        nodes = []
        for s in switches:
            dpid = _dpid_int(s["dpid"])
            role_name, role = switch_roles.get(dpid, (f"Switch {dpid}", "switch"))
            nodes.append({
                "id":    dpid,
                "dpid":  dpid,
                "label": role_name,
                "name":  role_name,
                "type":  "switch",
                "role":  role,
            })

        # ── Host nodes (Mininet h1-h8) from Ryu ──────────────────────────────
        for h in ryu_hosts:
            mac  = h.get("mac", "")
            ipv4 = h.get("ipv4", [])
            ip   = ipv4[0] if ipv4 else mac
            if ip.startswith("33:33") or ip.startswith("fe80"):
                continue
            nodes.append({
                "id":    mac,
                "label": f"Host {ip}",
                "type":  "host",
            })

        # ── Synthesised nodes: r1 + h_ext ────────────────────────────────────
        nodes.append({"id": "r1",    "label": "Router R1",       "type": "router", "dpid": "r1"})
        nodes.append({"id": "h_ext", "label": "WAN (h_ext)",     "type": "host",   "dpid": "h_ext"})

        # ── Links ─────────────────────────────────────────────────────────────
        links = []
        seen  = set()

        # Switch-switch from Ryu LLDP
        for l in ryu_links:
            src_dpid = _dpid_int(l["src"]["dpid"])
            dst_dpid = _dpid_int(l["dst"]["dpid"])
            edge = tuple(sorted([src_dpid, dst_dpid]))
            if edge not in seen:
                seen.add(edge)
                links.append({
                    "source":   src_dpid,
                    "target":   dst_dpid,
                    "src_port": l["src"]["port_no"],
                    "dst_port": l["dst"]["port_no"],
                    "type":     _classify_link(src_dpid, dst_dpid),
                })

        # Host-switch edges from Ryu
        for h in ryu_hosts:
            mac  = h.get("mac", "")
            ipv4 = h.get("ipv4", [])
            ip   = ipv4[0] if ipv4 else mac
            if ip.startswith("33:33") or ip.startswith("fe80"):
                continue
            links.append({
                "source":   mac,
                "target":   _dpid_int(h["port"]["dpid"]),
                "src_port": "eth0",
                "dst_port": h["port"]["port_no"],
                "type":     "edge",
            })

        # Router uplink (s1 → r1) and WAN link (r1 → h_ext) via SSH
        extra_links = await _get_router_links()
        links.extend(extra_links)

        # ── LLDP Fallback for Switch-Switch ──────────────────────────────────
        # If Ryu didn't find any links, we fallback to the known research topology
        # to ensure the dashboard remains functional.
        if not ryu_links:
            static_links = [
                ("1", "2"), ("1", "3"), # Spine-agg
                ("2", "4"), ("2", "5"), # Agg-leaf West
                ("3", "6"), ("3", "7"), # Agg-leaf East
            ]
            for s, d in static_links:
                edge = tuple(sorted([s, d]))
                if edge not in seen:
                    seen.add(edge)
                    links.append({
                        "source":   s,
                        "target":   d,
                        "src_port": "auto",
                        "dst_port": "auto",
                        "type":     _classify_link(s, d)
                    })

        return {"nodes": nodes, "links": links}

    except Exception as e:
        print(f"[graph] error: {e}")
        return {"nodes": [], "links": []}


def _classify_link(a: str, b: str) -> str:
    """Return a link type label based on the hybrid topology structure."""
    spine   = {"1"}
    agg     = {"2", "3"}
    leaf    = {"4", "5", "6", "7"}
    if a in spine and b in agg or b in spine and a in agg:
        return "spine"
    if a in agg and b in leaf or b in agg and a in leaf:
        return "agg_leaf"
    if a in agg and b in agg:
        return "cross_agg"
    return "backbone"


async def _get_router_links() -> list:
    """SSH scrape to detect r1 uplink presence, return synthesised links."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4",
            SDN_HOST, "ip link show",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=7)
        output = stdout.decode()
    except Exception:
        output = ""

    links = []
    # If s1-eth (router uplink port) present → add r1 uplink
    if re.search(r"s1-eth\d+@", output):
        links.append({"source": "1",    "target": "r1",    "src_port": "uplink", "dst_port": "eth0", "type": "uplink"})
    # Always add simulated WAN
    links.append({"source": "r1", "target": "h_ext", "src_port": "eth1", "dst_port": "0", "type": "wan"})
    return links


# ── Port metrics ───────────────────────────────────────────────────────────────

_last_metrics_state = {"time": 0, "data": {}}  # dpid -> port -> rx/tx bytes

@app.get("/api/network/metrics")
async def get_network_metrics():
    global _last_metrics_state
    now = time.time()
    dt  = now - _last_metrics_state["time"]

    async with httpx.AsyncClient(timeout=5) as client:
        try:
            sw_res = await client.get(f"{RYU_BASE_URL}/v1.0/topology/switches")
            if sw_res.status_code != 200:
                return {}
            dpids = [_dpid_int(s["dpid"]) for s in sw_res.json()]

            stats_resps = await asyncio.gather(
                *[client.get(f"{RYU_BASE_URL}/stats/port/{d}") for d in dpids],
                return_exceptions=True,
            )

            result = {
                "switches": {},
                "latency_stats": _latency_cache
            }
            for i, dpid in enumerate(dpids):
                res = stats_resps[i]
                if isinstance(res, Exception) or res.status_code != 200:
                    continue
                ports = list(res.json().values())[0]
                calc  = []
                for p in ports:
                    p_no     = str(p["port_no"])
                    # Skip LOCAL port
                    if p_no == "4294967294" or p_no == "LOCAL": continue

                    rx, tx   = p.get("rx_bytes", 0), p.get("tx_bytes", 0)
                    prev_sw  = _last_metrics_state["data"].get(dpid, {})
                    prev_p   = prev_sw.get(p_no, {"rx": rx, "tx": tx})
                    rx_bps   = max(0, (rx - prev_p["rx"]) * 8 / dt) if dt > 0 else 0
                    tx_bps   = max(0, (tx - prev_p["tx"]) * 8 / dt) if dt > 0 else 0
                    _last_metrics_state["data"].setdefault(dpid, {})[p_no] = {"rx": rx, "tx": tx}

                    # Determine which latency bucket to use
                    # s1 (dpid 1), port 3 is the uplink to r1/WAN
                    is_wan = (dpid == "1" and p_no == "3")
                    lat_src = _latency_cache["wan"] if is_wan else _latency_cache["internal"]

                    calc.append({
                        **p,
                        "rx_bps":    rx_bps,
                        "tx_bps":    tx_bps,
                        "rx_errors": p.get("rx_errors", 0),
                        "tx_errors": p.get("tx_errors", 0),
                        "latency":   lat_src["latency"],
                        "jitter":    lat_src["jitter"],
                    })
                result["switches"][dpid] = calc

            _last_metrics_state["time"] = now
            return result
        except Exception as e:
            print(f"[metrics] error: {e}")
            return {}


# ── Flow setup times ──────────────────────────────────────────────────────────

@app.get("/api/network/flows")
async def get_flow_stats():
    """Return recent flow-setup time samples from the remote controller CSV."""
    path = f"{LOG_DIR}/flow_setup_times.csv"
    content = await _ssh_cat(path)
    if not content:
        return {"error": "No data yet", "rows": []}
    
    rows = []
    try:
        import io
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            rows.append(row)
    except Exception:
        pass

    rows = rows[-200:]
    if rows:
        setups = [float(r["setup_ms"]) for r in rows if r.get("setup_ms")]
        return {
            "avg_setup_ms": round(sum(setups) / len(setups), 3) if setups else 0,
            "max_setup_ms": round(max(setups), 3) if setups else 0,
            "min_setup_ms": round(min(setups), 3) if setups else 0,
            "sample_count": len(setups),
            "recent": rows[-20:]
        }
    return {"rows": []}


# ── Controller efficiency ──────────────────────────────────────────────────────

@app.get("/api/network/controller")
async def get_controller_efficiency():
    path = f"{LOG_DIR}/controller_efficiency.csv"
    content = await _ssh_cat(path)
    if not content:
        return {"error": "No data yet"}
    
    rows = []
    try:
        import io
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
    except Exception:
        pass
    return {"recent": rows[-50:], "count": len(rows)}


# ── Scenario results ──────────────────────────────────────────────────────────

@app.get("/api/network/scenarios")
async def get_scenario_results():
    """Return cached experiment results from remote host CSV files."""
    out = {}
    files = {
        "baseline":     "scenario_1_baseline.csv",
        "heavy":        "scenario_2_heavy.csv",
        "scalability":  "scenario_3_scalability.csv",
        "multipath":    "scenario_4_multipath.csv",
        "link_failure": "scenario_5_link_failure.csv",
    }
    import io
    for key, fname in files.items():
        path = f"{LOG_DIR}/{fname}"
        content = await _ssh_cat(path)
        if content:
            reader = csv.DictReader(io.StringIO(content))
            out[key] = list(reader)
        else:
            out[key] = []

    content_summary = await _ssh_cat(f"{LOG_DIR}/experiment_summary.json")
    if content_summary:
        try:
            out["summary"] = json.loads(content_summary)
        except Exception:
            pass
    return out

# @app.post("/api/network/experiments/run")
# async def run_experiment(request: Request):
#     """Runs a specific research scenario on the remote Mininet host."""
#     # Logic commented out to disable experimentation features
#     return {"status": "disabled", "message": "Experimentation features are currently inactive."}


# ── Latency (background ping logs) ───────────────────────────────────────────

_latency_cache = {"wan": {"latency": 0, "jitter": 0},
                  "internal": {"latency": 0, "jitter": 0}}


async def _read_ping_log(label: str) -> dict:
    log_file = f"/tmp/ping_{label}.log"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4",
            SDN_HOST, f"tail -n 10 {log_file}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=7)
        rtts = [float(m.group(1))
                for m in re.finditer(r"time=([\d.]+)\s+ms", stdout.decode())]
        if not rtts:
            return {"latency": 0, "jitter": 0}
        avg = round(sum(rtts) / len(rtts), 2)
        jit = 0.0
        if len(rtts) > 1:
            diffs = [abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))]
            jit   = round(sum(diffs) / len(diffs), 3)
        return {"latency": avg, "jitter": jit}
    except Exception:
        return {"latency": 0, "jitter": 0}


async def _latency_updater():
    while True:
        wan, internal = await asyncio.gather(
            _read_ping_log("wan"),
            _read_ping_log("internal"),
        )
        _latency_cache["wan"]      = wan
        _latency_cache["internal"] = internal
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_latency_updater())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
