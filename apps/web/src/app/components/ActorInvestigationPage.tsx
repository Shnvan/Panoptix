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
  Activity, KeyRound,
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
  { value: 'service_token_monitor', label: 'Service Token', icon: KeyRound },
];

const SYSTEM_ACTOR_TYPES = new Set(['system', 'break_glass', 'service_token_monitor']);

const SEVERITY_OPTIONS = ['', 'informational', 'low', 'medium', 'high', 'critical'];
const CATEGORY_OPTIONS = ['', 'authentication', 'authorization', 'data_access', 'admin', 'system', 'compliance'];
const OUTCOME_OPTIONS = ['', 'success', 'failure', 'denied', 'error'];

const SEVERITY_CLASS: Record<string, string> = {
  critical: 'text-red-400',
  high: 'text-orange-400',
  medium: 'text-amber-400',
  low: 'text-blue-400',
  informational: 'text-neutral-400',
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
    <div className={`border rounded-lg overflow-hidden ${dark ? 'border-neutral-700/50 bg-neutral-900/60' : 'border-neutral-200 bg-white'}`}>
      <div className={`flex items-center gap-2 px-4 py-3 border-b ${dark ? 'border-neutral-700/50' : 'border-neutral-100'}`}>
        <Icon className={`w-4 h-4 ${dark ? 'text-orange-400' : 'text-orange-600'}`} />
        <h4 className={`text-sm font-semibold ${dark ? 'text-white' : 'text-neutral-900'}`}>{title}</h4>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function KV({ label, value, dark }: { label: string; value: React.ReactNode; dark: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <span className={`text-xs flex-shrink-0 w-36 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>{label}</span>
      <span className={`text-xs text-right break-all ${dark ? 'text-neutral-200' : 'text-neutral-800'}`}>{value ?? '—'}</span>
    </div>
  );
}

// ── Activity row ──

function ActivityRow({ item, dark }: { item: ActorActivityItem; dark: boolean }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`border-b ${dark ? 'border-neutral-800' : 'border-neutral-100'}`}>
      <button
        className={`w-full text-left flex items-center gap-3 px-4 py-2.5 transition-colors ${dark ? 'hover:bg-neutral-800/40' : 'hover:bg-neutral-50'}`}
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-0.5">
            <span className={`text-xs font-medium ${SEVERITY_CLASS[item.event_severity ?? ''] ?? 'text-neutral-400'}`}>
              {item.event_severity ?? '?'}
            </span>
            {item.event_outcome && (
              <span className={`text-xs px-1.5 py-0.5 rounded border ${OUTCOME_BADGE[item.event_outcome] ?? 'bg-neutral-500/10 text-neutral-400 border-neutral-500/20'}`}>
                {item.event_outcome}
              </span>
            )}
            {item.event_category && (
              <span className={`text-xs ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>{item.event_category}</span>
            )}
          </div>
          <p className={`text-xs truncate font-mono ${dark ? 'text-neutral-300' : 'text-neutral-700'}`}>{item.action}</p>
          {item.resource && (
            <p className={`text-xs truncate ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>{item.resource}</p>
          )}
        </div>
        <div className={`flex-shrink-0 text-xs ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>
          {item.ts ? new Date(item.ts).toLocaleTimeString('en-US', { hour12: false }) : '—'}
        </div>
        {item.payload ? (
          expanded ? <ChevronUp className="w-3.5 h-3.5 flex-shrink-0 text-neutral-500" /> : <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 text-neutral-500" />
        ) : null}
      </button>
      <AnimatePresence>
        {expanded && item.payload && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className={`px-4 pb-3 border-t ${dark ? 'border-neutral-800' : 'border-neutral-100'}`}
          >
            <pre className={`text-xs mt-2 p-2 rounded overflow-auto max-h-40 ${dark ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-50 text-neutral-700'}`}>
              {JSON.stringify(item.payload, null, 2)}
            </pre>
            <div className={`flex gap-4 mt-2 text-xs ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>
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
      <div className={`flex items-center gap-3 p-4 border rounded-lg ${dark ? 'border-neutral-700/50 bg-neutral-900/60' : 'border-neutral-200 bg-white'}`}>
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${dark ? 'bg-orange-500/20' : 'bg-orange-50'}`}>
          <Icon className="w-5 h-5 text-orange-400" />
        </div>
        <div>
          <p className={`font-semibold ${dark ? 'text-white' : 'text-neutral-900'}`}>
            {profile.email ?? profile.name ?? actorCfg.label}
          </p>
          <p className={`text-xs font-mono ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>
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
              : 'bg-neutral-500/15 text-neutral-400 border-neutral-500/30'
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
              <div key={label} className={`text-center p-3 rounded-lg ${dark ? 'bg-neutral-800/50' : 'bg-neutral-50'}`}>
                <p className={`text-xl font-bold ${cls}`}>{val}</p>
                <p className={`text-xs mt-1 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>{label}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* User-specific fields */}
      {profile.actor_type === 'user' && (
        <Section title="User Profile" icon={User} dark={dark}>
          <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
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
          <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
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
              <div key={i} className={`flex items-center gap-3 p-2.5 rounded text-xs ${dark ? 'bg-neutral-800/50' : 'bg-neutral-50'}`}>
                <span className={`font-mono ${dark ? 'text-neutral-300' : 'text-neutral-700'}`}>{login.ip ?? '—'}</span>
                <span className={`flex-1 truncate ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>{login.ua ?? '—'}</span>
                <span className={dark ? 'text-neutral-500' : 'text-neutral-400'}>{fmt(login.ts)}</span>
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
  const [actionFilter, setActionFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [outcomeFilter, setOutcomeFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('');
  const [sessionFilter, setSessionFilter] = useState('');
  const [tsFromFilter, setTsFromFilter] = useState('');
  const [tsToFilter, setTsToFilter] = useState('');

  const [profile, setProfile] = useState<ActorProfileResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [activity, setActivity] = useState<ActorActivityItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityCursor, setActivityCursor] = useState<string | null>(null);

  const resolvedId = SYSTEM_ACTOR_TYPES.has(actorType) ? 'none' : actorId;

  const loadProfile = useCallback(async () => {
    if (!resolvedId && !SYSTEM_ACTOR_TYPES.has(actorType)) return;
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
    if (!resolvedId && !SYSTEM_ACTOR_TYPES.has(actorType)) return;
    setActivityLoading(true);
    setActivityError(null);
    try {
      const data = await api.getActorActivity(actorType, resolvedId || 'none', {
        cursor,
        limit: 50,
        action: actionFilter || undefined,
        severity: severityFilter || undefined,
        category: categoryFilter || undefined,
        outcome: outcomeFilter || undefined,
        resource: resourceFilter || undefined,
        session_id: sessionFilter || undefined,
        ts_from: tsFromFilter ? new Date(tsFromFilter).toISOString() : undefined,
        ts_to: tsToFilter ? new Date(tsToFilter).toISOString() : undefined,
      });
      setActivity((prev) => cursor ? [...prev, ...data.items] : data.items);
      setActivityCursor(data.next_cursor);
    } catch (err) {
      setActivityError(err instanceof ApiError ? err.detail : 'Failed to load activity');
    } finally {
      setActivityLoading(false);
    }
  }, [
    actorType,
    resolvedId,
    actionFilter,
    severityFilter,
    categoryFilter,
    outcomeFilter,
    resourceFilter,
    sessionFilter,
    tsFromFilter,
    tsToFilter,
  ]);

  const handleSearch = () => {
    const isSystemActor = SYSTEM_ACTOR_TYPES.has(actorType);
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

  const isSystemActor = SYSTEM_ACTOR_TYPES.has(actorType);

  const clearActivityFilters = () => {
    setActionFilter('');
    setSeverityFilter('');
    setCategoryFilter('');
    setOutcomeFilter('');
    setResourceFilter('');
    setSessionFilter('');
    setTsFromFilter('');
    setTsToFilter('');
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${dark ? 'bg-purple-500/20' : 'bg-purple-50'}`}>
          <UserSearch className="w-5 h-5 text-purple-400" />
        </div>
        <div>
          <h3 className={`font-semibold ${dark ? 'text-white' : 'text-neutral-900'}`}>Actor Investigation</h3>
          <p className={`text-sm ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>Profile and activity timeline for users, gateways, and system actors</p>
        </div>
      </div>

      {/* Search form */}
      <div className={`border rounded-lg p-4 ${dark ? 'border-neutral-700/50 bg-neutral-900/60' : 'border-neutral-200 bg-white'}`}>
        <div className="flex flex-wrap gap-3 items-end">
          {/* Actor type */}
          <div className="flex-shrink-0">
            <label className={`block text-xs mb-1.5 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>Actor type</label>
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
                          ? 'bg-neutral-800 text-neutral-400 border-neutral-700 hover:border-neutral-600'
                          : 'bg-neutral-50 text-neutral-500 border-neutral-200 hover:border-neutral-300'
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
              <label className={`block text-xs mb-1.5 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>
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
                    ? 'bg-neutral-800 border-neutral-700 text-neutral-200 placeholder-neutral-600 focus:border-orange-500/50'
                    : 'bg-white border-neutral-200 text-neutral-800 placeholder-neutral-300 focus:border-orange-400'
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
              className={`flex items-center gap-1.5 text-sm px-3 py-2 rounded transition-colors ${dark ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'}`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${profileLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Activity filters */}
      <div className={`border rounded-lg p-4 ${dark ? 'border-neutral-700/50 bg-neutral-900/60' : 'border-neutral-200 bg-white'}`}>
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            <h4 className={`text-sm font-semibold ${dark ? 'text-white' : 'text-neutral-900'}`}>Activity Filters</h4>
            <p className={`text-xs ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>Applied to the actor activity endpoint.</p>
          </div>
          <button
            id="actor-clear-filters"
            onClick={clearActivityFilters}
            className={`text-xs px-3 py-1.5 rounded border transition-colors ${
              dark
                ? 'border-neutral-700 text-neutral-400 hover:text-neutral-200 hover:border-neutral-600'
                : 'border-neutral-200 text-neutral-500 hover:text-neutral-700 hover:border-neutral-300'
            }`}
          >
            Clear Filters
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <input
            id="actor-action-filter"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder="Action exact match"
            className={`text-xs px-3 py-2 rounded border outline-none ${dark ? 'bg-neutral-800 border-neutral-700 text-neutral-200 placeholder-neutral-600' : 'bg-white border-neutral-200 text-neutral-800 placeholder-neutral-400'}`}
          />
          <select
            id="actor-severity-filter"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className={`text-xs px-3 py-2 rounded border outline-none ${dark ? 'bg-neutral-800 border-neutral-700 text-neutral-200' : 'bg-white border-neutral-200 text-neutral-800'}`}
          >
            {SEVERITY_OPTIONS.map((value) => <option key={value || 'all'} value={value}>{value || 'All severities'}</option>)}
          </select>
          <select
            id="actor-category-filter"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className={`text-xs px-3 py-2 rounded border outline-none ${dark ? 'bg-neutral-800 border-neutral-700 text-neutral-200' : 'bg-white border-neutral-200 text-neutral-800'}`}
          >
            {CATEGORY_OPTIONS.map((value) => <option key={value || 'all'} value={value}>{value ? value.replace(/_/g, ' ') : 'All categories'}</option>)}
          </select>
          <select
            id="actor-outcome-filter"
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            className={`text-xs px-3 py-2 rounded border outline-none ${dark ? 'bg-neutral-800 border-neutral-700 text-neutral-200' : 'bg-white border-neutral-200 text-neutral-800'}`}
          >
            {OUTCOME_OPTIONS.map((value) => <option key={value || 'all'} value={value}>{value || 'All outcomes'}</option>)}
          </select>
          <input
            id="actor-resource-filter"
            value={resourceFilter}
            onChange={(e) => setResourceFilter(e.target.value)}
            placeholder="Resource exact match"
            className={`text-xs px-3 py-2 rounded border outline-none ${dark ? 'bg-neutral-800 border-neutral-700 text-neutral-200 placeholder-neutral-600' : 'bg-white border-neutral-200 text-neutral-800 placeholder-neutral-400'}`}
          />
          <input
            id="actor-session-filter"
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            placeholder="Session UUID"
            className={`text-xs px-3 py-2 rounded border outline-none ${dark ? 'bg-neutral-800 border-neutral-700 text-neutral-200 placeholder-neutral-600' : 'bg-white border-neutral-200 text-neutral-800 placeholder-neutral-400'}`}
          />
          <input
            id="actor-ts-from-filter"
            type="datetime-local"
            value={tsFromFilter}
            onChange={(e) => setTsFromFilter(e.target.value)}
            className={`text-xs px-3 py-2 rounded border outline-none ${dark ? 'bg-neutral-800 border-neutral-700 text-neutral-200' : 'bg-white border-neutral-200 text-neutral-800'}`}
          />
          <input
            id="actor-ts-to-filter"
            type="datetime-local"
            value={tsToFilter}
            onChange={(e) => setTsToFilter(e.target.value)}
            className={`text-xs px-3 py-2 rounded border outline-none ${dark ? 'bg-neutral-800 border-neutral-700 text-neutral-200' : 'bg-white border-neutral-200 text-neutral-800'}`}
          />
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
        <div className={`text-center py-12 border rounded-lg ${dark ? 'border-neutral-700/50 border-dashed' : 'border-neutral-200 border-dashed'}`}>
          <Info className={`w-10 h-10 mx-auto mb-2 ${dark ? 'text-neutral-700' : 'text-neutral-300'}`} />
          <p className={`text-sm ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>
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
            <div className={`border rounded-lg overflow-hidden ${dark ? 'border-neutral-700/50' : 'border-neutral-200'}`}>
              <div className={`flex items-center justify-between px-4 py-3 border-b ${dark ? 'border-neutral-700/50 bg-neutral-900/60' : 'border-neutral-100 bg-neutral-50'}`}>
                <div className="flex items-center gap-2">
                  <Activity className={`w-4 h-4 ${dark ? 'text-orange-400' : 'text-orange-600'}`} />
                  <span className={`text-sm font-semibold ${dark ? 'text-white' : 'text-neutral-900'}`}>Activity Timeline</span>
                  <span className={`text-xs ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>({activity.length} events)</span>
                </div>
                <button
                  id="activity-refresh"
                  onClick={() => { setActivity([]); loadActivity(); }}
                  disabled={activityLoading}
                  className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${dark ? 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700' : 'bg-white text-neutral-500 hover:bg-neutral-50 border border-neutral-200'}`}
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
                <div className={`text-center py-8 text-sm ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>
                  No activity recorded for this actor.
                </div>
              )}

              {activity.map((item) => (
                <ActivityRow key={item.id} item={item} dark={dark} />
              ))}

              {activityCursor && (
                <div className={`p-3 text-center border-t ${dark ? 'border-neutral-800' : 'border-neutral-100'}`}>
                  <button
                    id="activity-load-more"
                    onClick={() => loadActivity(activityCursor)}
                    disabled={activityLoading}
                    className={`text-xs px-3 py-1.5 rounded transition-colors ${dark ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'}`}
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
