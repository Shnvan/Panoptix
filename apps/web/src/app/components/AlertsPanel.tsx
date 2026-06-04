/* ── AlertsPanel ──
 * Wired to real backend alert APIs:
 *   GET  /api/v1/admin/alerts
 *   GET  /api/v1/admin/alerts/{alert_id}
 *   POST /api/v1/admin/alerts/{alert_id}/acknowledge
 *   POST /api/v1/admin/alerts/{alert_id}/resolve
 *
 * Guardrails:
 *   - No browser notification push or email delivery.
 *   - Alert records and statuses only — display only.
 */

import { useMemo, useState } from 'react';
import {
  AlertTriangle, XCircle, Info, Clock, AlertCircle,
  CheckCircle2, ShieldAlert, ChevronDown, ChevronUp,
  RefreshCw, Loader2, Filter,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { useAdminAlerts } from '../../lib/hooks';
import type { AdminAlert, AlertCategory, AlertSeverity, AlertStatus } from '../../lib/types';

// ── Severity config ──

type SeverityConfig = {
  icon: typeof AlertCircle;
  badge: string;
  border: string;
  bg: string;
  text: string;
};

const SEVERITY_CONFIG: Record<AlertSeverity, SeverityConfig> = {
  critical: {
    icon: XCircle,
    badge: 'bg-red-500/20 text-red-400 border border-red-500/40',
    border: 'border-red-500/30',
    bg: 'bg-red-500/10',
    text: 'text-red-400',
  },
  high: {
    icon: AlertTriangle,
    badge: 'bg-orange-500/20 text-orange-400 border border-orange-500/40',
    border: 'border-orange-500/30',
    bg: 'bg-orange-500/10',
    text: 'text-orange-400',
  },
  medium: {
    icon: AlertCircle,
    badge: 'bg-amber-500/20 text-amber-400 border border-amber-500/40',
    border: 'border-amber-500/30',
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
  },
  low: {
    icon: Info,
    badge: 'bg-blue-500/20 text-blue-400 border border-blue-500/40',
    border: 'border-blue-500/30',
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
  },
  informational: {
    icon: Info,
    badge: 'bg-neutral-500/20 text-neutral-400 border border-neutral-500/40',
    border: 'border-neutral-500/30',
    bg: 'bg-neutral-500/10',
    text: 'text-neutral-400',
  },
};

const STATUS_BADGE: Record<AlertStatus, string> = {
  open: 'bg-red-500/15 text-red-400 border border-red-500/30',
  acknowledged: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
  resolved: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
};

const CATEGORY_LABEL: Record<string, string> = {
  security: 'Security',
  operations: 'Operations',
  compliance: 'Compliance',
  availability: 'Availability',
};

function fmt(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

function relativeTime(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Alert Row ──

interface AlertRowProps {
  alert: AdminAlert;
  expanded: boolean;
  onToggle: () => void;
  onAcknowledge: () => Promise<void>;
  onResolve: () => Promise<void>;
  dark: boolean;
  compact: boolean;
}

function AlertRow({ alert, expanded, onToggle, onAcknowledge, onResolve, dark, compact }: AlertRowProps) {
  const [actioning, setActioning] = useState<string | null>(null);
  const cfg = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.informational;
  const Icon = cfg.icon;

  const handle = async (action: 'ack' | 'resolve', fn: () => Promise<void>) => {
    setActioning(action);
    try { await fn(); } catch { /* ApiError shown via refetch */ }
    finally { setActioning(null); }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`border rounded-lg overflow-hidden transition-colors ${
        dark
          ? `bg-neutral-900/60 ${cfg.border}`
          : `bg-white ${cfg.border} border`
      }`}
    >
      {/* Header row */}
      <button
        id={`alert-row-${alert.alert_id}`}
        className={`w-full text-left px-4 flex items-start gap-3 hover:bg-white/5 transition-colors ${compact ? 'py-2' : 'py-3'}`}
        onClick={onToggle}
        aria-expanded={expanded}
      >
        {/* Severity icon */}
        <div className={`mt-0.5 rounded flex items-center justify-center flex-shrink-0 ${cfg.bg} ${compact ? 'w-7 h-7' : 'w-8 h-8'}`}>
          <Icon className={`${compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} ${cfg.text}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full uppercase tracking-wide ${cfg.badge}`}>
              {alert.severity}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${dark ? 'border-neutral-700 text-neutral-400' : 'border-neutral-200 text-neutral-500'}`}>
              {CATEGORY_LABEL[alert.category] ?? alert.category}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_BADGE[alert.status]}`}>
              {alert.status}
            </span>
          </div>
          <h4 className={`font-semibold text-sm leading-snug ${dark ? 'text-white' : 'text-neutral-900'}`}>
            {alert.title}
          </h4>
          <p className={`text-xs mt-0.5 ${compact ? 'line-clamp-1' : ''} ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>
            {alert.message}
          </p>
        </div>

        {/* Timestamp + chevron */}
        <div className={`flex flex-col items-end gap-1 flex-shrink-0 ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>
          <div className="flex items-center gap-1 text-xs">
            <Clock className="w-3 h-3" />
            <span>{relativeTime(alert.created_at)}</span>
          </div>
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className={`border-t px-4 py-3 space-y-3 ${dark ? 'border-neutral-800' : 'border-neutral-100'}`}
          >
            {/* Meta grid */}
            <div className={`grid grid-cols-2 gap-2 text-xs ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>
              <div>
                <span className="font-medium">Source</span>
                <p className="mt-0.5 truncate">{alert.source}</p>
              </div>
              {alert.resource && (
                <div>
                  <span className="font-medium">Resource</span>
                  <p className="mt-0.5 truncate">{alert.resource}</p>
                </div>
              )}
              {alert.actor_type && (
                <div>
                  <span className="font-medium">Actor</span>
                  <p className="mt-0.5">{alert.actor_type}{alert.actor_id ? ` · ${alert.actor_id.slice(0, 8)}…` : ''}</p>
                </div>
              )}
              <div>
                <span className="font-medium">Created</span>
                <p className="mt-0.5">{fmt(alert.created_at)}</p>
              </div>
              {alert.acknowledged_at && (
                <div>
                  <span className="font-medium">Acknowledged</span>
                  <p className="mt-0.5">{fmt(alert.acknowledged_at)}</p>
                </div>
              )}
              {alert.resolved_at && (
                <div>
                  <span className="font-medium">Resolved</span>
                  <p className="mt-0.5">{fmt(alert.resolved_at)}</p>
                </div>
              )}
            </div>

            {/* Actions */}
            {alert.status !== 'resolved' && (
              <div className="flex items-center gap-2 pt-1">
                {alert.status === 'open' && (
                  <button
                    id={`alert-ack-${alert.alert_id}`}
                    disabled={actioning !== null}
                    onClick={() => handle('ack', onAcknowledge)}
                    className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded transition-colors disabled:opacity-50 ${
                      dark
                        ? 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/30'
                        : 'bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200'
                    }`}
                  >
                    {actioning === 'ack'
                      ? <Loader2 className="w-3 h-3 animate-spin" />
                      : <CheckCircle2 className="w-3 h-3" />}
                    Acknowledge
                  </button>
                )}
                <button
                  id={`alert-resolve-${alert.alert_id}`}
                  disabled={actioning !== null}
                  onClick={() => handle('resolve', onResolve)}
                  className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded transition-colors disabled:opacity-50 ${
                    dark
                      ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/30'
                      : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                  }`}
                >
                  {actioning === 'resolve'
                    ? <Loader2 className="w-3 h-3 animate-spin" />
                    : <CheckCircle2 className="w-3 h-3" />}
                  Resolve
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Main Panel ──

const STATUS_TABS: { label: string; value?: string }[] = [
  { label: 'All' },
  { label: 'Open', value: 'open' },
  { label: 'Acknowledged', value: 'acknowledged' },
  { label: 'Resolved', value: 'resolved' },
];

const SEVERITY_OPTIONS: { label: string; value?: AlertSeverity }[] = [
  { label: 'All Severities' },
  { label: 'Informational', value: 'informational' },
  { label: 'Low', value: 'low' },
  { label: 'Medium', value: 'medium' },
  { label: 'High', value: 'high' },
  { label: 'Critical', value: 'critical' },
];

const CATEGORY_OPTIONS: { label: string; value?: AlertCategory }[] = [
  { label: 'All Categories' },
  { label: 'Security', value: 'security' },
  { label: 'Operations', value: 'operations' },
  { label: 'Compliance', value: 'compliance' },
  { label: 'Availability', value: 'availability' },
];

export function AlertsPanel() {
  const { theme } = useTheme();
  const dark = theme === 'dark';

  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [severityFilter, setSeverityFilter] = useState<string | undefined>(undefined);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [density, setDensity] = useState<'comfortable' | 'compact'>('compact');
  const [hideVisitorContinue, setHideVisitorContinue] = useState(true);

  const { alerts, loading, error, hasMore, loadMore, refetch, acknowledge, resolve } =
    useAdminAlerts(statusFilter, severityFilter, categoryFilter);

  const openCount = alerts.filter((a) => a.status === 'open').length;
  const criticalCount = alerts.filter((a) => a.severity === 'critical' && a.status !== 'resolved').length;
  const visibleAlerts = useMemo(() => {
    if (!hideVisitorContinue) return alerts;
    return alerts.filter((alert) => {
      const haystack = `${alert.title} ${alert.message} ${alert.source}`.toLowerCase();
      return !haystack.includes('visitor continued to secure sign-in');
    });
  }, [alerts, hideVisitorContinue]);
  const hiddenNoiseCount = alerts.length - visibleAlerts.length;

  return (
    <div className="space-y-4">
      {/* Section header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${dark ? 'bg-red-500/20' : 'bg-red-50'}`}>
            <ShieldAlert className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h3 className={`font-semibold ${dark ? 'text-white' : 'text-neutral-900'}`}>
              Active Alerts
            </h3>
            <p className={`text-sm ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>
              {loading ? 'Loading...' : `${visibleAlerts.length} shown${hiddenNoiseCount > 0 ? `, ${hiddenNoiseCount} hidden` : ''}${openCount > 0 ? `, ${openCount} open` : ''}${criticalCount > 0 ? `, ${criticalCount} critical` : ''}`}
            </p>
          </div>
        </div>
        <button
          id="alerts-refresh"
          onClick={refetch}
          disabled={loading}
          className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 ${
            dark
              ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'
              : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
          }`}
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Status filter tabs */}
      <div className={`flex items-center gap-1 border-b ${dark ? 'border-neutral-800' : 'border-neutral-200'}`}>
        <Filter className={`w-3.5 h-3.5 mr-1 ${dark ? 'text-neutral-500' : 'text-neutral-400'}`} />
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.label}
            id={`alert-tab-${tab.label.toLowerCase()}`}
            onClick={() => { setStatusFilter(tab.value); setExpandedId(null); }}
            className={`text-xs px-3 py-2 border-b-2 transition-colors ${
              statusFilter === tab.value
                ? 'border-orange-500 text-orange-500'
                : `border-transparent ${dark ? 'text-neutral-400 hover:text-neutral-200' : 'text-neutral-500 hover:text-neutral-700'}`
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Severity/category filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className={`inline-flex rounded-lg border p-1 ${dark ? 'border-neutral-700 bg-neutral-900' : 'border-neutral-200 bg-neutral-100'}`}>
          {(['compact', 'comfortable'] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setDensity(mode)}
              className={`px-3 py-1.5 text-xs rounded-md capitalize ${density === mode ? 'bg-orange-500 text-white' : dark ? 'text-neutral-400 hover:bg-neutral-800' : 'text-neutral-600 hover:bg-white'}`}
            >
              {mode}
            </button>
          ))}
        </div>
        <label className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${dark ? 'border-neutral-700 bg-neutral-900 text-neutral-300' : 'border-neutral-200 bg-white text-neutral-700'}`}>
          <input
            type="checkbox"
            checked={hideVisitorContinue}
            onChange={(event) => setHideVisitorContinue(event.target.checked)}
            className="h-3.5 w-3.5"
          />
          Hide visitor sign-in noise
        </label>
        <select
          id="alert-severity-filter"
          aria-label="Alert severity filter"
          value={severityFilter ?? ''}
          onChange={(e) => { setSeverityFilter(e.target.value || undefined); setExpandedId(null); }}
          className={`text-xs px-3 py-2 rounded-lg border outline-none transition-colors ${
            dark
              ? 'bg-neutral-900 border-neutral-700 text-neutral-300 focus:border-orange-500/50'
              : 'bg-white border-neutral-200 text-neutral-700 focus:border-orange-400'
          }`}
        >
          {SEVERITY_OPTIONS.map((option) => (
            <option key={option.value ?? 'all'} value={option.value ?? ''}>{option.label}</option>
          ))}
        </select>
        <select
          id="alert-category-filter"
          aria-label="Alert category filter"
          value={categoryFilter ?? ''}
          onChange={(e) => { setCategoryFilter(e.target.value || undefined); setExpandedId(null); }}
          className={`text-xs px-3 py-2 rounded-lg border outline-none transition-colors ${
            dark
              ? 'bg-neutral-900 border-neutral-700 text-neutral-300 focus:border-orange-500/50'
              : 'bg-white border-neutral-200 text-neutral-700 focus:border-orange-400'
          }`}
        >
          {CATEGORY_OPTIONS.map((option) => (
            <option key={option.value ?? 'all'} value={option.value ?? ''}>{option.label}</option>
          ))}
        </select>
        {(severityFilter || categoryFilter) && (
          <button
            id="alert-clear-extra-filters"
            onClick={() => { setSeverityFilter(undefined); setCategoryFilter(undefined); setExpandedId(null); }}
            className={`text-xs px-3 py-2 rounded-lg transition-colors ${
              dark ? 'bg-neutral-800 text-neutral-400 hover:text-neutral-200' : 'bg-neutral-100 text-neutral-500 hover:text-neutral-700'
            }`}
          >
            Clear alert filters
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${dark ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-red-50 text-red-600 border border-red-200'}`}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && alerts.length === 0 && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={`h-20 rounded-lg animate-pulse ${dark ? 'bg-neutral-800/50' : 'bg-neutral-100'}`} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && visibleAlerts.length === 0 && (
        <div className={`text-center py-12 border rounded-lg ${dark ? 'bg-neutral-900/50 border-neutral-700/50' : 'bg-neutral-50 border-neutral-200'}`}>
          <CheckCircle2 className={`w-12 h-12 mx-auto mb-3 ${dark ? 'text-emerald-500' : 'text-emerald-400'}`} />
          <h4 className={`font-medium mb-1 ${dark ? 'text-white' : 'text-neutral-900'}`}>
            {alerts.length > 0 ? 'Only hidden noise alerts match' : statusFilter ? `No ${statusFilter} alerts` : 'No alerts'}
          </h4>
          <p className={`text-sm ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>
            {alerts.length > 0
              ? 'Turn off the visitor noise toggle to inspect those records.'
              : statusFilter === 'open'
                ? 'All clear - no open alerts at this time.'
                : 'No alerts match the current filter.'}
          </p>
        </div>
      )}

      {/* Alert list */}
      {visibleAlerts.length > 0 && (
        <div className="space-y-2">
          {visibleAlerts.map((alert) => (
            <AlertRow
              key={alert.alert_id}
              alert={alert}
              expanded={expandedId === alert.alert_id}
              onToggle={() => setExpandedId((id) => (id === alert.alert_id ? null : alert.alert_id))}
              onAcknowledge={async () => { await acknowledge(alert.alert_id); }}
              onResolve={async () => { await resolve(alert.alert_id); }}
              dark={dark}
              compact={density === 'compact'}
            />
          ))}
        </div>
      )}

      {/* Load more */}
      {hasMore && (
        <div className="text-center pt-2">
          <button
            id="alerts-load-more"
            onClick={loadMore}
            disabled={loading}
            className={`text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-50 ${
              dark
                ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700'
                : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
            }`}
          >
            {loading ? (
              <span className="flex items-center gap-2"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading...</span>
            ) : 'Load more'}
          </button>
        </div>
      )}
    </div>
  );
}
