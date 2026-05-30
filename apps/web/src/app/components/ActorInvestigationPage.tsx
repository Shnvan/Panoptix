/* ── ActorInvestigationPage ──
 * Admin actor investigation UI.
 * Profile: GET /api/v1/admin/actors/{actor_type}/{actor_id}/profile
 * Activity: GET /api/v1/admin/actors/{actor_type}/{actor_id}/activity
 *
 * Actor types: user, gateway, system, break_glass, service_token_monitor
 */

import { useState, useCallback, useEffect } from 'react';
import {
  UserSearch, Search, User, Server, Cpu, Shield,
  Clock, AlertCircle, ChevronDown, ChevronUp,
  Loader2, RefreshCw, XCircle, CheckCircle2, Info,
  Activity,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { api, ApiError } from '../../lib/api';
import type { ActorProfileResponse, ActorActivityItem } from '../../lib/types';

// ── Helpers ──

function fmt(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });
}

const ACTOR_TYPES = [
  { value: 'user', label: 'User', icon: User },
  { value: 'gateway', label: 'Gateway', icon: Server },
  { value: 'system', label: 'System', icon: Cpu },
  { value: 'break_glass', label: 'Break-Glass', icon: Shield },
];

const SEVERITY_CLASS: Record<string, string> = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-amber-400',
  low: 'text-blue-400',
  informational: 'text-slate-400',
};

const OUTCOME_BADGE: Record<string, string> = {
  success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  failure: 'bg-red-500/15 text-red-400 border-red-500/30',
  error: 'bg-red-500/15 text-red-400 border-red-500/30',
  denied: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
};

// ── Section card ──

