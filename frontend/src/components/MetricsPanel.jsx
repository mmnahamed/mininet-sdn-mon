import React from 'react';
import { ArrowDownRight, ArrowUpRight, AlertTriangle, Activity, Database } from 'lucide-react';

const formatBytes = (bytes, decimals = 2) => {
    if (!+bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
};

const formatBps = (bps) => {
    if (bps < 1000) return `${bps.toFixed(0)} bps`;
    if (bps < 1000000) return `${(bps / 1000).toFixed(1)} Kbps`;
    return `${(bps / 1000000).toFixed(1)} Mbps`;
};

const PortCard = ({ port }) => {
    const isLocal = port.port_no === 4294967294 || port.port_no === "LOCAL";
    const portName = isLocal ? 'LOCAL' : `Port ${port.port_no}`;

    const hasErrors = port.rx_errors > 0 || port.tx_errors > 0 || port.rx_dropped > 0 || port.tx_dropped > 0;

    return (
        <div className={`bg-gray-900/60 rounded-xl p-4 border border-gray-800 hover:border-blue-500/50 transition-all group shrink-0 ${hasErrors ? 'border-red-500/30 bg-red-500/5' : ''}`}>
            <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2">
                    <Database className="w-3 h-3 text-blue-400" /> {portName}
                </span>
                {hasErrors && (
                    <span className="flex items-center gap-1 text-[10px] text-red-400 font-bold animate-pulse bg-red-400/10 px-2 py-0.5 rounded-full uppercase">
                        <AlertTriangle className="w-3 h-3" /> Errors Detected
                    </span>
                )}
            </div>

            <div className="grid grid-cols-2 gap-3">
                {/* RX Stats */}
                <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-bold uppercase">
                        <ArrowDownRight className="w-3.5 h-3.5" /> RX (Down)
                    </div>
                    <div className="p-2.5 rounded-lg bg-black/40 border border-gray-800 group-hover:border-emerald-500/20 transition-colors">
                        <div className="flex flex-col gap-1">
                            <span className="text-sm font-mono text-gray-100 font-bold">{formatBytes(port.rx_bytes)}</span>
                            <span className="text-[11px] font-mono text-emerald-400/80 font-semibold">{formatBps(port.rx_bps || 0)}</span>
                            <div className="flex items-center justify-between mt-1 pt-1 border-t border-gray-800/50">
                                <span className="text-[10px] text-gray-500">{port.rx_packets?.toLocaleString()} pkts</span>
                                {port.rx_errors > 0 && <span className="text-[10px] text-red-400">{port.rx_errors} err</span>}
                            </div>
                            {port.latency !== undefined && (
                                <div className="flex items-center justify-between mt-1 pt-1 border-t border-gray-800/20">
                                    <span className={`text-[10px] font-bold ${port.latency > 20 ? 'text-amber-400' : 'text-emerald-500/70'}`}>
                                        {port.latency.toFixed(2)}ms <span className="text-[8px] font-normal opacity-60">LAT</span>
                                    </span>
                                    <span className="text-[10px] text-sky-400/70 font-bold">
                                        {port.jitter.toFixed(3)}ms <span className="text-[8px] font-normal opacity-60">JIT</span>
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* TX Stats */}
                <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-[10px] text-sky-400 font-bold uppercase">
                        <ArrowUpRight className="w-3.5 h-3.5" /> TX (Up)
                    </div>
                    <div className="p-2.5 rounded-lg bg-black/40 border border-gray-800 group-hover:border-sky-500/20 transition-colors">
                        <div className="flex flex-col gap-1">
                            <span className="text-sm font-mono text-gray-100 font-bold">{formatBytes(port.tx_bytes)}</span>
                            <span className="text-[11px] font-mono text-sky-400/80 font-semibold">{formatBps(port.tx_bps || 0)}</span>
                            <div className="flex items-center justify-between mt-1 pt-1 border-t border-gray-800/50">
                                <span className="text-[10px] text-gray-500">{port.tx_packets?.toLocaleString()} pkts</span>
                                {port.tx_errors > 0 && <span className="text-[10px] text-red-400">{port.tx_errors} err</span>}
                            </div>
                            {port.latency !== undefined && (
                                <div className="flex items-center justify-between mt-1 pt-1 border-t border-gray-800/20 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <span className="text-[9px] text-gray-500 uppercase tracking-tighter">Link Quality Active</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default function MetricsPanel({ metrics, nodes }) {
    if (!nodes || nodes.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500 gap-3">
                <Activity className="w-8 h-8 opacity-20 animate-pulse" />
                <span className="text-sm font-medium">Waiting for switch telemetry…</span>
            </div>
        );
    }

    // Filter only switch nodes that have telemetry data
    const switchNodes = nodes.filter(n => n.type === 'switch');
    const switchData = metrics.switches || metrics; // fallback for safety

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-12">
            {switchNodes.map(node => {
                const ports = switchData[node.dpid] || [];
                return (
                    <div key={node.dpid} className="flex flex-col bg-gray-900/40 rounded-2xl border border-gray-800/60 overflow-hidden shadow-xl shadow-black/20">
                        <div className="px-5 py-3.5 bg-gray-800/80 border-b border-gray-700/50 flex items-center justify-between backdrop-blur-md">
                            <div className="flex items-center gap-3">
                                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                                <h3 className="font-bold text-gray-100 text-sm tracking-wide uppercase">{node.name}</h3>
                            </div>
                            <span className="text-[11px] text-gray-500 font-mono bg-black/40 px-2 py-1 rounded border border-gray-700/50">DPID: {node.dpid}</span>
                        </div>
                        <div className="p-4 grid grid-cols-1 gap-3 overflow-y-auto max-h-[500px] scrollbar-thin scrollbar-thumb-gray-800">
                            {ports.length === 0 ? (
                                <div className="text-center py-12 flex flex-col items-center gap-2">
                                    <Activity className="w-6 h-6 text-gray-700" />
                                    <p className="text-gray-600 text-xs">Awaiting data from Controller...</p>
                                </div>
                            ) : (
                                ports.map((port, i) => <PortCard key={i} port={port} />)
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
