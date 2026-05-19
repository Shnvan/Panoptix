import { Search, Bell, User, Shield, Clock, Sun, Moon } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTheme } from '../../lib/theme';
import type { MeResponse } from '../../lib/types';

interface HeaderProps {
  user: MeResponse | null;
  alertCount: number;
}

export function Header({ user, alertCount }: HeaderProps) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className={`h-16 backdrop-blur-xl border-b flex items-center justify-between px-6 flex-shrink-0 ${
      theme === 'dark'
        ? 'bg-slate-900/50 border-slate-800/50'
        : 'bg-white/80 border-slate-200'
    }`}>
      {/* Search Bar */}
      <div className="flex-1 max-w-xl">
        <div className="relative">
          <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${
            theme === 'dark' ? 'text-slate-400' : 'text-slate-400'
          }`} />
          <input
            type="text"
            placeholder="Search cameras, gateways, users..."
            className={`w-full rounded-lg pl-10 pr-4 py-2 text-sm transition-all focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${
              theme === 'dark'
                ? 'bg-slate-800/50 border border-slate-700/50 text-white placeholder-slate-400'
                : 'bg-slate-100 border border-slate-200 text-slate-900 placeholder-slate-400'
            }`}
          />
        </div>
      </div>

      {/* Right Side */}
      <div className="flex items-center gap-3">
        {/* Current Time */}
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
          theme === 'dark' ? 'bg-slate-800/50' : 'bg-slate-100'
        }`}>
          <Clock className="w-4 h-4 text-orange-500" />
          <span className={`text-sm font-medium font-mono ${
            theme === 'dark' ? 'text-white' : 'text-slate-700'
          }`}>
            {currentTime.toLocaleTimeString('en-US', { hour12: false })}
          </span>
        </div>

        {/* Security Status */}
        <div className="flex items-center gap-2 px-3 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
          <Shield className="w-4 h-4 text-emerald-400" />
          <span className="text-sm text-emerald-400 font-medium">Secure</span>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
            theme === 'dark'
              ? 'bg-slate-800/50 hover:bg-slate-700/50 text-slate-400 hover:text-white'
              : 'bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-700'
          }`}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        {/* Notifications */}
        <button className={`relative w-10 h-10 rounded-lg flex items-center justify-center transition-colors group ${
          theme === 'dark'
            ? 'bg-slate-800/50 hover:bg-slate-700/50'
            : 'bg-slate-100 hover:bg-slate-200'
        }`}>
          <Bell className={`w-5 h-5 ${
            theme === 'dark' ? 'text-slate-400 group-hover:text-white' : 'text-slate-500 group-hover:text-slate-700'
          }`} />
          {alertCount > 0 && (
            <div className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-xs text-white font-bold">
              {alertCount > 9 ? '9+' : alertCount}
            </div>
          )}
        </button>

        {/* User Profile */}
        <button className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors group ${
          theme === 'dark'
            ? 'bg-slate-800/50 hover:bg-slate-700/50'
            : 'bg-slate-100 hover:bg-slate-200'
        }`}>
          <div className="w-8 h-8 bg-gradient-to-br from-orange-500 to-amber-600 rounded-md flex items-center justify-center">
            <User className="w-5 h-5 text-white" />
          </div>
          <div className="text-left">
            <p className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
              {user?.email?.split('@')[0] || 'User'}
            </p>
            <p className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
              {user?.roles?.includes('admin') ? 'Administrator' : 'Viewer'}
            </p>
          </div>
        </button>
      </div>
    </header>
  );
}
