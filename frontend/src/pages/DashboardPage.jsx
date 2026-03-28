import React, { useState, useEffect } from 'react';
import {
    Activity, Cpu, Link2, AlertCircle, Zap, BarChart2,
    TrendingUp, Shield, RefreshCw, Clock, Wifi, Database
} from 'lucide-react';
import MetricsPanel from '../components/MetricsPanel';

const API = 'http://192.168.233.140:8000/api/network';

// ── Helpers ────────────────────────────────────────────────────────────────────
const fmtBytes = b => {
    if (!b) return '0 B';
    const k = 1024, s = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return `${(b / Math.pow(k, i)).toFixed(1)} ${s[i]}`;
};
const fmtBps = b => {
    if (b < 1000) return `${b.toFixed(0)} bps`;
    if (b < 1e6) return `${(b / 1000).toFixed(1)} Kbps`;
    return `${(b / 1e6).toFixed(2)} Mbps`;
};
const safe = (v, decimals = 2) => (v == null || v === '' ? '—' : parseFloat(v).toFixed(decimals));

// ── Colour helpers ─────────────────────────────────────────────────────────────
const COLOR = {
    blue: 'text-blue-400   bg-blue-500/10   border-blue-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    violet: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
    amber: 'text-amber-400  bg-amber-500/10  border-amber-500/20',
    rose: 'text-rose-400   bg-rose-500/10   border-rose-500/20',
    sky: 'text-sky-400    bg-sky-500/10    border-sky-500/20',
};

// ── Stat card ──────────────────────────────────────────────────────────────────
const StatCard = ({ icon: Icon, label, value, sub, color = 'blue' }) => (
    <div className={`rounded-lg border px-3 py-2.5 flex items-center gap-3 ${COLOR[color]}`}>
        <div className="p-1.5 rounded-md bg-black/20 shrink-0">
            <Icon className="w-4 h-4" />
        </div>
        <div className="min-w-0">
            <p className="text-gray-400 text-[10px] uppercase tracking-wider truncate">{label}</p>
            <p className="text-lg font-bold text-white leading-tight">{value}</p>
            {sub && <p className="text-[10px] text-gray-500 truncate">{sub}</p>}
        </div>
    </div>
);

// ── Mini bar chart (SVG, no deps) ──────────────────────────────────────────────
const MiniBar = ({ data = [], label = '', color = '#60a5fa', unit = '' }) => {
    if (!data.length) return null;
    const max = Math.max(...data, 0.001);
    return (
        <div>
            <p className="text-[10px] text-gray-500 mb-1 uppercase tracking-wider">{label}</p>
            <svg viewBox={`0 0 ${data.length * 12} 40`} className="w-full h-10">
                {data.map((v, i) => {
                    const h = Math.max(1, (v / max) * 38);
                    return (
                        <rect key={i} x={i * 12} y={40 - h} width={9} height={h}
                            fill={color} rx="1" opacity="0.85" />
                    );
                })}
            </svg>
            <p className="text-[10px] text-gray-500 text-right">
                {data[data.length - 1]?.toFixed(2)} {unit}
            </p>
        </div>
    );
};

// ── Section header ─────────────────────────────────────────────────────────────
const SectionHeader = ({ icon: Icon, title, color = 'text-blue-400' }) => (
    <h3 className={`text-xs font-semibold text-gray-400 mb-2 flex items-center gap-1.5 uppercase tracking-wider`}>
        <Icon className={`w-3.5 h-3.5 ${color}`} /> {title}
    </h3>
);

