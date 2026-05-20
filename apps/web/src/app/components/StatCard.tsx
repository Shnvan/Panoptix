import type { LucideIcon } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon: LucideIcon;
  color: 'orange' | 'emerald' | 'red' | 'amber' | 'blue';
}

const colorMap = {
  orange:  { bg: 'from-orange-500/20 to-orange-600/20', border: 'border-orange-500/30', icon: 'text-orange-400', text: 'text-orange-400', shadow: 'shadow-orange-500/20', lightBg: 'from-orange-50 to-orange-100/50', lightBorder: 'border-orange-200', lightIcon: 'text-orange-600', lightText: 'text-orange-700' },
  emerald: { bg: 'from-emerald-500/20 to-emerald-600/20', border: 'border-emerald-500/30', icon: 'text-emerald-400', text: 'text-emerald-400', shadow: 'shadow-emerald-500/20', lightBg: 'from-emerald-50 to-emerald-100/50', lightBorder: 'border-emerald-200', lightIcon: 'text-emerald-600', lightText: 'text-emerald-700' },
  red:     { bg: 'from-red-500/20 to-red-600/20', border: 'border-red-500/30', icon: 'text-red-400', text: 'text-red-400', shadow: 'shadow-red-500/20', lightBg: 'from-red-50 to-red-100/50', lightBorder: 'border-red-200', lightIcon: 'text-red-600', lightText: 'text-red-700' },
  amber:   { bg: 'from-amber-500/20 to-amber-600/20', border: 'border-amber-500/30', icon: 'text-amber-400', text: 'text-amber-400', shadow: 'shadow-amber-500/20', lightBg: 'from-amber-50 to-amber-100/50', lightBorder: 'border-amber-200', lightIcon: 'text-amber-600', lightText: 'text-amber-700' },
  blue:    { bg: 'from-blue-500/20 to-blue-600/20', border: 'border-blue-500/30', icon: 'text-blue-400', text: 'text-blue-400', shadow: 'shadow-blue-500/20', lightBg: 'from-blue-50 to-blue-100/50', lightBorder: 'border-blue-200', lightIcon: 'text-blue-600', lightText: 'text-blue-700' },
};

export function StatCard({ title, value, change, trend = 'neutral', icon: Icon, color }: StatCardProps) {
  const { theme } = useTheme();
  const c = colorMap[color];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2, transition: { duration: 0.2 } }}
      className={`backdrop-blur-xl border rounded-lg p-6 transition-all duration-300 cursor-default ${
        theme === 'dark'
          ? `bg-gradient-to-br ${c.bg} ${c.border} shadow-lg ${c.shadow} hover:shadow-xl`
          : `bg-gradient-to-br ${c.lightBg} ${c.lightBorder} shadow-sm hover:shadow-md`
      }`}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={`w-12 h-12 rounded-lg flex items-center justify-center shadow-lg ${
          theme === 'dark' ? `bg-slate-900/50 ${c.shadow}` : 'bg-white/80 shadow-sm'
        }`}>
          <Icon className={`w-6 h-6 ${theme === 'dark' ? c.icon : c.lightIcon}`} />
        </div>
        {change && (
          <span className={`text-sm font-medium ${
            trend === 'up' ? 'text-emerald-500' : trend === 'down' ? 'text-red-500' : theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
          }`}>
            {change}
          </span>
        )}
      </div>
      <div>
        <h3 className={`text-sm mb-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>{title}</h3>
        <p className={`text-3xl font-bold ${theme === 'dark' ? c.text : c.lightText}`}>{value}</p>
      </div>
    </motion.div>
  );
}
