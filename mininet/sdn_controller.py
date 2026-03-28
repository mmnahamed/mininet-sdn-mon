"""
SDN Research Controller  (sdn_controller.py)
=============================================
Drop-in replacement for  ryu.app.simple_switch_13  that adds:

  • Flow-setup time measurement  → /tmp/sdn_logs/flow_setup_times.csv
  • Per-port statistics (3 s poll) → /tmp/sdn_logs/port_stats.csv
  • Controller efficiency metrics  → /tmp/sdn_logs/controller_efficiency.csv
    (CPU %, memory MB, flows installed, requests/s, active switches)
  • Extra REST endpoints served on the Ryu WSGI port (8080):
      GET /sdn/stats/summary   → JSON summary snapshot
      GET /sdn/stats/ports     → all collected port stats

Run alongside the standard Ryu REST apps:
  ryu-manager sdn_controller.py ryu.app.ofctl_rest ryu.app.rest_topology
"""

import csv
import json
import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime

import psutil
from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (CONFIG_DISPATCHER, MAIN_DISPATCHER,
                                    set_ev_cls)
from ryu.lib import hub
from ryu.lib.packet import ethernet, ether_types, packet
from ryu.ofproto import ofproto_v1_3

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = "/tmp/sdn_logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/controller.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── CSV initialisation ────────────────────────────────────────────────────────
FLOW_CSV  = f"{LOG_DIR}/flow_setup_times.csv"
PORT_CSV  = f"{LOG_DIR}/port_stats.csv"
CTRL_CSV  = f"{LOG_DIR}/controller_efficiency.csv"


def _init_csv(path, headers):
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(headers)


_init_csv(FLOW_CSV, [
    "timestamp", "dpid", "in_port", "eth_src", "eth_dst", "out_port", "setup_ms",
])
_init_csv(PORT_CSV, [
    "timestamp", "dpid", "port_no",
    "rx_bytes", "tx_bytes", "rx_packets", "tx_packets",
    "rx_errors", "tx_errors", "rx_dropped", "tx_dropped",
])
_init_csv(CTRL_CSV, [
    "timestamp", "cpu_pct", "mem_mb",
    "flows_installed", "requests_per_sec", "active_switches",
])


# ── Controller ────────────────────────────────────────────────────────────────