function Section({ title, icon: Icon, children, dark }: {
  title: string;
  icon: typeof User;
  children: React.ReactNode;
  dark: boolean;
}) {
  return (
    <div className={`border rounded-lg overflow-hidden ${dark ? 'border-slate-700/50 bg-slate-900/60' : 'border-slate-200 bg-white'}`}>
      <div className={`flex items-center gap-2 px-4 py-3 border-b ${dark ? 'border-slate-700/50' : 'border-slate-100'}`}>
        <Icon className={`w-4 h-4 ${dark ? 'text-orange-400' : 'text-orange-600'}`} />
        <h4 className={`text-sm font-semibold ${dark ? 'text-white' : 'text-slate-900'}`}>{title}</h4>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function KV({ label, value, dark }: { label: string; value: React.ReactNode; dark: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <span className={`text-xs flex-shrink-0 w-36 ${dark ? 'text-slate-400' : 'text-slate-500'}`}>{label}</span>
      <span className={`text-xs text-right break-all ${dark ? 'text-slate-200' : 'text-slate-800'}`}>{value ?? '—'}</span>
    </div>
  );
}

// ── Activity row ──

function ActivityRow({ item, dark }: { item: ActorActivityItem; dark: boolean }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`border-b ${dark ? 'border-slate-800' : 'border-slate-100'}`}>
      <button
        className={`w-full text-left flex items-center gap-3 px-4 py-2.5 transition-colors ${dark ? 'hover:bg-slate-800/40' : 'hover:bg-slate-50'}`}
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-0.5">
            <span className={`text-xs font-medium ${SEVERITY_CLASS[item.event_severity ?? ''] ?? 'text-slate-400'}`}>
              {item.event_severity ?? '?'}
            </span>
            {item.event_outcome && (
              <span className={`text-xs px-1.5 py-0.5 rounded border ${OUTCOME_BADGE[item.event_outcome] ?? 'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>
                {item.event_outcome}
              </span>
            )}
            {item.event_category && (
              <span className={`text-xs ${dark ? 'text-slate-500' : 'text-slate-400'}`}>{item.event_category}</span>
            )}
          </div>
          <p className={`text-xs truncate font-mono ${dark ? 'text-slate-300' : 'text-slate-700'}`}>{item.action}</p>
          {item.resource && (
            <p className={`text-xs truncate ${dark ? 'text-slate-500' : 'text-slate-400'}`}>{item.resource}</p>
          )}
        </div>
        <div className={`flex-shrink-0 text-xs ${dark ? 'text-slate-500' : 'text-slate-400'}`}>
          {item.ts ? new Date(item.ts).toLocaleTimeString('en-US', { hour12: false }) : '—'}
        </div>
        {item.payload ? (
          expanded ? <ChevronUp className="w-3.5 h-3.5 flex-shrink-0 text-slate-500" /> : <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 text-slate-500" />
        ) : null}
      </button>
      <AnimatePresence>
        {expanded && item.payload && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className={`px-4 pb-3 border-t ${dark ? 'border-slate-800' : 'border-slate-100'}`}
          >
            <pre className={`text-xs mt-2 p-2 rounded overflow-auto max-h-40 ${dark ? 'bg-slate-800 text-slate-300' : 'bg-slate-50 text-slate-700'}`}>
              {JSON.stringify(item.payload, null, 2)}
            </pre>
            <div className={`flex gap-4 mt-2 text-xs ${dark ? 'text-slate-500' : 'text-slate-400'}`}>
              {item.ip && <span>IP: {item.ip}</span>}
              {item.session_id && <span>Session: {item.session_id.slice(0, 8)}…</span>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Profile panel ──

function ProfilePanel({ profile, dark }: { profile: ActorProfileResponse; dark: boolean }) {
  const actorCfg = ACTOR_TYPES.find((a) => a.value === profile.actor_type) ?? ACTOR_TYPES[0];
  const Icon = actorCfg.icon;
  const as = profile.alert_summary;

  return (
    <div className="space-y-4">
      {/* Identity header */}
      <div className={`flex items-center gap-3 p-4 border rounded-lg ${dark ? 'border-slate-700/50 bg-slate-900/60' : 'border-slate-200 bg-white'}`}>
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${dark ? 'bg-orange-500/20' : 'bg-orange-50'}`}>
          <Icon className="w-5 h-5 text-orange-400" />
        </div>
        <div>
          <p className={`font-semibold ${dark ? 'text-white' : 'text-slate-900'}`}>
            {profile.email ?? profile.name ?? actorCfg.label}
          </p>
          <p className={`text-xs font-mono ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
            {profile.actor_type} · {profile.actor_id?.slice(0, 12) ?? 'n/a'}
          </p>
        </div>
        {profile.disabled_at && (
          <span className="ml-auto text-xs px-2 py-0.5 rounded border bg-red-500/15 text-red-400 border-red-500/30">Disabled</span>
        )}
        {profile.status && !profile.disabled_at && (
          <span className={`ml-auto text-xs px-2 py-0.5 rounded border ${
            profile.status === 'active' || profile.status === 'enabled'
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              : 'bg-slate-500/15 text-slate-400 border-slate-500/30'
          }`}>{profile.status}</span>
        )}
      </div>

      {/* Alert summary */}
      {as && (
        <Section title="Alert Summary" icon={AlertCircle} dark={dark}>
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Open', val: as.open, cls: 'text-red-400' },
              { label: 'Ack', val: as.acknowledged, cls: 'text-amber-400' },
              { label: 'Resolved', val: as.resolved, cls: 'text-emerald-400' },
              { label: 'Critical', val: as.critical, cls: 'text-red-500' },
            ].map(({ label, val, cls }) => (
              <div key={label} className={`text-center p-3 rounded-lg ${dark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
                <p className={`text-xl font-bold ${cls}`}>{val}</p>
                <p className={`text-xs mt-1 ${dark ? 'text-slate-400' : 'text-slate-500'}`}>{label}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* User-specific fields */}
      {profile.actor_type === 'user' && (
        <Section title="User Profile" icon={User} dark={dark}>
          <div className={`divide-y ${dark ? 'divide-slate-800' : 'divide-slate-100'}`}>
            <KV label="Email" value={profile.email ?? '—'} dark={dark} />
            <KV label="Roles" value={profile.roles?.join(', ') || 'none'} dark={dark} />
            <KV label="Created" value={fmt(profile.created_at)} dark={dark} />
            <KV label="Disabled" value={profile.disabled_at ? fmt(profile.disabled_at) : <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />} dark={dark} />
          </div>
        </Section>
      )}

      {/* Gateway-specific fields */}
      {profile.actor_type === 'gateway' && (
        <Section title="Gateway Profile" icon={Server} dark={dark}>
          <div className={`divide-y ${dark ? 'divide-slate-800' : 'divide-slate-100'}`}>
            <KV label="Name" value={profile.name ?? '—'} dark={dark} />
            <KV label="Status" value={profile.status ?? '—'} dark={dark} />
            <KV label="Last seen" value={fmt(profile.last_seen_at)} dark={dark} />
          </div>
        </Section>
      )}

      {/* Recent logins (user only) */}
      {profile.recent_logins && profile.recent_logins.length > 0 && (
        <Section title="Login Baseline" icon={Clock} dark={dark}>
          <div className="space-y-2">
            {profile.recent_logins.slice(0, 5).map((login, i) => (
              <div key={i} className={`flex items-center gap-3 p-2.5 rounded text-xs ${dark ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
                <span className={`font-mono ${dark ? 'text-slate-300' : 'text-slate-700'}`}>{login.ip ?? '—'}</span>
                <span className={`flex-1 truncate ${dark ? 'text-slate-500' : 'text-slate-400'}`}>{login.ua ?? '—'}</span>
                <span className={dark ? 'text-slate-500' : 'text-slate-400'}>{fmt(login.ts)}</span>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

// ── Main page ──

export function ActorInvestigationPage() {
  const { theme } = useTheme();
  const dark = theme === 'dark';

  const [actorType, setActorType] = useState('user');
  const [actorId, setActorId] = useState('');
  const [inputId, setInputId] = useState('');

  const [profile, setProfile] = useState<ActorProfileResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [activity, setActivity] = useState<ActorActivityItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityCursor, setActivityCursor] = useState<string | null>(null);

  const resolvedId = actorType === 'system' || actorType === 'break_glass' ? 'none' : actorId;

  const loadProfile = useCallback(async () => {
    if (!resolvedId && actorType !== 'system' && actorType !== 'break_glass') return;
    setProfileLoading(true);
    setProfileError(null);
    setProfile(null);
    try {
      const data = await api.getActorProfile(actorType, resolvedId || 'none');
      setProfile(data);
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.detail : 'Failed to load actor profile');
    } finally {
      setProfileLoading(false);
    }
  }, [actorType, resolvedId]);

  const loadActivity = useCallback(async (cursor?: string) => {
    if (!resolvedId && actorType !== 'system' && actorType !== 'break_glass') return;
    setActivityLoading(true);
    setActivityError(null);
    try {
      const data = await api.getActorActivity(actorType, resolvedId || 'none', cursor);
      setActivity((prev) => cursor ? [...prev, ...data.items] : data.items);
      setActivityCursor(data.next_cursor);
    } catch (err) {
      setActivityError(err instanceof ApiError ? err.detail : 'Failed to load activity');
    } finally {
      setActivityLoading(false);
    }
  }, [actorType, resolvedId]);

  const handleSearch = () => {
    const isSystemActor = actorType === 'system' || actorType === 'break_glass';
    if (!isSystemActor && !inputId.trim()) return;
    if (!isSystemActor) setActorId(inputId.trim());
    setActivity([]);
    setActivityCursor(null);
  };

  useEffect(() => {
    if (!actorId && actorType !== 'system' && actorType !== 'break_glass') return;
    loadProfile();
    setActivity([]);
    setActivityCursor(null);
    loadActivity();
  }, [actorId, actorType, loadProfile, loadActivity]);

  const isSystemActor = actorType === 'system' || actorType === 'break_glass';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${dark ? 'bg-purple-500/20' : 'bg-purple-50'}`}>
          <UserSearch className="w-5 h-5 text-purple-400" />
        </div>
        <div>
          <h3 className={`font-semibold ${dark ? 'text-white' : 'text-slate-900'}`}>Actor Investigation</h3>
          <p className={`text-sm ${dark ? 'text-slate-400' : 'text-slate-500'}`}>Profile and activity timeline for users, gateways, and system actors</p>
        </div>
      </div>

      {/* Search form */}
      <div className={`border rounded-lg p-4 ${dark ? 'border-slate-700/50 bg-slate-900/60' : 'border-slate-200 bg-white'}`}>
        <div className="flex flex-wrap gap-3 items-end">
          {/* Actor type */}
          <div className="flex-shrink-0">
            <label className={`block text-xs mb-1.5 ${dark ? 'text-slate-400' : 'text-slate-500'}`}>Actor type</label>
            <div className="flex gap-1">
              {ACTOR_TYPES.map((t) => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.value}
                    id={`actor-type-${t.value}`}
                    onClick={() => { setActorType(t.value); setActorId(''); setInputId(''); setProfile(null); setActivity([]); }}
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs border transition-colors ${
                      actorType === t.value
                        ? 'bg-orange-500/20 text-orange-400 border-orange-500/30'
                        : dark
                          ? 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-600'
                          : 'bg-slate-50 text-slate-500 border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <Icon className="w-3 h-3" />
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ID input (not shown for system actors) */}
          {!isSystemActor && (
            <div className="flex-1 min-w-48">
              <label className={`block text-xs mb-1.5 ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                {actorType === 'user' ? 'User ID (UUID)' : 'Gateway ID (UUID)'}
              </label>
              <input
                id="actor-id-input"
                type="text"
                value={inputId}
                onChange={(e) => setInputId(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Paste UUID from Users or Audit Logs…"
                className={`w-full text-sm px-3 py-2 rounded border outline-none transition-colors font-mono ${
                  dark
                    ? 'bg-slate-800 border-slate-700 text-slate-200 placeholder-slate-600 focus:border-orange-500/50'
                    : 'bg-white border-slate-200 text-slate-800 placeholder-slate-300 focus:border-orange-400'
                }`}
              />
            </div>
          )}

          <button
            id="actor-search-btn"
            onClick={handleSearch}
            disabled={!isSystemActor && !inputId.trim()}
            className="flex items-center gap-2 px-4 py-2 rounded bg-orange-500 hover:bg-orange-400 text-white text-sm font-medium transition-colors disabled:opacity-40"
          >
            <Search className="w-4 h-4" />
            {isSystemActor ? 'Load System Actor' : 'Investigate'}
          </button>

          {profile && (
            <button
              id="actor-refresh-btn"
              onClick={() => { loadProfile(); setActivity([]); loadActivity(); }}
              disabled={profileLoading}
              className={`flex items-center gap-1.5 text-sm px-3 py-2 rounded transition-colors ${dark ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${profileLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Loading / error */}
      {profileLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
        </div>
      )}

      {profileError && (
        <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${dark ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-red-50 text-red-600 border border-red-200'}`}>
          <XCircle className="w-4 h-4 flex-shrink-0" />
          {profileError}
        </div>
      )}

      {/* Empty hint */}
      {!profile && !profileLoading && !profileError && (
        <div className={`text-center py-12 border rounded-lg ${dark ? 'border-slate-700/50 border-dashed' : 'border-slate-200 border-dashed'}`}>
          <Info className={`w-10 h-10 mx-auto mb-2 ${dark ? 'text-slate-700' : 'text-slate-300'}`} />
          <p className={`text-sm ${dark ? 'text-slate-500' : 'text-slate-400'}`}>
            {isSystemActor ? 'Click "Load System Actor" to investigate' : 'Paste a user or gateway ID and click Investigate'}
          </p>
        </div>
      )}

      {/* Profile + Activity */}
      {profile && !profileLoading && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {/* Left — profile */}
          <ProfilePanel profile={profile} dark={dark} />

          {/* Right — activity timeline */}
          <div className="space-y-3">
            <div className={`border rounded-lg overflow-hidden ${dark ? 'border-slate-700/50' : 'border-slate-200'}`}>
              <div className={`flex items-center justify-between px-4 py-3 border-b ${dark ? 'border-slate-700/50 bg-slate-900/60' : 'border-slate-100 bg-slate-50'}`}>
                <div className="flex items-center gap-2">
                  <Activity className={`w-4 h-4 ${dark ? 'text-orange-400' : 'text-orange-600'}`} />
                  <span className={`text-sm font-semibold ${dark ? 'text-white' : 'text-slate-900'}`}>Activity Timeline</span>
                  <span className={`text-xs ${dark ? 'text-slate-500' : 'text-slate-400'}`}>({activity.length} events)</span>
                </div>
                <button
                  id="activity-refresh"
                  onClick={() => { setActivity([]); loadActivity(); }}
                  disabled={activityLoading}
                  className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${dark ? 'bg-slate-800 text-slate-400 hover:bg-slate-700' : 'bg-white text-slate-500 hover:bg-slate-50 border border-slate-200'}`}
                >
                  <RefreshCw className={`w-3 h-3 ${activityLoading ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {activityLoading && activity.length === 0 && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-orange-500" />
                </div>
              )}

              {activityError && (
                <div className={`m-3 flex items-center gap-2 p-3 rounded text-xs ${dark ? 'bg-red-500/10 text-red-400' : 'bg-red-50 text-red-600'}`}>
                  <XCircle className="w-3.5 h-3.5" /> {activityError}
                </div>
              )}

              {!activityLoading && !activityError && activity.length === 0 && (
                <div className={`text-center py-8 text-sm ${dark ? 'text-slate-500' : 'text-slate-400'}`}>
                  No activity recorded for this actor.
                </div>
              )}

              {activity.map((item) => (
                <ActivityRow key={item.id} item={item} dark={dark} />
              ))}

              {activityCursor && (
                <div className={`p-3 text-center border-t ${dark ? 'border-slate-800' : 'border-slate-100'}`}>
                  <button
                    id="activity-load-more"
                    onClick={() => loadActivity(activityCursor)}
                    disabled={activityLoading}
                    className={`text-xs px-3 py-1.5 rounded transition-colors ${dark ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                  >
                    {activityLoading ? 'Loading…' : 'Load more'}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
