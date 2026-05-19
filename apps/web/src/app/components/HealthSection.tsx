import { Activity, CheckCircle, XCircle, AlertTriangle, Shield, Wrench, Radio, Server, Globe, Lock, Database, HardDrive } from 'lucide-react';
import { motion } from 'motion/react';
import { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../../lib/theme';
import { api, ApiError } from '../../lib/api';
import { useBackupStatus } from '../../lib/hooks';
import type { DeepHealthResponse } from '../../lib/types';

export function HealthSection() {
  const { theme } = useTheme();
  const d = theme === 'dark';

  const [health, setHealth] = useState<DeepHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [maintenanceResult, setMaintenanceResult] = useState<string | null>(null);
  const [runningMaintenance, setRunningMaintenance] = useState(false);
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [livekitMode, setLivekitMode] = useState<'cloud' | 'fallback'>('cloud');
  const [switchingMode, setSwitchingMode] = useState(false);
  const { backup } = useBackupStatus();

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 5000);
  };

  useEffect(() => {
    api.getDeepHealth()
      .then(h => setHealth(h))
      .catch(() => setHealth(null))
      .finally(() => setHealthLoading(false));
  }, []);

  const handleMaintenance = useCallback(async () => {
    setRunningMaintenance(true);
    try {
      const r = await api.runMaintenance();
      setMaintenanceResult(`Expired commands cleaned: ${r.expired_commands}, stops enqueued: ${r.stops_enqueued}`);
      showMsg('Maintenance completed successfully', 'success');
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'Maintenance failed', 'error');
    }
    setRunningMaintenance(false);
  }, []);

  const handleLivekitToggle = useCallback(async () => {
    const newMode = livekitMode === 'cloud' ? 'fallback' : 'cloud';
    setSwitchingMode(true);
    try {
      await api.toggleLivekitFallback(newMode);
      setLivekitMode(newMode);
      showMsg(`LiveKit switched to ${newMode} mode`, 'success');
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'Failed to switch LiveKit mode', 'error');
    }
    setSwitchingMode(false);
  }, [livekitMode]);

  const statusIcon = (s: string) => {
    if (s === 'ok' || s === 'healthy' || s === 'pass') return <CheckCircle className="w-5 h-5 text-emerald-400" />;
    if (s === 'degraded' || s === 'warn') return <AlertTriangle className="w-5 h-5 text-amber-400" />;
    return <XCircle className="w-5 h-5 text-red-400" />;
  };

  const statusBg = (s: string) => {
    if (s === 'ok' || s === 'healthy' || s === 'pass') return 'bg-emerald-500/10 border-emerald-500/20';
    if (s === 'degraded' || s === 'warn') return 'bg-amber-500/10 border-amber-500/20';
    return 'bg-red-500/10 border-red-500/20';
  };

  const renderSecurityCheck = (title: string, IconComp: typeof Shield) => (
    <div className={`backdrop-blur-xl border rounded-lg p-5 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
      <div className="flex items-center gap-3 mb-3">
        <IconComp className="w-5 h-5 text-slate-400" />
        <h4 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>{title}</h4>
      </div>
      <p className={`text-sm ${d ? 'text-slate-500' : 'text-slate-400'}`}>
        Planned pilot check. Backend endpoint is not implemented in the current branch.
      </p>
    </div>
  );

  const latestBackup = backup?.latest_run;

  return (
    <div className="space-y-6">
      <div>
        <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>System Health</h2>
        <p className={d ? 'text-slate-400' : 'text-slate-500'}>Deep health monitoring, backup status, and maintenance controls</p>
      </div>

      {msg && (
        <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
          msg.type === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
        }`}>
          {msg.type === 'error' ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          {msg.text}
        </div>
      )}

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        className={`backdrop-blur-xl border rounded-lg p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center">
            <Activity className="w-5 h-5 text-emerald-500" />
          </div>
          <div>
            <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Deep Health Check</h3>
            <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>DB, LiveKit, and gateway reachability</p>
          </div>
        </div>

        {healthLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className={`p-4 rounded-lg animate-pulse ${d ? 'bg-slate-800/50' : 'bg-slate-100'}`}>
                <div className="h-4 w-16 rounded bg-slate-700/50 mb-2" />
                <div className="h-6 w-12 rounded bg-slate-700/50" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Database', status: health?.db || 'unknown', icon: Server },
              { label: 'LiveKit', status: health?.livekit || 'unknown', icon: Radio },
              { label: 'Gateway', status: health?.gateway || 'unknown', icon: Globe },
              { label: 'Overall', status: health?.status || 'unknown', icon: Activity },
            ].map(item => (
              <div key={item.label} className={`p-4 rounded-lg border ${statusBg(item.status)}`}>
                <div className="flex items-center gap-2 mb-2">
                  <item.icon className={`w-4 h-4 ${item.status === 'ok' ? 'text-emerald-400' : item.status === 'degraded' ? 'text-amber-400' : 'text-red-400'}`} />
                  <span className={`text-sm font-medium ${d ? 'text-slate-300' : 'text-slate-600'}`}>{item.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  {statusIcon(item.status)}
                  <span className={`font-semibold ${item.status === 'ok' ? 'text-emerald-400' : item.status === 'degraded' ? 'text-amber-400' : 'text-red-400'}`}>
                    {item.status.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      {/* Backup Status — from GET /admin/backups/status */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
        className={`backdrop-blur-xl border rounded-lg p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
            <Database className="w-5 h-5 text-orange-500" />
          </div>
          <div>
            <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Backup Status</h3>
            <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>Latest database backup from R2 storage</p>
          </div>
        </div>
        {latestBackup ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className={`p-3 rounded-lg ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <p className={`text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}>Status</p>
              <p className={`text-sm font-medium ${latestBackup.status === 'completed' ? 'text-emerald-400' : latestBackup.status === 'running' ? 'text-amber-400' : 'text-red-400'}`}>
                {latestBackup.status.toUpperCase()}
              </p>
            </div>
            <div className={`p-3 rounded-lg ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <p className={`text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}>Upload</p>
              <p className={`text-sm font-medium ${d ? 'text-white' : 'text-slate-900'}`}>{latestBackup.upload_status}</p>
            </div>
            <div className={`p-3 rounded-lg ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <p className={`text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}>Started</p>
              <p className={`text-sm font-medium ${d ? 'text-white' : 'text-slate-900'}`}>{new Date(latestBackup.started_at).toLocaleString()}</p>
            </div>
            <div className={`p-3 rounded-lg ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <p className={`text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}>Size</p>
              <p className={`text-sm font-medium ${d ? 'text-white' : 'text-slate-900'}`}>
                {latestBackup.size_bytes ? `${(latestBackup.size_bytes / 1024 / 1024).toFixed(2)} MB` : '—'}
              </p>
            </div>
          </div>
        ) : (
          <div className={`p-4 rounded-lg text-sm text-center ${d ? 'bg-slate-800/50 text-slate-400' : 'bg-slate-50 text-slate-500'}`}>
            <HardDrive className={`w-8 h-8 mx-auto mb-2 ${d ? 'text-slate-600' : 'text-slate-300'}`} />
            No backup data available
          </div>
        )}
      </motion.div>

      <div>
        <h3 className={`text-lg font-semibold mb-4 flex items-center gap-2 ${d ? 'text-white' : 'text-slate-900'}`}>
          <Shield className="w-5 h-5 text-orange-500" /> Security Check Reports
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {renderSecurityCheck('T-30: Exposure Check', Globe)}
          {renderSecurityCheck('T-45: Media Isolation', Radio)}
          {renderSecurityCheck('T-56: Origin Binding', Lock)}
        </div>
      </div>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
        className={`backdrop-blur-xl border rounded-lg p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center">
              <Radio className="w-5 h-5 text-purple-500" />
            </div>
            <div>
              <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>LiveKit Media Plane</h3>
              <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>
                Current mode: <span className={`font-medium ${livekitMode === 'cloud' ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {livekitMode === 'cloud' ? 'LiveKit Cloud (Primary)' : 'Self-Hosted Fallback'}
                </span>
              </p>
              <p className={`text-xs mt-1 ${d ? 'text-slate-500' : 'text-slate-400'}`}>
                Admin only. Switches dynamic CSP connect-src on next request. No redeploy needed.
              </p>
            </div>
          </div>
          <button onClick={handleLivekitToggle} disabled={switchingMode}
            className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
              livekitMode === 'cloud'
                ? 'bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/30 text-amber-400'
                : 'bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 text-emerald-400'
            }`}>
            {switchingMode ? 'Switching...' : livekitMode === 'cloud' ? 'Switch to Fallback' : 'Switch to Cloud'}
          </button>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
        className={`backdrop-blur-xl border rounded-lg p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center">
              <Wrench className="w-5 h-5 text-amber-500" />
            </div>
            <div>
              <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Manual Maintenance</h3>
              <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>Clean expired commands and enqueue pending stop-publish commands</p>
            </div>
          </div>
          <button onClick={handleMaintenance} disabled={runningMaintenance}
            className="px-4 py-2.5 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white rounded-lg text-sm font-medium shadow-lg shadow-amber-500/25 disabled:opacity-50 transition-all">
            <Wrench className="w-4 h-4 inline mr-2" />{runningMaintenance ? 'Running...' : 'Run Maintenance'}
          </button>
        </div>
        {maintenanceResult && (
          <div className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-sm text-emerald-400">
            {maintenanceResult}
          </div>
        )}
      </motion.div>
    </div>
  );
}
