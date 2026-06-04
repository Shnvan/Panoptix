import { Clock, User } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTheme } from '../../lib/theme';
import type { MeResponse } from '../../lib/types';

interface HeaderProps {
  user: MeResponse | null;
}

export function Header({ user }: HeaderProps) {
  const [currentTime, setCurrentTime] = useState(new Date());
  const { theme } = useTheme();

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className={`h-16 backdrop-blur-xl border-b flex items-center justify-between px-6 flex-shrink-0 ${
      theme === 'dark'
        ? 'bg-neutral-950/80 border-neutral-800/50'
        : 'bg-white/90 border-neutral-200'
    }`}>
      {/* Left — Page context */}
      <div className="flex items-center gap-3">
        <div className={`h-8 w-1 rounded-full bg-orange-500`} />
        <h2 className={`text-lg font-semibold tracking-tight ${theme === 'dark' ? 'text-white' : 'text-neutral-900'}`}>
          Control Panel
        </h2>
      </div>

      {/* Right Side */}
      <div className="flex items-center gap-3">
        {/* Current Time */}
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${
          theme === 'dark' ? 'bg-neutral-900/50 border-neutral-800/50' : 'bg-neutral-50 border-neutral-200'
        }`}>
          <Clock className="w-4 h-4 text-orange-500" />
          <span className={`text-sm font-medium font-mono ${
            theme === 'dark' ? 'text-white' : 'text-neutral-700'
          }`}>
            {currentTime.toLocaleTimeString('en-US', { hour12: false })}
          </span>
        </div>

        {/* User Profile */}
        <div className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${
          theme === 'dark'
            ? 'bg-neutral-900/50 border-neutral-800/50'
            : 'bg-neutral-50 border-neutral-200'
        }`}>
          <div className="w-8 h-8 bg-gradient-to-br from-orange-500 to-amber-600 rounded-lg flex items-center justify-center shadow-sm shadow-orange-500/20">
            <User className="w-4 h-4 text-white" />
          </div>
          <div className="text-left">
            <p className={`text-sm font-medium leading-tight ${theme === 'dark' ? 'text-white' : 'text-neutral-900'}`}>
              {user?.email?.split('@')[0] || 'User'}
            </p>
            <p className={`text-xs leading-tight ${theme === 'dark' ? 'text-neutral-400' : 'text-neutral-500'}`}>
              {user?.roles?.includes('admin') ? 'Administrator' : 'Viewer'}
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