// ── Flow stats panel ───────────────────────────────────────────────────────────
const FlowStatsPanel = ({ flowData }) => {
    if (!flowData) return null;
    const { avg_setup_ms, max_setup_ms, min_setup_ms, sample_count, recent = [] } = flowData;
    const setups = recent.map(r => parseFloat(r.setup_ms)).filter(Boolean);

    return (
        <div className="bg-gray-900/50 rounded-xl border border-gray-800 p-4 space-y-3">
            <SectionHeader icon={Clock} title="Flow Setup Times" color="text-violet-400" />
            <div className="grid grid-cols-3 gap-2 text-center">
                {[
                    { label: 'AVG', val: safe(avg_setup_ms, 3) + ' ms', color: 'text-emerald-400' },
                    { label: 'MIN', val: safe(min_setup_ms, 3) + ' ms', color: 'text-sky-400' },
                    { label: 'MAX', val: safe(max_setup_ms, 3) + ' ms', color: 'text-amber-400' },
                ].map(({ label, val, color }) => (
                    <div key={label} className="bg-black/30 rounded-lg p-2">
                        <p className="text-[10px] text-gray-500 uppercase">{label}</p>
                        <p className={`text-sm font-bold ${color}`}>{val}</p>
                    </div>
                ))}
            </div>
            <div className="text-[10px] text-gray-600">Samples collected: {sample_count ?? '—'}</div>
            {setups.length > 0 && (
                <MiniBar data={setups} label="Recent setup times (ms)" color="#a78bfa" unit="ms" />
            )}
        </div>
    );
};

// ── Controller efficiency panel ────────────────────────────────────────────────
const ControllerPanel = ({ ctrlData }) => {
    if (!ctrlData?.recent?.length) return null;
    const rows = ctrlData.recent;
    const last = rows[rows.length - 1];
    const cpuSeries = rows.map(r => parseFloat(r.cpu_pct));
    const memSeries = rows.map(r => parseFloat(r.mem_mb));

    return (
        <div className="bg-gray-900/50 rounded-xl border border-gray-800 p-4 space-y-3">
            <SectionHeader icon={Cpu} title="Controller Efficiency" color="text-amber-400" />
            <div className="grid grid-cols-2 gap-2 text-center">
                {[
                    { label: 'CPU', val: `${safe(last?.cpu_pct, 1)}%`, color: 'text-amber-400' },
                    { label: 'Memory', val: `${safe(last?.mem_mb, 0)} MB`, color: 'text-violet-400' },
                    { label: 'Flows', val: last?.flows_installed ?? '—', color: 'text-blue-400' },
                    { label: 'Req/s', val: safe(last?.requests_per_sec, 2), color: 'text-emerald-400' },
                ].map(({ label, val, color }) => (
                    <div key={label} className="bg-black/30 rounded-lg p-2">
                        <p className="text-[10px] text-gray-500 uppercase">{label}</p>
                        <p className={`text-sm font-bold ${color}`}>{val}</p>
                    </div>
                ))}
            </div>
            <MiniBar data={cpuSeries} label="CPU % (history)" color="#f59e0b" unit="%" />
            <MiniBar data={memSeries} label="Memory MB" color="#8b5cf6" unit="MB" />
        </div>
    );
};

