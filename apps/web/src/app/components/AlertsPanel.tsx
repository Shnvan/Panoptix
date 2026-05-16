import { AlertTriangle, XCircle, Info, Clock, AlertCircle } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';
import type { CameraEvent } from '../../lib/types';

interface AlertsPanelProps {
  events?: CameraEvent[];
}

interface Alert {
  id: string;
  type: 'critical' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
}

function eventsToAlerts(events: CameraEvent[]): Alert[] {
  return events.slice(0, 10).map((e) => ({
    id: e.event_id,
    type: e.kind === 'offline' || e.kind === 'retired' ? 'critical' as const
        : e.kind === 'degraded' || e.kind === 'reconnecting' ? 'warning' as const
        : 'info' as const,
    title: `Camera ${e.kind}`,
    message: `Camera ${e.camera_id.slice(0, 8)} is ${e.kind}${e.gateway_id ? ` via gateway ${e.gateway_id.slice(0, 8)}` : ''}`,
    timestamp: new Date(e.at).toLocaleTimeString('en-US', { hour12: false }),
  }));
}

const defaultAlerts: Alert[] = [
  { id: '1', type: 'info', title: 'System Ready', message: 'All monitoring systems are operational. No active alerts.', timestamp: 'Now' },
];

export function AlertsPanel({ events = [] }: AlertsPanelProps) {
  const { theme } = useTheme();
  const alerts = events.length > 0 ? eventsToAlerts(events) : defaultAlerts;

  const alertConfig = {
    critical: { icon: XCircle, bg: 'from-red-500/20 to-red-600/20', border: 'border-red-500/30', iconColor: 'text-red-400', textColor: 'text-red-400', lightBg: 'from-red-50 to-red-100/50', lightBorder: 'border-red-200', lightText: 'text-red-700' },
    warning: { icon: AlertTriangle, bg: 'from-amber-500/20 to-amber-600/20', border: 'border-amber-500/30', iconColor: 'text-amber-400', textColor: 'text-amber-400', lightBg: 'from-amber-50 to-amber-100/50', lightBorder: 'border-amber-200', lightText: 'text-amber-700' },
    info: { icon: Info, bg: 'from-blue-500/20 to-blue-600/20', border: 'border-blue-500/30', iconColor: 'text-blue-400', textColor: 'text-blue-400', lightBg: 'from-blue-50 to-blue-100/50', lightBorder: 'border-blue-200', lightText: 'text-blue-700' },
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-red-500/20 rounded-xl flex items-center justify-center">
            <AlertCircle className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h3 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Active Alerts</h3>
            <p className={`text-sm ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
              {alerts.length} notification{alerts.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {alerts.map((alert, index) => {
          const config = alertConfig[alert.type];
          const Icon = config.icon;
          return (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className={`backdrop-blur-xl border rounded-xl p-4 transition-all duration-300 hover:shadow-lg ${
                theme === 'dark'
                  ? `bg-gradient-to-br ${config.bg} ${config.border}`
                  : `bg-gradient-to-br ${config.lightBg} ${config.lightBorder}`
              }`}
            >
              <div className="flex gap-4">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                  theme === 'dark' ? 'bg-slate-900/50' : 'bg-white/80'
                }`}>
                  <Icon className={`w-5 h-5 ${config.iconColor}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <h4 className={`font-semibold ${theme === 'dark' ? config.textColor : config.lightText}`}>
                      {alert.title}
                    </h4>
                    <div className={`flex items-center gap-1.5 text-xs flex-shrink-0 ${
                      theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
                    }`}>
                      <Clock className="w-3 h-3" />
                      <span>{alert.timestamp}</span>
                    </div>
                  </div>
                  <p className={`text-sm ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
                    {alert.message}
                  </p>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
