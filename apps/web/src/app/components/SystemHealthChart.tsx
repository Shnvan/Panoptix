import { Activity, TrendingUp } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useTheme } from '../../lib/theme';

const mockData = [
  { time: '00:00', value: 45 }, { time: '04:00', value: 32 },
  { time: '08:00', value: 67 }, { time: '12:00', value: 89 },
  { time: '16:00', value: 78 }, { time: '20:00', value: 54 },
  { time: '23:59', value: 61 },
];

export function SystemHealthChart() {
  const { theme } = useTheme();

  return (
    <div className={`backdrop-blur-xl border rounded-lg p-6 ${
      theme === 'dark'
        ? 'bg-gradient-to-br from-neutral-900/90 to-neutral-800/90 border-neutral-700/50'
        : 'bg-white border-neutral-200'
    }`}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center">
            <Activity className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-neutral-900'}`}>Network Activity</h3>
            <p className={`text-sm ${theme === 'dark' ? 'text-neutral-400' : 'text-neutral-500'}`}>Last 24 hours</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-emerald-500">
          <TrendingUp className="w-4 h-4" />
          <span className="text-sm font-medium">+12.5%</span>
        </div>
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={mockData}>
            <defs>
              <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={theme === 'dark' ? '#334155' : '#e2e8f0'} opacity={0.3} />
            <XAxis dataKey="time" stroke={theme === 'dark' ? '#94a3b8' : '#64748b'} tick={{ fill: theme === 'dark' ? '#94a3b8' : '#64748b', fontSize: 12 }} />
            <YAxis stroke={theme === 'dark' ? '#94a3b8' : '#64748b'} tick={{ fill: theme === 'dark' ? '#94a3b8' : '#64748b', fontSize: 12 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: theme === 'dark' ? '#1e293b' : '#ffffff',
                border: `1px solid ${theme === 'dark' ? '#334155' : '#e2e8f0'}`,
                borderRadius: '8px',
                padding: '8px 12px',
                color: theme === 'dark' ? '#f1f5f9' : '#0f172a',
              }}
              labelStyle={{ color: theme === 'dark' ? '#f1f5f9' : '#0f172a', fontWeight: 600 }}
              itemStyle={{ color: '#f97316' }}
            />
            <Area type="monotone" dataKey="value" stroke="#f97316" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
