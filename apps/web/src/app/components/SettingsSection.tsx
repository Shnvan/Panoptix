import { Monitor, LogOut, Shield, Activity, Clock, CheckCircle } from 'lucide-react';
import { useTheme } from '../../lib/theme';
import { useActiveSessions } from '../../lib/hooks';
import { api, ApiError } from '../../lib/api';
import { useState } from 'react';
import type { MeResponse } from '../../lib/types';

interface SettingsSectionProps {
  user: MeResponse | null;
}

/**
 * Settings — only real, functional features:
 * - Active sessions list with revoke (from /sessions/active + /sessions/revoke)
 * - User profile info from /me
 * 
 * No fake toggle switches — everything shown must be functional.
 */
export function SettingsSection({ user }: SettingsSectionProps) {
  const { theme } = useTheme();
  const d = theme === 'dark';
  const { sessions, refetch: refetchSessions } = useActiveSessions();
  const [revokedId, setRevokedId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await api.revokeSession(sessionId);
      setRevokedId(sessionId);
      setMsg('Session revoked successfully');
      refetchSessions();
      setTimeout(() => { setRevokedId(null); setMsg(null); }, 3000);
    } catch (err) {
      setMsg(err instanceof ApiError ? err.detail : 'Failed to revoke session');
      setTimeout(() => setMsg(null), 3000);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>Settings</h2>
        <p className={d ? 'text-slate-400' : 'text-slate-500'}>Manage your profile and active sessions</p>
      </div>

      {msg && (
        <div className={`p-3 rounded-lg text-sm ${msg.includes('Failed') || msg.includes('denied') ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'}`}>{msg}</div>
      )}

      {/* User Profile */}
      <div className={`backdrop-blur-xl border rounded-lg p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center gap-3 mb-6">
          <Shield className={`w-5 h-5 ${d ? 'text-orange-400' : 'text-orange-600'}`} />
          <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Your Profile</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            ['Email', user?.email || '—'],
            ['Subject', user?.subject?.slice(0, 20) || '—'],
            ['Roles', user?.roles?.join(', ') || 'none'],
            ['Kind', user?.kind || '—'],
            ['Permissions', (user?.permissions?.length || 0) > 0 ? user!.permissions.join(', ') : 'Standard'],
            ['Auth Mode', user?.is_dev ? 'Dev Auth (local only)' : 'Cloudflare Access'],
          ].map(([label, value]) => (
            <div key={label} className={`p-3 rounded-lg ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <p className={`text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}>{label}</p>
              <p className={`text-sm font-medium ${d ? 'text-white' : 'text-slate-900'}`}>{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Security Info */}
      <div className={`backdrop-blur-xl border rounded-lg p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center gap-3 mb-4">
          <Activity className={`w-5 h-5 ${d ? 'text-emerald-400' : 'text-emerald-600'}`} />
          <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Security Information</h3>
        </div>
        <div className={`space-y-3 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>
          <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Identity verified at every request via Cloudflare Access</div>
          <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Session cookies are HttpOnly — never stored in browser storage</div>
          <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Stream tokens expire in ≤60 seconds and are subscriber-only</div>
          <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Every action is logged in the tamper-evident audit trail</div>
          <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-orange-500" /> MFA reset is admin-mediated only — you cannot reset your own MFA</div>
        </div>
      </div>

      {/* Active Sessions */}
      <div className={`backdrop-blur-xl border rounded-lg p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center gap-3 mb-6">
          <Monitor className={`w-5 h-5 ${d ? 'text-orange-400' : 'text-orange-600'}`} />
          <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Active Sessions</h3>
        </div>
        <div className="space-y-3">
          {sessions.length === 0 ? (
            <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>No active sessions found</p>
          ) : sessions.map(session => (
            <div key={session.id} className={`flex items-center justify-between p-4 rounded-lg ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <div>
                <p className={`text-sm font-medium font-mono ${d ? 'text-white' : 'text-slate-900'}`}>{session.id.slice(0, 12)}...</p>
                <p className={`text-xs ${d ? 'text-slate-400' : 'text-slate-500'}`}>
                  Created: {session.created_at ? new Date(session.created_at).toLocaleString() : '—'}
                  {session.last_seen_at && <> · Last seen: {new Date(session.last_seen_at).toLocaleString()}</>}
                </p>
                {session.ua_fp && <p className={`text-xs mt-1 ${d ? 'text-slate-500' : 'text-slate-400'}`}>{session.ua_fp}</p>}
              </div>
              <button onClick={() => handleRevokeSession(session.id)} disabled={revokedId === session.id}
                className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg text-red-400 text-xs font-medium transition-colors disabled:opacity-50">
                <LogOut className="w-3 h-3" />{revokedId === session.id ? 'Revoked' : 'Revoke'}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Login History — core-features §8 MVP */}
      <div className={`backdrop-blur-xl border rounded-lg p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center gap-3 mb-6">
          <Clock className={`w-5 h-5 ${d ? 'text-purple-400' : 'text-purple-600'}`} />
          <div>
            <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Login History</h3>
            <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>Recent login sessions for your account</p>
          </div>
        </div>
        <div className="space-y-2">
          {sessions.length === 0 ? (
            <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>No login history available</p>
          ) : sessions.map(session => (
            <div key={`hist-${session.id}`} className={`flex items-center gap-4 p-3 rounded-lg ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${d ? 'bg-emerald-500/20' : 'bg-emerald-100'}`}>
                <CheckCircle className="w-4 h-4 text-emerald-500" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className={`text-sm font-medium ${d ? 'text-white' : 'text-slate-900'}`}>
                    {session.created_at ? new Date(session.created_at).toLocaleString() : 'Unknown date'}
                  </p>
                  <span className={`text-xs px-2 py-0.5 rounded-md ${d ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-50 text-emerald-700'}`}>
                    Authenticated
                  </span>
                </div>
                <p className={`text-xs truncate ${d ? 'text-slate-400' : 'text-slate-500'}`}>
                  Session {session.id.slice(0, 8)} · {session.ua_fp || 'Unknown browser'}
                  {session.last_seen_at && ` · Active until ${new Date(session.last_seen_at).toLocaleString()}`}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
