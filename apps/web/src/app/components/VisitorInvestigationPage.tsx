/* ── VisitorInvestigationPage ──
 * Admin visitor investigation UI.
 * List: GET /api/v1/admin/visitor-visits
 * Detail: GET /api/v1/admin/visitor-visits/{visit_id}
 *
 * Guardrails (from FRONTEND_PRODUCTION_TODO.md):
 *  - Do NOT display raw Ipregistry payloads, SDP/candidate strings, canvas/audio fingerprints,
 *    exact coordinates, or broad fingerprint dumps.
 *  - Display structured sections only as documented in the data contract.
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import {
  Users, Globe, Monitor, Wifi, Radio, Clock, Shield,
  AlertTriangle, ChevronRight, X, Loader2, RefreshCw,
  CheckCircle2, XCircle, Info, Link2, MapPin, Search,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { api, ApiError } from '../../lib/api';
import type { VisitorVisitSummary, VisitorVisitDetail } from '../../lib/types';

// ── Helpers ──

function fmt(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function boolBadge(value: boolean | null | undefined, dark: boolean) {
  if (value === null || value === undefined) return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${dark ? 'bg-neutral-700 text-neutral-400' : 'bg-neutral-100 text-neutral-400'}`}>—</span>
  );
  return value
    ? <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30">Yes</span>
    : <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">No</span>;
}

// ── Section card ──

function Section({ title, icon: Icon, children, dark }: {
  title: string;
  icon: typeof Globe;
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
      <span className={`text-xs flex-shrink-0 w-40 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>{label}</span>
      <span className={`text-xs text-right break-all ${dark ? 'text-neutral-200' : 'text-neutral-800'}`}>{value ?? '—'}</span>
    </div>
  );
}

// ── Detail drawer ──

function VisitDetailDrawer({ visitId, dark, onClose }: { visitId: string; dark: boolean; onClose: () => void }) {
  const [detail, setDetail] = useState<VisitorVisitDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getAdminVisitorVisit(visitId)
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError ? err.detail : 'Failed to load visit detail'))
      .finally(() => setLoading(false));
  }, [visitId]);

  const rc = detail?.risk_context;
  const riskFlags = rc
    ? Object.entries(rc)
        .filter(([k, v]) => k !== 'repeat_visitor_count' && v === true)
        .map(([k]) => k.replace(/_/g, ' '))
    : [];

  return (
    <motion.div
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 40 }}
      transition={{ duration: 0.2 }}
      className={`fixed inset-y-0 right-0 w-full max-w-xl z-50 flex flex-col shadow-2xl border-l overflow-y-auto ${
        dark ? 'bg-neutral-950 border-neutral-700' : 'bg-white border-neutral-200'
      }`}
    >
      {/* Drawer header */}
      <div className={`sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b ${dark ? 'bg-neutral-950 border-neutral-700' : 'bg-white border-neutral-200'}`}>
        <div>
          <h3 className={`font-semibold ${dark ? 'text-white' : 'text-neutral-900'}`}>Visitor Detail</h3>
          <p className={`text-xs font-mono ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>{visitId.slice(0, 16)}…</p>
        </div>
        <button id="visit-detail-close" onClick={onClose} className={`p-1.5 rounded-lg transition-colors ${dark ? 'hover:bg-neutral-800 text-neutral-400' : 'hover:bg-neutral-100 text-neutral-500'}`}>
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 p-5 space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
          </div>
        )}

        {error && (
          <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${dark ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-red-50 text-red-600 border border-red-200'}`}>
            <XCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {detail && (
          <>
            {/* Risk summary banner */}
            {riskFlags.length > 0 && (
              <div className={`flex items-start gap-2 p-3 rounded-lg border ${dark ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-amber-50 border-amber-200 text-amber-700'}`}>
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">Risk flags detected</p>
                  <ul className="mt-1 text-xs space-y-0.5 list-disc list-inside">
                    {riskFlags.map((f) => <li key={f}>{f}</li>)}
                  </ul>
                </div>
              </div>
            )}

            {/* 1 — Visitor Summary */}
            <Section title="Visitor Summary" icon={Users} dark={dark}>
              <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                <KV label="Visit ID" value={<span className="font-mono text-xs">{detail.visit_id}</span>} dark={dark} />
                <KV label="Collected" value={fmt(detail.collected_at)} dark={dark} />
                <KV label="Page path" value={detail.page_path} dark={dark} />
                <KV label="Notice version" value={detail.notice_version} dark={dark} />
                <KV label="Logged in" value={detail.login.logged_in ? <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" /> : '—'} dark={dark} />
                {detail.login.logged_in_at && <KV label="Login time" value={fmt(detail.login.logged_in_at)} dark={dark} />}
              </div>
            </Section>

            {/* 2 — IP & Location */}
            <Section title="IP & Location" icon={MapPin} dark={dark}>
              <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                <KV label="IP" value={detail.ip_details.ip ?? '—'} dark={dark} />
                <KV label="Enrichment status" value={detail.ip_details.status} dark={dark} />
                <KV label="Provider" value={detail.ip_details.provider ?? '—'} dark={dark} />
                {detail.ip_details.location && (
                  <>
                    <KV label="Country" value={`${detail.ip_details.location.country_name ?? '—'} (${detail.ip_details.location.country_code ?? '—'})`} dark={dark} />
                    <KV label="City" value={detail.ip_details.location.city ?? '—'} dark={dark} />
                    <KV label="IP timezone" value={detail.ip_details.location.timezone ?? '—'} dark={dark} />
                  </>
                )}
              </div>
            </Section>

            {/* 3 — Device & Browser */}
            <Section title="Device & Browser" icon={Monitor} dark={dark}>
              <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                <KV label="Language" value={detail.browser_context.language ?? '—'} dark={dark} />
                <KV label="Languages" value={detail.browser_context.languages?.join(', ') ?? '—'} dark={dark} />
                <KV label="Timezone" value={detail.browser_context.timezone ?? '—'} dark={dark} />
                <KV label="Color scheme" value={detail.browser_context.color_scheme ?? '—'} dark={dark} />
                <KV label="Screen" value={
                  detail.browser_context.screen
                    ? `${detail.browser_context.screen.width}×${detail.browser_context.screen.height}`
                    : '—'
                } dark={dark} />
                <KV label="Viewport" value={
                  detail.browser_context.viewport
                    ? `${detail.browser_context.viewport.width}×${detail.browser_context.viewport.height}`
                    : '—'
                } dark={dark} />
                <KV label="Pixel ratio" value={detail.browser_context.device_pixel_ratio ?? '—'} dark={dark} />
                <KV label="Touch" value={detail.browser_context.touch_supported != null ? String(detail.browser_context.touch_supported) : '—'} dark={dark} />
                <KV label="Cookies enabled" value={detail.browser_context.cookies_enabled != null ? String(detail.browser_context.cookies_enabled) : '—'} dark={dark} />
                <KV label="Do Not Track" value={detail.browser_context.privacy?.do_not_track ?? '—'} dark={dark} />
                <KV label="Global Privacy Control" value={detail.browser_context.privacy?.global_privacy_control != null ? String(detail.browser_context.privacy.global_privacy_control) : '—'} dark={dark} />
              </div>
            </Section>

            {/* 4 — Browser Network Hints */}
            <Section title="Browser Network Hints" icon={Wifi} dark={dark}>
              <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                <KV label="Effective type" value={detail.network_context.effective_type ?? '—'} dark={dark} />
                <KV label="Downlink" value={detail.network_context.downlink_mbps != null ? `${detail.network_context.downlink_mbps} Mbps` : '—'} dark={dark} />
                <KV label="RTT" value={detail.network_context.rtt_ms != null ? `${detail.network_context.rtt_ms} ms` : '—'} dark={dark} />
                <KV label="Save data" value={detail.network_context.save_data != null ? String(detail.network_context.save_data) : '—'} dark={dark} />
              </div>
            </Section>

            {/* 5 — WebRTC Check */}
            <Section title="WebRTC Check" icon={Radio} dark={dark}>
              <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                <KV label="Available" value={detail.webrtc_details.available != null ? String(detail.webrtc_details.available) : '—'} dark={dark} />
                <KV label="Tested" value={detail.webrtc_details.tested != null ? String(detail.webrtc_details.tested) : '—'} dark={dark} />
                <KV label="Candidate count" value={detail.webrtc_details.candidate_count ?? '—'} dark={dark} />
                <KV label="Candidate types" value={detail.webrtc_details.candidate_types?.join(', ') || '—'} dark={dark} />
                <KV label="Public IPs" value={detail.webrtc_details.public_ip_candidates?.length ? `${detail.webrtc_details.public_ip_candidates.length} found` : '—'} dark={dark} />
                <KV label="mDNS masking" value={detail.webrtc_details.mdns_hostname_seen != null ? String(detail.webrtc_details.mdns_hostname_seen) : '—'} dark={dark} />
                {detail.webrtc_details.error && <KV label="Error" value={detail.webrtc_details.error} dark={dark} />}
              </div>
            </Section>

            {/* 6 — Timing */}
            <Section title="Timing" icon={Clock} dark={dark}>
              <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                <KV label="Notice loaded" value={detail.timing.notice_loaded_at_ms != null ? `${detail.timing.notice_loaded_at_ms} ms` : '—'} dark={dark} />
                <KV label="Continue clicked" value={detail.timing.continue_clicked_at_ms != null ? `${detail.timing.continue_clicked_at_ms} ms` : '—'} dark={dark} />
                <KV label="Collect started" value={detail.timing.collect_started_at_ms != null ? `${detail.timing.collect_started_at_ms} ms` : '—'} dark={dark} />
                <KV label="WebRTC elapsed" value={detail.timing.webrtc_elapsed_ms != null ? `${detail.timing.webrtc_elapsed_ms} ms` : '—'} dark={dark} />
              </div>
            </Section>

            {/* 7 — Server Context */}
            <Section title="Server Context" icon={Globe} dark={dark}>
              <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                <KV label="CF Ray ID" value={detail.server_context.cf_ray_id ?? '—'} dark={dark} />
                <KV label="CF Country" value={detail.server_context.cf_country ?? '—'} dark={dark} />
              </div>
            </Section>

            {/* 8 — Risk Context */}
            <Section title="Risk Context" icon={Shield} dark={dark}>
              <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                <div className="flex items-start justify-between gap-4 py-1.5">
                  <span className={`text-xs flex-shrink-0 w-40 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>Timezone / IP mismatch</span>
                  <span>{boolBadge(rc?.timezone_ip_mismatch, dark)}</span>
                </div>
                <div className="flex items-start justify-between gap-4 py-1.5">
                  <span className={`text-xs flex-shrink-0 w-40 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>Language / country mismatch</span>
                  <span>{boolBadge(rc?.language_country_mismatch, dark)}</span>
                </div>
                <div className="flex items-start justify-between gap-4 py-1.5">
                  <span className={`text-xs flex-shrink-0 w-40 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>WebRTC / request IP mismatch</span>
                  <span>{boolBadge(rc?.webrtc_public_ip_request_ip_mismatch, dark)}</span>
                </div>
                <div className="flex items-start justify-between gap-4 py-1.5">
                  <span className={`text-xs flex-shrink-0 w-40 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>IP changed entry→login</span>
                  <span>{boolBadge(rc?.ip_changed_between_entry_and_login, dark)}</span>
                </div>
                <KV label="Repeat visit count" value={rc?.repeat_visitor_count ?? '—'} dark={dark} />
              </div>
            </Section>

            {/* Login correlation */}
            {detail.login.logged_in && (
              <Section title="Login Correlation" icon={Link2} dark={dark}>
                <div className={`divide-y ${dark ? 'divide-neutral-800' : 'divide-neutral-100'}`}>
                  <KV label="User ID" value={<span className="font-mono text-xs">{detail.login.user_id ?? '—'}</span>} dark={dark} />
                  <KV label="Session ID" value={<span className="font-mono text-xs">{detail.login.session_id?.slice(0, 12) ?? '—'}…</span>} dark={dark} />
                  <KV label="Logged in at" value={fmt(detail.login.logged_in_at)} dark={dark} />
                  <KV label="Session IP" value={detail.login.ip ?? '—'} dark={dark} />
                </div>
              </Section>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}

// ── Visit row ──

function VisitRow({ visit, dark, onClick }: { visit: VisitorVisitSummary; dark: boolean; onClick: () => void }) {
  return (
    <button
      id={`visit-row-${visit.visit_id}`}
      className={`w-full text-left flex items-center gap-4 px-4 py-3 border-b transition-colors ${
        dark
          ? 'border-neutral-800 hover:bg-neutral-800/50'
          : 'border-neutral-100 hover:bg-neutral-50'
      }`}
      onClick={onClick}
    >
      <div className={`w-8 h-8 rounded flex items-center justify-center flex-shrink-0 ${
        dark ? 'bg-neutral-800' : 'bg-neutral-100'
      }`}>
        <Users className={`w-4 h-4 ${dark ? 'text-neutral-400' : 'text-neutral-500'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={`text-sm font-mono truncate ${dark ? 'text-neutral-300' : 'text-neutral-700'}`}>
            {visit.visit_id.slice(0, 8)}…
          </span>
          {visit.login.logged_in && (
            <span className={`text-xs px-1.5 py-0.5 rounded border ${dark ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' : 'border-emerald-200 text-emerald-700 bg-emerald-50'}`}>
              Logged in
            </span>
          )}
        </div>
        <p className={`text-xs truncate ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>
          {visit.page_path} · {relativeTime(visit.collected_at)}
        </p>
      </div>
      <ChevronRight className={`w-4 h-4 flex-shrink-0 ${dark ? 'text-neutral-600' : 'text-neutral-300'}`} />
    </button>
  );
}

// ── Main page ──

export function VisitorInvestigationPage() {
  const { theme } = useTheme();
  const dark = theme === 'dark';

  const [visits, setVisits] = useState<VisitorVisitSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loginFilter, setLoginFilter] = useState<'all' | 'linked' | 'anonymous'>('all');
  const [timeFilter, setTimeFilter] = useState<'all' | '1h' | '24h' | '7d'>('all');

  const load = useCallback(async (cursor?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listAdminVisitorVisits(cursor);
      setVisits((prev) => cursor ? [...prev, ...data.items] : data.items);
      setNextCursor(data.next_cursor);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load visitor visits');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filteredVisits = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const now = Date.now();
    const cutoffMs = timeFilter === '1h'
      ? now - 60 * 60 * 1000
      : timeFilter === '24h'
        ? now - 24 * 60 * 60 * 1000
        : timeFilter === '7d'
          ? now - 7 * 24 * 60 * 60 * 1000
          : null;

    return visits.filter((visit) => {
      if (loginFilter === 'linked' && !visit.login.logged_in) return false;
      if (loginFilter === 'anonymous' && visit.login.logged_in) return false;
      if (cutoffMs !== null) {
        const collectedMs = visit.collected_at ? new Date(visit.collected_at).getTime() : Number.NaN;
        if (!Number.isFinite(collectedMs) || collectedMs < cutoffMs) return false;
      }
      if (!q) return true;
      const haystack = [
        visit.visit_id,
        visit.page_path,
        visit.notice_version,
        visit.user_agent,
        visit.login.user_id,
        visit.login.session_id,
        visit.login.ip,
      ].filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(q);
    });
  }, [loginFilter, searchQuery, timeFilter, visits]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${dark ? 'bg-blue-500/20' : 'bg-blue-50'}`}>
            <Users className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className={`font-semibold ${dark ? 'text-white' : 'text-neutral-900'}`}>Visitor Investigation</h3>
            <p className={`text-sm ${dark ? 'text-neutral-400' : 'text-neutral-500'}`}>
              {loading ? 'Loading...' : `${filteredVisits.length} shown of ${visits.length} visit record${visits.length !== 1 ? 's' : ''}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg ${dark ? 'bg-neutral-800 text-neutral-400' : 'bg-neutral-100 text-neutral-500'}`}>
            <Info className="w-3.5 h-3.5" />
            Public entry page records only
          </div>
          <button
            id="visitors-refresh"
            onClick={() => { setVisits([]); load(); }}
            disabled={loading}
            className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 ${
              dark ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
            }`}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${dark ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-red-50 text-red-600 border border-red-200'}`}>
          <XCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Loaded-row filters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="relative">
          <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${dark ? 'text-neutral-500' : 'text-neutral-400'}`} />
          <input
            id="visitor-visit-search"
            aria-label="Search visitor visits"
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search visit ID, page, user, IP..."
            className={`w-full pl-10 pr-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/40 ${
              dark ? 'bg-neutral-900 border-neutral-700 text-white placeholder-neutral-500' : 'bg-white border-neutral-200 text-neutral-900 placeholder-neutral-400'
            }`}
          />
        </div>
        <select
          id="visitor-login-filter"
          aria-label="Visitor login filter"
          value={loginFilter}
          onChange={(event) => setLoginFilter(event.target.value as typeof loginFilter)}
          className={`px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/40 ${
            dark ? 'bg-neutral-900 border-neutral-700 text-white' : 'bg-white border-neutral-200 text-neutral-900'
          }`}
        >
          <option value="all">All visitors</option>
          <option value="linked">Login linked</option>
          <option value="anonymous">Anonymous only</option>
        </select>
        <select
          id="visitor-time-filter"
          aria-label="Visitor time filter"
          value={timeFilter}
          onChange={(event) => setTimeFilter(event.target.value as typeof timeFilter)}
          className={`px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/40 ${
            dark ? 'bg-neutral-900 border-neutral-700 text-white' : 'bg-white border-neutral-200 text-neutral-900'
          }`}
        >
          <option value="all">All loaded times</option>
          <option value="1h">Last hour</option>
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
        </select>
      </div>

      {/* Table */}
      <div className={`border rounded-lg overflow-hidden ${dark ? 'border-neutral-700/50' : 'border-neutral-200'}`}>
        {/* Table header */}
        <div className={`flex items-center gap-4 px-4 py-2.5 border-b text-xs font-medium uppercase tracking-wide ${
          dark ? 'border-neutral-700/50 bg-neutral-900/60 text-neutral-500' : 'border-neutral-100 bg-neutral-50 text-neutral-400'
        }`}>
          <span className="w-8 flex-shrink-0" />
          <span className="flex-1">Visit ID - Page - Time</span>
          <span className="w-4 flex-shrink-0" />
        </div>

        {/* Loading skeleton */}
        {loading && visits.length === 0 && (
          <div>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className={`flex items-center gap-4 px-4 py-3 border-b animate-pulse ${dark ? 'border-neutral-800' : 'border-neutral-100'}`}>
                <div className={`w-8 h-8 rounded flex-shrink-0 ${dark ? 'bg-neutral-800' : 'bg-neutral-100'}`} />
                <div className="flex-1 space-y-2">
                  <div className={`h-3 w-40 rounded ${dark ? 'bg-neutral-800' : 'bg-neutral-100'}`} />
                  <div className={`h-2.5 w-56 rounded ${dark ? 'bg-neutral-800/50' : 'bg-neutral-50'}`} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && filteredVisits.length === 0 && (
          <div className={`text-center py-12 ${dark ? 'text-neutral-500' : 'text-neutral-400'}`}>
            <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">{visits.length > 0 ? 'No loaded visits match the current filters.' : 'No visitor visits recorded yet.'}</p>
          </div>
        )}

        {/* Rows */}
        {filteredVisits.map((v) => (
          <VisitRow key={v.visit_id} visit={v} dark={dark} onClick={() => setSelectedId(v.visit_id)} />
        ))}

        {/* Load more */}
        {nextCursor && (
          <div className="p-3 text-center">
            <button
              id="visitors-load-more"
              onClick={() => load(nextCursor)}
              disabled={loading}
              className={`text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-50 ${
                dark ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
              }`}
            >
              {loading ? <span className="flex items-center gap-2"><Loader2 className="w-3.5 h-3.5 animate-spin" />Loading...</span> : 'Load more visits'}
            </button>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      <AnimatePresence>
        {selectedId && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
              onClick={() => setSelectedId(null)}
            />
            <VisitDetailDrawer visitId={selectedId} dark={dark} onClose={() => setSelectedId(null)} />
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
