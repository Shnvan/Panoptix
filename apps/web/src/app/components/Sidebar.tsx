import {
  LayoutDashboard, Video, Server, Users, FileText,
  Activity, Settings, ChevronLeft, Sun, Moon,
  Camera, ShieldAlert, AlertTriangle, Eye, UserSearch,
} from 'lucide-react';
import { useState } from 'react';
import { useTheme } from '../../lib/theme';

interface SidebarProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
  isAdmin: boolean;
  systemStatus: string;
}

/**
 * Sidebar navigation — all items backed by real backend APIs.
 */
const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, adminOnly: false },
  { id: 'cameras', label: 'Live Cameras', icon: Video, adminOnly: false },
  { id: 'manage-cameras', label: 'Camera Management', icon: Camera, adminOnly: true },
  { id: 'gateways', label: 'Gateways', icon: Server, adminOnly: true },
  { id: 'users', label: 'Users & Access', icon: Users, adminOnly: true },
  { id: 'audit', label: 'Audit Logs', icon: FileText, adminOnly: true },
  { id: 'alerts', label: 'Alerts', icon: AlertTriangle, adminOnly: true },
  { id: 'visitors', label: 'Visitor Visits', icon: Eye, adminOnly: true },
  { id: 'actors', label: 'Actor Investigation', icon: UserSearch, adminOnly: true },
  { id: 'health', label: 'System Health', icon: Activity, adminOnly: true },
  { id: 'break-glass', label: 'Break Glass', icon: ShieldAlert, adminOnly: true },
  { id: 'settings', label: 'Settings', icon: Settings, adminOnly: false },
];

export function Sidebar({ activeSection, onSectionChange, isAdmin, systemStatus }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const filteredItems = navItems.filter((item) => !item.adminOnly || isAdmin);
  const d = theme === 'dark';

  return (
    <div className={`h-full border-r transition-all duration-300 flex flex-col flex-shrink-0 ${
      collapsed ? 'w-20' : 'w-64'
    } ${
      d
        ? 'bg-black border-neutral-800/50'
        : 'bg-neutral-950 border-neutral-800'
    }`}>
      {/* Logo */}
      <div className="p-6 border-b border-neutral-800/50 flex items-center justify-between">
        {!collapsed && (
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Panoptix" className="w-10 h-10 rounded-lg shadow-lg shadow-orange-500/25" />
            <div>
              <h1 className="font-semibold text-white">Panoptix</h1>
              <p className="text-xs text-neutral-400">CCTV Monitor</p>
            </div>
          </div>
        )}
        {collapsed && (
          <img src="/logo.png" alt="Panoptix" className="w-10 h-10 rounded-lg shadow-lg shadow-orange-500/25 mx-auto" />
        )}
        <button onClick={() => setCollapsed(!collapsed)}
          className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors ${
            collapsed ? 'hidden' : ''
          } bg-neutral-800/50 hover:bg-neutral-700/50`} aria-label="Collapse sidebar">
          <ChevronLeft className="w-4 h-4 text-neutral-400" />
        </button>
      </div>

      {collapsed && (
        <button onClick={() => setCollapsed(false)}
          className="mx-auto mt-3 w-8 h-8 rounded-md flex items-center justify-center transition-colors bg-neutral-800/50 hover:bg-neutral-700/50"
          aria-label="Expand sidebar">
          <ChevronLeft className="w-4 h-4 rotate-180 text-neutral-400" />
        </button>
      )}

      {/* Nav */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {filteredItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;
          return (
            <button key={item.id} onClick={() => onSectionChange(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all group ${
                isActive
                  ? 'bg-orange-500/15 text-orange-400 shadow-lg shadow-orange-500/5'
                  : 'text-neutral-400 hover:text-white hover:bg-white/5'
              } ${collapsed ? 'justify-center px-0' : ''}`} aria-current={isActive ? 'page' : undefined}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={`w-5 h-5 flex-shrink-0 ${isActive
                ? 'text-orange-400'
                : 'text-neutral-500 group-hover:text-white'
              }`} />
              {!collapsed && <span className="font-medium text-sm">{item.label}</span>}
              {isActive && !collapsed && (
                <div className="ml-auto w-2 h-2 rounded-full bg-orange-400 shadow-lg shadow-orange-400/50" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-neutral-800/50 space-y-3">
        <button onClick={toggleTheme}
          className={`flex items-center gap-3 w-full px-4 py-2.5 rounded-lg transition-colors ${
            collapsed ? 'justify-center px-0' : ''
          } bg-neutral-800/50 hover:bg-neutral-700/50 text-neutral-300`}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          {!collapsed && <span className="text-sm font-medium">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
        </button>
        {!collapsed && (
          <div className="rounded-lg p-3 bg-neutral-800/50">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-400">System Status</span>
              <div className="flex items-center gap-1.5">
                <div className={`w-2 h-2 rounded-full animate-pulse ${systemStatus === 'ok' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                <span className={`text-xs font-medium ${systemStatus === 'ok' ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {systemStatus === 'ok' ? 'Operational' : 'Checking...'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
