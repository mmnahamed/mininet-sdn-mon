import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, Network, Wifi, WifiOff, Loader } from 'lucide-react';

const StatusPill = ({ status }) => {
    if (status === 'ok') {
        return (
            <span className="flex items-center gap-1.5 text-emerald-400 text-xs font-mono bg-emerald-400/10 border border-emerald-500/30 px-3 py-1 rounded-full">
                <Wifi className="w-3 h-3" /> Controller Online
            </span>
        );
    }
    if (status === 'error') {
        return (
            <span className="flex items-center gap-1.5 text-red-400 text-xs font-mono bg-red-400/10 border border-red-500/30 px-3 py-1 rounded-full">
                <WifiOff className="w-3 h-3" /> Connection Lost
            </span>
        );
    }
    return (
        <span className="flex items-center gap-1.5 text-yellow-400 text-xs font-mono bg-yellow-400/10 border border-yellow-500/30 px-3 py-1 rounded-full">
            <Loader className="w-3 h-3 animate-spin" /> Connecting…
        </span>
    );
};

const navItems = [
    { to: '/dashboard', label: 'Dashboard', Icon: LayoutDashboard },
    { to: '/topology', label: 'Topology', Icon: Network },
];

export default function Layout({ status }) {
    return (
        <div className="flex flex-col h-screen bg-gray-950 text-gray-100 overflow-hidden font-sans">
            {/* Top Navbar */}
            <header className="flex-shrink-0 h-14 bg-gray-900 border-b border-gray-800 flex items-center px-6 gap-6 z-30">
                <div className="flex items-center gap-2 mr-4">
                    <Network className="w-5 h-5 text-blue-400" />
                    <span className="text-white font-bold text-lg tracking-tight">SDN Monitor</span>
                    <span className="text-gray-500 text-xs ml-1 hidden sm:block">Mininet + Ryu</span>
                </div>

                <nav className="flex items-center gap-1">
                    {navItems.map(({ to, label, Icon }) => (
                        <NavLink
                            key={to}
                            to={to}
                            className={({ isActive }) =>
                                `flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${isActive
                                    ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30'
                                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                                }`
                            }
                        >
                            <Icon className="w-4 h-4" />
                            {label}
                        </NavLink>
                    ))}
                </nav>

                <div className="ml-auto">
                    <StatusPill status={status} />
                </div>
            </header>

            {/* Page content */}
            <main className="flex-1 overflow-hidden">
                <Outlet />
            </main>
        </div>
    );
}