// ── Scenario results table ─────────────────────────────────────────────────────
const ScenarioTable = ({ title, rows = [], columns = [] }) => (
    <div className="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden">
        <div className="px-4 py-2.5 bg-gray-800/60 border-b border-gray-700 flex items-center gap-2">
            <BarChart2 className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-xs font-bold text-gray-200 uppercase tracking-wider">{title}</span>
        </div>
        {!rows.length ? (
            <p className="text-gray-600 text-xs text-center py-6">No data — run experiments first</p>
        ) : (
            <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                    <thead>
                        <tr className="border-b border-gray-800">
                            {columns.map(c => (
                                <th key={c.key} className="px-3 py-1.5 text-gray-500 text-left font-medium uppercase tracking-wider">
                                    {c.label}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, i) => (
                            <tr key={i} className="border-b border-gray-800/40 hover:bg-white/5">
                                {columns.map(c => (
                                    <td key={c.key} className={`px-3 py-1.5 font-mono ${c.color ?? 'text-gray-300'}`}>
                                        {row[c.key] != null && row[c.key] !== '' ? row[c.key] : '—'}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        )}
    </div>
);

// ── Tabs ──────────────────────────────────────────────────────────────────────
const TABS = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'flows', label: 'Flow Stats', icon: Zap },
    { id: 'controller', label: 'Controller', icon: Cpu },
    { id: 'scenarios', label: 'Experiments', icon: BarChart2 },
    { id: 'ports', label: 'Port Stats', icon: Database },
];

// ── Main dashboard ─────────────────────────────────────────────────────────────
export default function DashboardPage({ metrics, nodes }) {
    const [tab, setTab] = useState('overview');
    const [flowData, setFlowData] = useState(null);
    const [ctrlData, setCtrlData] = useState(null);
    const [scnData, setScnData] = useState(null);
    const [loading, setLoading] = useState({});
    const [executing, setExecuting] = useState(null);

    const handleRunExperiment = async (id) => {
        setExecuting(id);
        try {
            const res = await fetch(`${API}/experiments/run?scenario=${id}`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                // Scenario started in background
                setTimeout(fetchExtra, 2000);
            }
        } catch (err) {
            console.error("Experiment failed:", err);
        } finally {
            setExecuting(null);
        }
    };

    const fetchExtra = async () => {
        try {
            const [f, c, s] = await Promise.all([
                fetch(`${API}/flows`).then(r => r.json()),
                fetch(`${API}/controller`).then(r => r.json()),
                fetch(`${API}/scenarios`).then(r => r.json()),
            ]);
            setFlowData(f);
            setCtrlData(c);
            setScnData(s);
        } catch { /* silent */ }
    };

    useEffect(() => {
        fetchExtra();
        const id = setInterval(fetchExtra, 10000);
        return () => clearInterval(id);
    }, []);

    // Aggregates for Overview
    const switchCount = nodes.filter(n => n.type === 'switch').length;
    const allPorts = Object.values(metrics).flat().filter(p => p.port_no !== 4294967294);
    const portCount = allPorts.length;
    const totalRx = allPorts.reduce((a, p) => a + (p.rx_bytes || 0), 0);
    const totalTx = allPorts.reduce((a, p) => a + (p.tx_bytes || 0), 0);
    const totalRxBps = allPorts.reduce((a, p) => a + (p.rx_bps || 0), 0);
    const totalTxBps = allPorts.reduce((a, p) => a + (p.tx_bps || 0), 0);
    const errPorts = allPorts.filter(p => (p.rx_errors || 0) + (p.tx_errors || 0) > 0).length;

    // Scenario columns
    const baselineCols = [
        { key: 'src', label: 'Src' }, { key: 'dst', label: 'Dst' },
        { key: 'ping_avg_ms', label: 'Latency (ms)', color: 'text-emerald-400' },
        { key: 'ping_jitter_ms', label: 'Jitter (ms)', color: 'text-sky-400' },
        { key: 'ping_loss_pct', label: 'Loss %', color: 'text-rose-400' },
        { key: 'tcp_bw_mbps', label: 'TCP Mbps', color: 'text-blue-400' },
        { key: 'udp_bw_mbps', label: 'UDP Mbps', color: 'text-violet-400' },
    ];
    const heavyCols = [
        { key: 'src', label: 'Src' }, { key: 'dst', label: 'Dst' },
        { key: 'tcp_bw_mbps', label: 'TCP Mbps', color: 'text-blue-400' },
        { key: 'type', label: 'Scenario' },
    ];
    const scalabilityCols = [
        { key: 'hop_count', label: 'Hops' }, { key: 'dst', label: 'Dst' },
        { key: 'ping_avg_ms', label: 'Latency (ms)', color: 'text-emerald-400' },
        { key: 'jitter_ms', label: 'Jitter (ms)', color: 'text-sky-400' },
        { key: 'loss_pct', label: 'Loss %', color: 'text-rose-400' },
    ];
    const multipathCols = [
        { key: 'run', label: 'Run' }, { key: 'src', label: 'Src' }, { key: 'dst', label: 'Dst' },
        { key: 'ping_avg_ms', label: 'RTT (ms)', color: 'text-emerald-400' },
        { key: 'udp_bw_mbps', label: 'UDP Mbps', color: 'text-violet-400' },
        { key: 'tcp_bw_mbps', label: 'TCP Mbps', color: 'text-blue-400' },
        { key: 'udp_loss_pct', label: 'Loss %', color: 'text-rose-400' },
    ];
    const failureCols = [
        { key: 'phase', label: 'Phase' },
        { key: 'ping_avg_ms', label: 'Latency (ms)', color: 'text-emerald-400' },
        { key: 'loss_pct', label: 'Loss %', color: 'text-rose-400' },
        { key: 'jitter_ms', label: 'Jitter (ms)', color: 'text-sky-400' },
    ];

    return (
        <div className="h-full overflow-y-auto bg-gray-950">
            <div className="max-w-5xl mx-auto px-5 py-5 space-y-4">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-lg font-bold text-white">SDN Research Dashboard</h2>
                        <p className="text-gray-500 text-xs">Hybrid Topology · Live · 3s poll</p>
                    </div>
                    <button onClick={fetchExtra}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700
                                   text-gray-400 hover:text-white text-xs transition-colors">
                        <RefreshCw className="w-3 h-3" /> Refresh
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex gap-1 border-b border-gray-800 pb-0">
                    {TABS.map(({ id, label, icon: Icon }) => (
                        <button key={id} onClick={() => setTab(id)}
                            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-t-lg
                                        transition-colors border-b-2 -mb-px
                                        ${tab === id
                                    ? 'text-blue-300 border-blue-500 bg-blue-500/10'
                                    : 'text-gray-500 border-transparent hover:text-gray-300'}`}>
                            <Icon className="w-3.5 h-3.5" /> {label}
                        </button>
                    ))}
                </div>

                {/* ── OVERVIEW tab ──────────────────────────────────────── */}
                {tab === 'overview' && (
                    <>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                            <StatCard icon={Cpu} label="Switches" value={switchCount} sub="OpenFlow 1.3" color="blue" />
                            <StatCard icon={Link2} label="Ports" value={portCount} sub="Excluding LOCAL" color="emerald" />
                            <StatCard icon={Activity} label="Total RX" value={fmtBytes(totalRx)} sub={fmtBps(totalRxBps)} color="violet" />
                            <StatCard icon={Activity} label="Total TX" value={fmtBytes(totalTx)} sub={fmtBps(totalTxBps)} color="amber" />
                            <StatCard icon={AlertCircle} label="Error Ports" value={errPorts} sub="Ports with errors" color={errPorts > 0 ? 'rose' : 'emerald'} />
                            <StatCard icon={Database} label="Flows" value={ctrlData?.recent?.at(-1)?.flows_installed ?? '—'}
                                sub="Installed by controller" color="sky" />
                        </div>

                        {/* Topology info */}
                        <div className="bg-gray-900/40 rounded-xl border border-gray-800 p-4">
                            <SectionHeader icon={Shield} title="Hybrid Topology Structure" color="text-blue-400" />
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                                {[
                                    { role: 'Core Spine', sw: 's1', desc: '1000 Mbps uplinks' },
                                    { role: 'Aggregation', sw: 's2, s3', desc: 'Cross-link + dual-spine' },
                                    { role: 'Leaf', sw: 's4–s7', desc: '100 Mbps to hosts' },
                                    { role: 'Hosts', sw: 'h1–h8', desc: '10 Mbps edges' },
                                ].map(({ role, sw, desc }) => (
                                    <div key={role} className="bg-black/30 rounded-lg p-2.5 border border-gray-800">
                                        <p className="text-blue-400 font-bold">{role}</p>
                                        <p className="text-gray-300 font-mono">{sw}</p>
                                        <p className="text-gray-600">{desc}</p>
                                    </div>
                                ))}
                            </div>
                            <div className="mt-3 text-[10px] text-gray-500 leading-relaxed">
                                Multi-path: <span className="text-gray-400">s2 ↔ s3 cross-link</span> enables ECMP.
                                WAN: <span className="text-gray-400">h_ext → r1 → s1</span> (20ms, 0.5% loss).
                                Link failure recovery scenario uses the cross-agg path when s1↔s2 fails.
                            </div>
                        </div>
                    </>
                )}

                {/* ── FLOW STATS tab ────────────────────────────────────── */}
                {tab === 'flows' && (
                    <div className="space-y-4">
                        <FlowStatsPanel flowData={flowData} />
                        {flowData?.recent?.length > 0 && (
                            <div className="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden">
                                <div className="px-4 py-2.5 bg-gray-800/60 border-b border-gray-700">
                                    <span className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                                        Recent Flow Installations
                                    </span>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-[11px]">
                                        <thead>
                                            <tr className="border-b border-gray-800">
                                                {['Timestamp', 'DPID', 'In Port', 'Src MAC', 'Dst MAC', 'Out Port', 'Setup (ms)'].map(h => (
                                                    <th key={h} className="px-3 py-1.5 text-gray-500 text-left uppercase tracking-wider">{h}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {(flowData.recent || []).map((r, i) => (
                                                <tr key={i} className="border-b border-gray-800/40 hover:bg-white/5">
                                                    <td className="px-3 py-1 text-gray-500 font-mono">{r.timestamp?.slice(11, 19)}</td>
                                                    <td className="px-3 py-1 text-blue-400 font-mono">{r.dpid}</td>
                                                    <td className="px-3 py-1 text-gray-300 font-mono">{r.in_port}</td>
                                                    <td className="px-3 py-1 text-gray-400 font-mono text-[10px]">{r.eth_src}</td>
                                                    <td className="px-3 py-1 text-gray-400 font-mono text-[10px]">{r.eth_dst}</td>
                                                    <td className="px-3 py-1 text-gray-300 font-mono">{r.out_port}</td>
                                                    <td className={`px-3 py-1 font-bold font-mono ${parseFloat(r.setup_ms) > 5 ? 'text-rose-400' : 'text-emerald-400'}`}>
                                                        {parseFloat(r.setup_ms).toFixed(3)}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* ── CONTROLLER tab ────────────────────────────────────── */}
                {tab === 'controller' && (
                    <div className="space-y-4">
                        <ControllerPanel ctrlData={ctrlData} />
                        {ctrlData?.recent?.length > 0 && (
                            <div className="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden">
                                <div className="px-4 py-2.5 bg-gray-800/60 border-b border-gray-700">
                                    <span className="text-xs font-bold text-gray-200 uppercase tracking-wider">Efficiency Log</span>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-[11px]">
                                        <thead>
                                            <tr className="border-b border-gray-800">
                                                {['Time', 'CPU %', 'Memory (MB)', 'Flows', 'Req/s', 'Switches'].map(h => (
                                                    <th key={h} className="px-3 py-1.5 text-gray-500 text-left uppercase">{h}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {(ctrlData.recent || []).slice(-20).reverse().map((r, i) => (
                                                <tr key={i} className="border-b border-gray-800/40 hover:bg-white/5">
                                                    <td className="px-3 py-1 text-gray-500 font-mono">{r.timestamp?.slice(11, 19)}</td>
                                                    <td className={`px-3 py-1 font-bold ${parseFloat(r.cpu_pct) > 80 ? 'text-rose-400' : 'text-amber-400'}`}>{r.cpu_pct}%</td>
                                                    <td className="px-3 py-1 text-violet-400">{parseFloat(r.mem_mb).toFixed(1)}</td>
                                                    <td className="px-3 py-1 text-blue-400">{r.flows_installed}</td>
                                                    <td className="px-3 py-1 text-emerald-400">{r.requests_per_sec}</td>
                                                    <td className="px-3 py-1 text-gray-300">{r.active_switches}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* ── EXPERIMENTS tab ───────────────────────────────────── */}
                {tab === 'scenarios' && (
                    <div className="space-y-6">
                        <SectionHeader icon={Zap} title="Research Scenario Gallery" color="text-amber-400" />

                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {[
                                { id: '1', title: 'Baseline Performance', desc: 'Intra-leaf (h1↔h2) throughput, latency, and jitter.', color: 'blue' },
                                { id: '2', title: 'Heavy Traffic Load', desc: 'Stress test via 4 parallel cross-leaf TCP streams.', color: 'rose' },
                                { id: '3', title: 'Topology Scalability', desc: 'Sequential ping discovery h1 → h2..h8.', color: 'emerald' },
                                { id: '4', title: 'Multi-Path Routing', desc: 'East-West (h1↔h5) performance across aggregation.', color: 'violet' },
                                { id: '5', title: 'Link Failure Recovery', desc: 'Rerouting latency detection during s1↔s2 outage.', color: 'amber' },
                                { id: 'all', title: 'Full Suite', desc: 'Execute all 5 scenarios sequentially (long duration).', color: 'sky' },
                            ].map((s) => (
                                <div key={s.id} className="bg-gray-900/40 border border-gray-800 rounded-xl p-4 flex flex-col justify-between hover:border-gray-700 transition-colors group">
                                    <div>
                                        <div className="flex items-center justify-between mb-2">
                                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest bg-black/40 border border-gray-700 ${COLOR[s.color]}`}>
                                                Scenario {s.id}
                                            </span>
                                            {executing === s.id && <RefreshCw className="w-3 h-3 text-blue-400 animate-spin" />}
                                        </div>
                                        <h4 className="text-sm font-bold text-white mb-1 group-hover:text-blue-300 transition-colors">{s.title}</h4>
                                        <p className="text-[11px] text-gray-500 leading-relaxed mb-4">{s.desc}</p>
                                    </div>
                                    <button
                                        onClick={() => handleRunExperiment(s.id)}
                                        disabled={!!executing}
                                        className={`w-full py-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2
                                            ${executing === s.id
                                                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                                : 'bg-gray-800 hover:bg-blue-600 text-gray-300 hover:text-white border border-gray-700 hover:border-blue-500'}`}>
                                        {executing === s.id ? 'Executing...' : 'Run Scenario'}
                                        {!executing && <Zap className="w-3 h-3 text-amber-400" />}
                                    </button>
                                </div>
                            ))}
                        </div>

                        <div className="pt-4 border-t border-gray-800">
                            <SectionHeader icon={BarChart2} title="Experiment Results Cache" color="text-sky-400" />
                            <div className="space-y-4">
                                <ScenarioTable title="Scenario 1 – Baseline" rows={scnData?.baseline} columns={baselineCols} />
                                <ScenarioTable title="Scenario 2 – Heavy Traffic" rows={scnData?.heavy} columns={heavyCols} />
                                <ScenarioTable title="Scenario 3 – Scalability" rows={scnData?.scalability} columns={scalabilityCols} />
                                <ScenarioTable title="Scenario 4 – Multi-Path" rows={scnData?.multipath} columns={multipathCols} />
                                <ScenarioTable title="Scenario 5 – Link Failure" rows={scnData?.link_failure} columns={failureCols} />
                            </div>
                        </div>
                    </div>
                )}

                {/* ── PORT STATS tab ────────────────────────────────────── */}
                {tab === 'ports' && (
                    <MetricsPanel metrics={metrics} nodes={nodes} />
                )}
            </div>
        </div>
    );
}