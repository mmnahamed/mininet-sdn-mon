from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import asyncio.subprocess
import re
import time

app = FastAPI(title="SDN Monitor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RYU_BASE_URL = "http://192.168.233.141:8080"
SDN_HOST     = "test@192.168.233.141"

# Regex for veth peers: sw-to-sw
_VETH_RE = re.compile(r'^\d+:\s+(s\d+)-eth(\d+)@(s\d+)-eth(\d+):', re.MULTILINE)
# Regex for host-facing links: s1-eth4@if2
_HOST_VETH_RE = re.compile(r'^\d+:\s+(s\d+)-eth(\d+)@if\d+:', re.MULTILINE)

# State for bandwidth calculation
last_metrics_state = {
    "time": 0,
    "data": {} # dpid -> { port -> rx_bytes, tx_bytes }
}

def _dpid_int(dpid_hex: str) -> str:
    try:
        return str(int(str(dpid_hex), 16))
    except (ValueError, TypeError):
        return str(dpid_hex)

async def _get_remote_topology() -> tuple[list[dict], list[dict]]:
    """
    Parses ip link show to find both switch-switch and switch-host links.
    Synthesizes r1 (router) and h_ext (WAN host) manually since they are not OVS.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            SDN_HOST, "ip link show",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8)
        output = stdout.decode()
    except Exception:
        return [], []

    links = []
    extra_nodes = []
    seen_edges = set()

    # 1. Switch-to-Switch links
    for m in _VETH_RE.finditer(output):
        sw_a, p_a, sw_b, p_b = m.group(1), m.group(2), m.group(3), m.group(4)
        id_a, id_b = sw_a[1:], sw_b[1:]
        edge = tuple(sorted([id_a, id_b]))
        if edge not in seen_edges:
            seen_edges.add(edge)
            links.append({
                "source": id_a, "target": id_b,
                "src_port": p_a, "dst_port": p_b,
                "type": "backbone"
            })

    # 2. External nodes: r1 and h_ext
    # From network_sim.py: r1 connects to s1-eth4. h_ext connects to r1.
    extra_nodes.append({"id": "r1", "label": "Router R1", "type": "router", "dpid": "r1"})
    extra_nodes.append({"id": "h_ext", "label": "WAN Host (h_ext)", "type": "host", "dpid": "h_ext"})

    # Check for s1-eth4 in ip link to confirm r1 link
    for m in _HOST_VETH_RE.finditer(output):
        sw, port = m.group(1), m.group(2)
        if sw == "s1" and port == "4":
            links.append({
                "source": "1", "target": "r1",
                "src_port": "4", "dst_port": "0",
                "type": "uplink"
            })
    
    # h_ext connects to r1 (simulated)
    links.append({
        "source": "r1", "target": "h_ext",
        "src_port": "1", "dst_port": "0",
        "type": "wan"
    })

    return extra_nodes, links

@app.get("/api/network/graph")
async def get_network_graph():
    try:
        async with httpx.AsyncClient() as client:
            # Poll switches, links, AND hosts concurrently
            sw_res, link_res, host_res = await asyncio.gather(
                client.get(f"{RYU_BASE_URL}/v1.0/topology/switches"),
                client.get(f"{RYU_BASE_URL}/v1.0/topology/links"),
                client.get(f"{RYU_BASE_URL}/v1.0/topology/hosts")
            )
            switches_data = sw_res.json() if sw_res.status_code == 200 else []
            ryu_links = link_res.json() if link_res.status_code == 200 else []
            ryu_hosts = host_res.json() if host_res.status_code == 200 else []

        # 1. Process Standard Switch Nodes
        nodes = [
            {
                "id": _dpid_int(s["dpid"]),
                "dpid": _dpid_int(s["dpid"]),
                "label": f"Switch {int(s['dpid'], 16)}",
                "name": f"Switch {int(s['dpid'], 16)}",
                "type": "switch"
            }
            for s in switches_data
        ]

        # 2. Process Mininet Hosts (h1-h6) from Ryu Telemetry
        for h in ryu_hosts:
            host_mac = h.get("mac")
            host_ip = h.get("ipv4", [host_mac])[0] if h.get("ipv4") else host_mac
            
            # Filter out IPv6 multicast artifacts mapped by the controller
            if host_ip.startswith("33:33") or host_ip.startswith("fe80"): 
                continue
                
            nodes.append({
                "id": host_mac,
                "label": f"Host {host_ip}",
                "type": "host"
            })

        # 3. Inject the Custom Router (r1) and WAN Host (h_ext) via SSH scrape
        extra_nodes, extra_links = await _get_remote_topology()
        nodes.extend(extra_nodes)

        # 4. Process Backbone Links (Switch-to-Switch)
        links = []
        if ryu_links:
            links = [{
                "source": _dpid_int(l["src"]["dpid"]),
                "target": _dpid_int(l["dst"]["dpid"]),
                "src_port": l["src"]["port_no"],
                "dst_port": l["dst"]["port_no"],
                "type": "backbone"
            } for l in ryu_links]

        # 5. Process Edge Links (Host-to-Switch)
        for h in ryu_hosts:
            host_mac = h.get("mac")
            host_ip = h.get("ipv4", [host_mac])[0] if h.get("ipv4") else host_mac
            
            if host_ip.startswith("33:33") or host_ip.startswith("fe80"): 
                continue
                
            links.append({
                "source": host_mac,
                "target": _dpid_int(h["port"]["dpid"]),
                "src_port": "eth0", 
                "dst_port": h["port"]["port_no"],
                "type": "edge"
            })

        # Append the router uplink/WAN links
        if extra_links:
            if not ryu_links:
                links.extend(extra_links)
            else:
                links.extend([l for l in extra_links if l["source"] == "r1" or l["target"] == "r1"])

        return {"nodes": nodes, "links": links}
        
    except Exception as e:
        print(f"Topology Error: {e}")
        return {"nodes": [], "links": []}

# Global cache for latency/jitter to avoid SSH overhead in the request loop
latency_jitter_state = {
    "wan": {"latency": 0, "jitter": 0},
    "internal": {"latency": 0, "jitter": 0}
}

async def _get_latency_jitter(client_id: str) -> dict[str, float]:
    """Parses RTT from remote ping logs."""
    log_file = f"/tmp/ping_{client_id}.log"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            SDN_HOST, f"tail -n 10 {log_file}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8)
        rtts = []
        for line in stdout.decode().splitlines():
            m = re.search(r"time=([\d.]+)\s+ms", line)
            if m: rtts.append(float(m.group(1)))
        
        if not rtts: return {"latency": 0, "jitter": 0}
        
        avg_l = round(sum(rtts) / len(rtts), 2)
        jit = 0
        if len(rtts) > 1:
            diffs = [abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))]
            jit = round(sum(diffs) / len(diffs), 3)
        return {"latency": avg_l, "jitter": jit}
    except Exception:
        return {"latency": 0, "jitter": 0}

async def _update_latency_jitter_loop():
    """Background task to update metrics every 5 seconds."""
    while True:
        try:
            wan, internal = await asyncio.gather(
                _get_latency_jitter("wan"),
                _get_latency_jitter("internal")
            )
            global latency_jitter_state
            latency_jitter_state["wan"] = wan
            latency_jitter_state["internal"] = internal
        except Exception:
            pass
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_update_latency_jitter_loop())

@app.get("/api/network/metrics")
async def get_network_metrics():
    global last_metrics_state
    now = time.time()
    dt = now - last_metrics_state["time"]
    
    async with httpx.AsyncClient() as client:
        try:
            sw_res = await client.get(f"{RYU_BASE_URL}/v1.0/topology/switches")
            if sw_res.status_code != 200: return {}
            sw_json = sw_res.json()
            dpids = [_dpid_int(s["dpid"]) for s in sw_json]
            
            stats_resps = await asyncio.gather(
                *[client.get(f"{RYU_BASE_URL}/stats/port/{d}") for d in dpids],
                return_exceptions=True
            )
            
            integrated_metrics = {}
            for i, dpid in enumerate(dpids):
                res = stats_resps[i]
                if isinstance(res, Exception) or res.status_code != 200: continue
                
                ports = list(res.json().values())[0]
                calculated_ports = []
                for p in ports:
                    p_no = str(p["port_no"])
                    rx, tx = p["rx_bytes"], p["tx_bytes"]
                    
                    prev_sw = last_metrics_state["data"].get(dpid, {})
                    prev_p = prev_sw.get(p_no, {"rx": rx, "tx": tx})
                    rx_speed = (rx - prev_p["rx"]) * 8 / dt if dt > 0 else 0
                    tx_speed = (tx - prev_p["tx"]) * 8 / dt if dt > 0 else 0
                    last_metrics_state["data"].setdefault(dpid, {})[p_no] = {"rx": rx, "tx": tx}
                    
                    # Attribution from background cache
                    l_val, j_val = 0, 0
                    if dpid == "1" and p_no == "4":
                        l_val = latency_jitter_state["wan"]["latency"]
                        j_val = latency_jitter_state["wan"]["jitter"]
                    elif dpid in ("3", "4") and p_no == "1":
                        l_val = latency_jitter_state["internal"]["latency"]
                        j_val = latency_jitter_state["internal"]["jitter"]
                    
                    calculated_ports.append({
                        **p,
                        "rx_bps": max(0, rx_speed), "tx_bps": max(0, tx_speed),
                        "rx_errors": p.get("rx_errors", 0), "tx_errors": p.get("tx_errors", 0),
                        "rx_dropped": p.get("rx_dropped", 0), "tx_dropped": p.get("tx_dropped", 0),
                        "latency_ms": l_val, "jitter_ms": j_val
                    })
                integrated_metrics[dpid] = calculated_ports
            
            last_metrics_state["time"] = now
            return integrated_metrics
        except Exception:
            return {}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
