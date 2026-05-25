import {
  LayoutDashboard, Video, Server, Users, FileText,
  Activity, Settings, ChevronLeft, Sun, Moon,
  Camera, ShieldAlert, AlertTriangle,
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
 * Sidebar navigation — derived from:
 * - Original design (Dashboard, Live Cameras, Gateways, Users, Audit Logs, Alerts, Health, Settings)
 * - cctv-core-functionality-features.md §4 (Camera Management, Break Glass)
 * - ux-product-spec.md "Core screens"
 * - BACKEND_STATUS.md "What Frontend Can Build Now"
 *
 * ALL items from the original design + ALL items required by MDs are included.
 */
const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, adminOnly: false },
  { id: 'cameras', label: 'Live Cameras', icon: Video, adminOnly: false },
  { id: 'manage-cameras', label: 'Camera Management', icon: Camera, adminOnly: true },
  { id: 'gateways', label: 'Gateways', icon: Server, adminOnly: true },
  { id: 'users', label: 'Users & Access', icon: Users, adminOnly: true },
  { id: 'audit', label: 'Audit Logs', icon: FileText, adminOnly: true },
  { id: 'alerts', label: 'Alerts', icon: AlertTriangle, adminOnly: true },
  { id: 'health', label: 'System Health', icon: Activity, adminOnly: true },
  { id: 'break-glass', label: 'Break Glass', icon: ShieldAlert, adminOnly: true },
  { id: 'settings', label: 'Settings', icon: Settings, adminOnly: false },
];

export function Sidebar({ activeSection, onSectionChange, isAdmin, systemStatus }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const filteredItems = navItems.filter((item) => !item.adminOnly || isAdmin);

  return (
    <div className={`h-full border-r transition-all duration-300 flex flex-col flex-shrink-0 ${
      collapsed ? 'w-20' : 'w-64'
    } ${
      theme === 'dark'
        ? 'bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 border-slate-800/50'
        : 'bg-gradient-to-b from-white via-slate-50 to-white border-slate-200'
    }`}>
      {/* Logo */}
      <div className={`p-6 border-b flex items-center justify-between ${
        theme === 'dark' ? 'border-slate-800/50' : 'border-slate-200'
      }`}>
        {!collapsed && (
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Panoptix" className="w-10 h-10 rounded-lg shadow-lg shadow-orange-500/25" />
            <div>
              <h1 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Panoptix</h1>
              <p className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>CCTV Monitor</p>
            </div>
          </div>
        )}
        {collapsed && (
          <img src="/logo.png" alt="Panoptix" className="w-10 h-10 rounded-lg shadow-lg shadow-orange-500/25 mx-auto" />
        )}
        <button onClick={() => setCollapsed(!collapsed)}
          className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors ${
            collapsed ? 'hidden' : ''
          } ${
            theme === 'dark' ? 'bg-slate-800/50 hover:bg-slate-700/50' : 'bg-slate-100 hover:bg-slate-200'
          }`} aria-label="Collapse sidebar">
          <ChevronLeft className={`w-4 h-4 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`} />
        </button>
      </div>

      {collapsed && (
        <button onClick={() => setCollapsed(false)}
          className={`mx-auto mt-3 w-8 h-8 rounded-md flex items-center justify-center transition-colors ${
            theme === 'dark' ? 'bg-slate-800/50 hover:bg-slate-700/50' : 'bg-slate-100 hover:bg-slate-200'
          }`} aria-label="Expand sidebar">
          <ChevronLeft className={`w-4 h-4 rotate-180 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`} />
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
                  ? theme === 'dark'
                    ? 'bg-gradient-to-r from-orange-500/20 to-amber-500/20 text-orange-400 shadow-lg shadow-orange-500/10'
                    : 'bg-gradient-to-r from-orange-50 to-amber-50 text-orange-700 shadow-sm'
                  : theme === 'dark'
                    ? 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                    : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100'
              } ${collapsed ? 'justify-center px-0' : ''}`} aria-current={isActive ? 'page' : undefined}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={`w-5 h-5 flex-shrink-0 ${isActive
                ? theme === 'dark' ? 'text-orange-400' : 'text-orange-600'
                : theme === 'dark' ? 'text-slate-400 group-hover:text-white' : 'text-slate-400 group-hover:text-slate-700'
              }`} />
              {!collapsed && <span className="font-medium">{item.label}</span>}
              {isActive && !collapsed && (
                <div className={`ml-auto w-2 h-2 rounded-full shadow-lg ${
                  theme === 'dark' ? 'bg-orange-400 shadow-orange-400/50' : 'bg-orange-500 shadow-orange-500/50'
                }`} />
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className={`p-4 border-t space-y-3 ${theme === 'dark' ? 'border-slate-800/50' : 'border-slate-200'}`}>
        <button onClick={toggleTheme}
          className={`flex items-center gap-3 w-full px-4 py-2.5 rounded-lg transition-colors ${
            collapsed ? 'justify-center px-0' : ''
          } ${
            theme === 'dark' ? 'bg-slate-800/50 hover:bg-slate-700/50 text-slate-300' : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
          }`} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          {!collapsed && <span className="text-sm font-medium">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
        </button>
        {!collapsed && (
          <div className={`rounded-lg p-3 ${theme === 'dark' ? 'bg-slate-800/50' : 'bg-slate-100'}`}>
            <div className="flex items-center justify-between mb-1">
              <span className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>System Status</span>
              <div className="flex items-center gap-1">
                <div className={`w-2 h-2 rounded-full animate-pulse ${systemStatus === 'ok' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                <span className={`text-xs ${systemStatus === 'ok' ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {systemStatus === 'ok' ? 'Operational' : 'Checking...'}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Uptime</span>
              <span className={`text-xs font-medium ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>99.9%</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
