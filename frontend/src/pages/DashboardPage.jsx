import React from 'react';
import { Activity, Cpu, Link2, AlertCircle } from 'lucide-react';
import MetricsPanel from '../components/MetricsPanel';

const StatCard = ({ icon: Icon, label, value, sub, color = 'blue' }) => {
    const colorMap = {
        blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
        emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
        violet: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
        amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    };
    return (
        <div className={`rounded-lg border px-3 py-2.5 flex items-center gap-3 ${colorMap[color]}`}>
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
};

export default function DashboardPage({ metrics, nodes }) {
    const switchCount = nodes.length;
    const portCount = Object.values(metrics)
        .flat()
        .filter(p => p.port_no !== 4294967294)
        .length;
    const totalRx = Object.values(metrics)
        .flat()
        .reduce((acc, p) => acc + (p.rx_bytes || 0), 0);
    const totalTx = Object.values(metrics)
        .flat()
        .reduce((acc, p) => acc + (p.tx_bytes || 0), 0);

    const fmtBytes = b => {
        if (!b) return '0 B';
        const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(b) / Math.log(k));
        return `${parseFloat((b / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
    };

    return (
        <div className="h-full overflow-y-auto bg-gray-950">
            <div className="max-w-4xl mx-auto px-5 py-5 space-y-5">
                <div>
                    <h2 className="text-lg font-bold text-white">Dashboard</h2>
                    <p className="text-gray-500 text-xs">Live aggregated statistics · 3s poll</p>
                </div>

                {/* 2-column compact stat cards */}
                <div className="grid grid-cols-2 gap-3">
                    <StatCard icon={Cpu} label="Active Switches" value={switchCount} sub="OpenFlow enabled" color="blue" />
                    <StatCard icon={Link2} label="Active Ports" value={portCount} sub="Excluding LOCAL" color="emerald" />
                    <StatCard icon={Activity} label="Total RX" value={fmtBytes(totalRx)} sub="All ports" color="violet" />
                    <StatCard icon={Activity} label="Total TX" value={fmtBytes(totalTx)} sub="All ports" color="amber" />
                </div>

                {/* Per-switch port stats */}
                <div>
                    <h3 className="text-xs font-semibold text-gray-400 mb-2 flex items-center gap-1.5 uppercase tracking-wider">
                        <AlertCircle className="w-3.5 h-3.5 text-blue-400" /> Per-Switch Port Statistics
                    </h3>
                    <MetricsPanel metrics={metrics} nodes={nodes} />
                </div>
            </div>
        </div>
    );
}
