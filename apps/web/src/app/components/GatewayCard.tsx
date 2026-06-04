import { Server, Wifi, Activity, HardDrive, Cpu, Clock } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';

interface GatewayCardProps {
  name: string;
  status: 'enabled' | 'disabled' | 'retired';
  gatewayId: string;
  commandCount?: number;
  lastSeen?: string;
}

export function GatewayCard({ name, status, gatewayId, commandCount = 0, lastSeen }: GatewayCardProps) {
  const { theme } = useTheme();

  const cfg = {
    enabled: { bg: 'from-emerald-500/20 to-emerald-600/20', border: 'border-emerald-500/30', text: 'text-emerald-400', dot: 'bg-emerald-400', lightBg: 'from-emerald-50 to-emerald-100/50', lightBorder: 'border-emerald-200', lightText: 'text-emerald-700' },
    disabled: { bg: 'from-amber-500/20 to-amber-600/20', border: 'border-amber-500/30', text: 'text-amber-400', dot: 'bg-amber-400', lightBg: 'from-amber-50 to-amber-100/50', lightBorder: 'border-amber-200', lightText: 'text-amber-700' },
    retired: { bg: 'from-neutral-700/20 to-neutral-800/20', border: 'border-neutral-600/30', text: 'text-neutral-400', dot: 'bg-neutral-400', lightBg: 'from-neutral-50 to-neutral-100/50', lightBorder: 'border-neutral-200', lightText: 'text-neutral-600' },
  }[status];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      className={`backdrop-blur-xl border rounded-lg p-6 transition-all duration-300 ${
        theme === 'dark'
          ? `bg-gradient-to-br ${cfg.bg} ${cfg.border} hover:shadow-lg`
          : `bg-gradient-to-br ${cfg.lightBg} ${cfg.lightBorder} hover:shadow-md`
      }`}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
            theme === 'dark' ? 'bg-neutral-900/50' : 'bg-white/80'
          }`}>
            <Server className={`w-6 h-6 ${theme === 'dark' ? cfg.text : cfg.lightText}`} />
          </div>
          <div>
            <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-neutral-900'}`}>{name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <div className={`w-2 h-2 rounded-full ${cfg.dot} ${status === 'enabled' ? 'animate-pulse' : ''}`} />
              <span className={`text-sm capitalize ${theme === 'dark' ? cfg.text : cfg.lightText}`}>{status}</span>
            </div>
            <p className={`text-xs font-mono mt-1 ${theme === 'dark' ? 'text-neutral-500' : 'text-neutral-400'}`}>
              {gatewayId.slice(0, 8)}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <div className={`flex items-center gap-2 text-sm ${theme === 'dark' ? 'text-neutral-400' : 'text-neutral-500'}`}>
            <Wifi className="w-4 h-4" /><span>Status</span>
          </div>
          <p className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-neutral-900'}`}>
            {status === 'enabled' ? 'Active' : status}
          </p>
        </div>
        <div className="space-y-1">
          <div className={`flex items-center gap-2 text-sm ${theme === 'dark' ? 'text-neutral-400' : 'text-neutral-500'}`}>
            <Activity className="w-4 h-4" /><span>Commands</span>
          </div>
          <p className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-neutral-900'}`}>{commandCount}</p>
        </div>
        <div className="space-y-1">
          <div className={`flex items-center gap-2 text-sm ${theme === 'dark' ? 'text-neutral-400' : 'text-neutral-500'}`}>
            <Cpu className="w-4 h-4" /><span>Health</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`flex-1 h-2 rounded-full overflow-hidden ${theme === 'dark' ? 'bg-neutral-700/50' : 'bg-neutral-200'}`}>
              <div className={`h-full ${status === 'enabled' ? 'bg-emerald-500' : 'bg-neutral-400'}`} style={{ width: status === 'enabled' ? '45%' : '0%' }} />
            </div>
          </div>
        </div>
        <div className="space-y-1">
          <div className={`flex items-center gap-2 text-sm ${theme === 'dark' ? 'text-neutral-400' : 'text-neutral-500'}`}>
            <HardDrive className="w-4 h-4" /><span>Memory</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`flex-1 h-2 rounded-full overflow-hidden ${theme === 'dark' ? 'bg-neutral-700/50' : 'bg-neutral-200'}`}>
              <div className={`h-full ${status === 'enabled' ? 'bg-emerald-500' : 'bg-neutral-400'}`} style={{ width: status === 'enabled' ? '62%' : '0%' }} />
            </div>
          </div>
        </div>
      </div>

      <div className={`mt-4 pt-4 border-t flex items-center gap-2 text-sm ${
        theme === 'dark' ? 'border-neutral-700/50 text-neutral-400' : 'border-neutral-200 text-neutral-500'
      }`}>
        <Clock className="w-4 h-4" />
        <span>Last seen: {lastSeen || 'N/A'}</span>
      </div>
    </motion.div>
  );
}