class SdnResearchController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {"wsgi": WSGIApplication}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mac_to_port     = {}                  # dpid (int) → {mac → port}
        self.datapaths       = {}                  # dpid (int) → datapath
        self.port_stats      = defaultdict(dict)   # dpid (str) → port_no (str) → stat dict

        self.flows_installed = 0
        self._req_timestamps = []                  # recent PacketIn timestamps (last 10 s)
        self._lock           = threading.Lock()

        wsgi = kwargs["wsgi"]
        wsgi.register(SdnStatsApi, {"controller_app": self})

        hub.spawn(self._stats_poller)
        hub.spawn(self._efficiency_logger)

        logger.info("SdnResearchController started — logs in %s", LOG_DIR)

    # ── Switch handshake ──────────────────────────────────────────────────────

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp     = ev.msg.datapath
        ofp    = dp.ofproto
        parser = dp.ofproto_parser

        self.datapaths[dp.id] = dp
        logger.info("Switch connected  dpid=%s", hex(dp.id))

        # Install table-miss: send everything to controller
        match   = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self._add_flow(dp, priority=0, match=match, actions=actions)

    # ── Packet-in ─────────────────────────────────────────────────────────────

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        t_start = time.monotonic()

        msg     = ev.msg
        dp      = msg.datapath
        ofp     = dp.ofproto
        parser  = dp.ofproto_parser
        in_port = msg.match["in_port"]
        dpid    = dp.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src_mac = eth.src
        dst_mac = eth.dst

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src_mac] = in_port

        out_port = self.mac_to_port[dpid].get(dst_mac, ofp.OFPP_FLOOD)
        actions  = [parser.OFPActionOutput(out_port)]

        # Install a unicast flow for known destinations
        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(
                in_port=in_port, eth_dst=dst_mac, eth_src=src_mac
            )
            if msg.buffer_id != ofp.OFP_NO_BUFFER:
                self._add_flow(dp, 1, match, actions, buffer_id=msg.buffer_id)
            else:
                self._add_flow(dp, 1, match, actions)

        # Send packet out
        data = None if msg.buffer_id != ofp.OFP_NO_BUFFER else msg.data
        out  = parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data,
        )
        dp.send_msg(out)

        # ── Record metrics ────────────────────────────────────────────────────
        setup_ms = (time.monotonic() - t_start) * 1000
        self._log_flow_setup(dpid, in_port, src_mac, dst_mac, out_port, setup_ms)

        with self._lock:
            self.flows_installed += 1
            now = time.time()
            self._req_timestamps.append(now)
            self._req_timestamps = [t for t in self._req_timestamps if now - t < 10]

    # ── Flow mod helper ───────────────────────────────────────────────────────

    def _add_flow(self, dp, priority, match, actions,
                  buffer_id=None, idle_timeout=30, hard_timeout=0):
        parser = dp.ofproto_parser
        ofp    = dp.ofproto
        inst   = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        kwargs = dict(
            datapath=dp, priority=priority, match=match,
            instructions=inst,
            idle_timeout=idle_timeout, hard_timeout=hard_timeout,
        )
        if buffer_id and buffer_id != ofp.OFP_NO_BUFFER:
            kwargs["buffer_id"] = buffer_id
        dp.send_msg(parser.OFPFlowMod(**kwargs))

    # ── Port statistics polling ───────────────────────────────────────────────

    def _stats_poller(self):
        """Request port stats from every switch every 3 seconds."""
        while True:
            hub.sleep(3)
            for dp in list(self.datapaths.values()):
                parser = dp.ofproto_parser
                req    = parser.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY)
                dp.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        ts       = datetime.utcnow().isoformat()
        dp       = ev.msg.datapath
        dpid_str = str(dp.id)
        csv_rows = []

        for stat in ev.msg.body:
            pno = stat.port_no
            if pno > 65000:      # skip LOCAL / reserved
                continue

            entry = {
                "port_no":    pno,
                "rx_bytes":   stat.rx_bytes,
                "tx_bytes":   stat.tx_bytes,
                "rx_packets": stat.rx_packets,
                "tx_packets": stat.tx_packets,
                "rx_errors":  stat.rx_errors,
                "tx_errors":  stat.tx_errors,
                "rx_dropped": stat.rx_dropped,
                "tx_dropped": stat.tx_dropped,
                "timestamp":  ts,
            }
            self.port_stats[dpid_str][str(pno)] = entry
            csv_rows.append([
                ts, dpid_str, pno,
                stat.rx_bytes, stat.tx_bytes,
                stat.rx_packets, stat.tx_packets,
                stat.rx_errors, stat.tx_errors,
                stat.rx_dropped, stat.tx_dropped,
            ])

        with open(PORT_CSV, "a", newline="") as f:
            csv.writer(f).writerows(csv_rows)

    # ── Controller efficiency logger ──────────────────────────────────────────

    def _efficiency_logger(self):
        """Log CPU / memory / flow rate every 10 seconds."""
        proc = psutil.Process()
        while True:
            hub.sleep(10)
            cpu = proc.cpu_percent(interval=1)
            mem = proc.memory_info().rss / (1024 * 1024)
            with self._lock:
                flows = self.flows_installed
                rps   = len(self._req_timestamps) / 10.0
                n_sw  = len(self.datapaths)
            ts = datetime.now().astimezone().isoformat()
            row = [ts, round(cpu, 2), round(mem, 2), flows, round(rps, 3), n_sw]
            with open(CTRL_CSV, "a", newline="") as f:
                csv.writer(f).writerow(row)
            logger.info(
                "Efficiency | CPU:%.1f%% MEM:%.1fMB flows:%d rps:%.2f sw:%d",
                cpu, mem, flows, rps, n_sw,
            )

    # ── CSV writer ────────────────────────────────────────────────────────────

    def _log_flow_setup(self, dpid, in_port, src, dst, out_port, ms):
        ts = datetime.now().astimezone().isoformat()
        with open(FLOW_CSV, "a", newline="") as f:
            csv.writer(f).writerow(
                [ts, dpid, in_port, src, dst, out_port, round(ms, 4)]
            )

    # ── Public helpers (used by REST API) ─────────────────────────────────────

    def get_port_stats(self):
        return dict(self.port_stats)

    def get_summary(self):
        with self._lock:
            rps = len(self._req_timestamps) / 10.0
        return {
            "active_switches":  len(self.datapaths),
            "flows_installed":  self.flows_installed,
            "requests_per_sec": round(rps, 3),
            "log_dir":          LOG_DIR,
        }


# ── REST API ──────────────────────────────────────────────────────────────────

class SdnStatsApi(ControllerBase):

    def __init__(self, req, link, data, **config):
        super().__init__(req, link, data, **config)
        self.ctrl: SdnResearchController = data["controller_app"]

    @route("sdn_stats", "/sdn/stats/summary", methods=["GET"])
    def summary(self, req, **_kw):
        return self._json(self.ctrl.get_summary())

    @route("sdn_stats", "/sdn/stats/ports", methods=["GET"])
    def ports(self, req, **_kw):
        return self._json(self.ctrl.get_port_stats())

    @staticmethod
    def _json(obj):
        from webob import Response
        body = json.dumps(obj, default=str).encode()
        return Response(content_type="application/json", body=body)