import { FileText, Download, Search, CheckCircle, ShieldCheck, ClipboardList, ScrollText, XCircle, MapPin, FileStack, AlertTriangle, Copy } from 'lucide-react';
import { useTheme } from '../../lib/theme';
import { useAdminAudit, useDsrRequests } from '../../lib/hooks';
import { api, ApiError } from '../../lib/api';
import { useState } from 'react';
import type { Site } from '../../lib/types';

/**
 * Audit & Compliance — ux-product-spec.md requires:
 * - Audit filters: actor, action, resource, time range
 * - Audit verifier status
 * - Signed JSONL export action
 * - DPA/signage export action (functional)
 * - DSR request ledger view (functional)
 */
export function AuditLogTable() {
  const { theme } = useTheme();
  const d = theme === 'dark';
  const [tab, setTab] = useState<'audit' | 'compliance' | 'dsr'>('audit');

  // Server-side filter state variables
  const [action, setAction] = useState('');
  const [actorType, setActorType] = useState('');
  const [actorId, setActorId] = useState('');
  const [severity, setSeverity] = useState('');
  const [category, setCategory] = useState('');
  const [outcome, setOutcome] = useState('');
  const [resource, setResource] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [tsFrom, setTsFrom] = useState('');
  const [tsTo, setTsTo] = useState('');

  // Client-side text search query (sub-filtering loaded rows)
  const [searchQuery, setSearchQuery] = useState('');

  const [verifyResult, setVerifyResult] = useState<{ valid: boolean; checked: number } | null>(null);
  const [verifying, setVerifying] = useState(false);

  // Construct filters object to pass to the useAdminAudit hook
  const filters = {
    action: action || undefined,
    actor_type: actorType || undefined,
    actor_id: actorId || undefined,
    severity: severity || undefined,
    category: category || undefined,
    outcome: outcome || undefined,
    resource: resource || undefined,
    session_id: sessionId || undefined,
    ts_from: tsFrom ? new Date(tsFrom).toISOString() : undefined,
    ts_to: tsTo ? new Date(tsTo).toISOString() : undefined,
  };

  const { logs, loading, loadMore, hasMore } = useAdminAudit(filters);

  // Compliance state
  const sites: Site[] = [];
  const sitesLoading = false;
  const [dpaExporting, setDpaExporting] = useState(false);
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // DSR state
  const { requests: dsrRequests, loading: dsrLoading } = useDsrRequests();

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 5000);
  };

  const copyValue = async (label: string, value: string | null | undefined) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      showMsg(`${label} copied to clipboard`, 'success');
    } catch {
      showMsg(`Failed to copy ${label.toLowerCase()}`, 'error');
    }
  };

  const CopyableValue = ({ label, value }: { label: string; value: string | null | undefined }) => {
    if (!value) {
      return <span className={d ? 'text-[#666666]' : 'text-neutral-500'}>-</span>;
    }
    return (
      <div className="flex items-start gap-2 max-w-[360px]">
        <code className="text-xs whitespace-normal break-all leading-relaxed">{value}</code>
        <button
          type="button"
          onClick={() => { void copyValue(label, value); }}
          aria-label={`Copy ${label}`}
          title={`Copy ${label}`}
          className={`mt-0.5 p-1 rounded border transition-colors ${
            d
              ? 'border-[#333333] text-[#F07C1E] hover:bg-[#1A1A1A]'
              : 'border-neutral-200 text-orange-600 hover:bg-orange-50'
          }`}
        >
          <Copy className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  };

  const riskColor = (act: string) => {
    if (act.includes('disable') || act.includes('denied') || act.includes('break_glass')) {
      return d ? 'bg-[#FF3333]/10 text-[#FF3333] border-[#FF3333]/20' : 'bg-red-50 text-red-700 border-red-200';
    }
    if (act.includes('grant') || act.includes('role') || act.includes('rotate')) {
      return d ? 'bg-[#F4B266]/10 text-[#F4B266] border-[#F4B266]/20' : 'bg-amber-50 text-amber-700 border-amber-200';
    }
    return d ? 'bg-[#7BC67B]/10 text-[#7BC67B] border-[#7BC67B]/20' : 'bg-emerald-50 text-emerald-700 border-emerald-200';
  };

  const handleExport = async () => {
    try {
      const data = await api.exportAudit();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `panoptix-audit-export-${new Date().toISOString().slice(0, 10)}.jsonl`;
      a.click(); URL.revokeObjectURL(url);
    } catch { /* silent */ }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try { const r = await api.verifyAuditChain(); setVerifyResult(r); } catch { /* silent */ }
    setVerifying(false);
  };

  const handleDpaExport = async () => {
    setDpaExporting(true);
    try {
      const data = await api.exportDpa();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `panoptix-dpa-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click(); URL.revokeObjectURL(url);
      showMsg('DPA compliance artefact bundle exported successfully', 'success');
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'DPA export failed', 'error');
    }
    setDpaExporting(false);
  };

  const handleSignageAttest = async (siteId: string, siteName: string) => {
    // Disabled since backend site listing is planned but not currently sourceable
    showMsg(`Signage attestation is currently disabled for "${siteName}"`, 'error');
  };

  const filtered = logs.filter((log) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return log.action.toLowerCase().includes(q) ||
      (log.resource || '').toLowerCase().includes(q) ||
      (log.actor_id || '').toLowerCase().includes(q) ||
      (log.ip || '').toLowerCase().includes(q);
  });

  const tabs = [
    { id: 'audit' as const, label: 'Audit Logs', icon: ScrollText },
    { id: 'compliance' as const, label: 'Compliance & DPA', icon: ClipboardList },
    { id: 'dsr' as const, label: 'DSR Ledger', icon: FileStack },
  ];

  const dsrStatusColor = (status: string) => {
    if (status === 'completed' || status === 'closed') return 'bg-[#7BC67B]/10 text-[#7BC67B]';
    if (status === 'overdue') return 'bg-[#FF3333]/10 text-[#FF3333]';
    return 'bg-[#F4B266]/10 text-[#F4B266]';
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>Audit & Compliance</h2>
        <p className={d ? 'text-[#666666]' : 'text-neutral-500'}>Review security events, manage compliance records, and track data subject requests</p>
      </div>

      {/* Status messages */}
      {msg && (
        <div role={msg.type === 'error' ? 'alert' : 'status'} className={`p-3 text-sm flex items-center gap-2 rounded-none border ${
          msg.type === 'error' ? 'bg-[#F28F6C]/10 border-[#F28F6C]/30 text-[#F28F6C]' : 'bg-[#7BC67B]/10 border-[#7BC67B]/30 text-[#7BC67B]'
        }`}>
          {msg.type === 'error' ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          {msg.text}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2">
        {tabs.map(t => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors rounded-none ${tab === t.id
                ? 'bg-[#F07C1E] text-[#0A0A0A]'
                : d ? 'bg-[#111111] text-[#666666] border border-[#222222] hover:text-[#F0EAD6]' : 'bg-[#FFFFFF] text-[#555555] border border-[#DDDDDD] hover:text-[#0A0A0A]'
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === 'audit' ? (
        <div className={`border rounded-none overflow-hidden ${d ? 'bg-[#111111] border-[#222222]' : 'bg-[#FFFFFF] border-[#DDDDDD]'}`}>
          {/* Header */}
          <div className={`p-6 border-b ${d ? 'border-[#222222]' : 'border-[#DDDDDD]'}`}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[rgba(240,124,30,0.08)] rounded-none flex items-center justify-center">
                  <FileText className="w-5 h-5 text-[#F07C1E]" />
                </div>
                <div>
                  <h3 className={`font-semibold ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>Security Event Timeline</h3>
                  <p className={`text-sm ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>{logs.length} events loaded · Tamper-evident HMAC chain</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleVerify}
                  disabled={verifying}
                  className="flex items-center gap-2 px-4 py-2 bg-[rgba(123,198,123,0.1)] hover:bg-[rgba(123,198,123,0.2)] border border-[#7BC67B] rounded-none text-[#7BC67B] text-sm font-medium disabled:opacity-50 transition-colors"
                >
                  <ShieldCheck className="w-4 h-4" />
                  {verifying ? 'Verifying...' : 'Verify Chain'}
                </button>
                <button
                  onClick={handleExport}
                  className="flex items-center gap-2 px-4 py-2 bg-[rgba(240,124,30,0.08)] hover:bg-[rgba(240,124,30,0.12)] border border-[#222222] hover:border-[#F07C1E] rounded-none text-[#F07C1E] text-sm font-medium transition-all"
                >
                  <Download className="w-4 h-4" />
                  Export JSONL
                </button>
              </div>
            </div>

            {verifyResult && (
              <div className={`mb-4 p-3 rounded-none flex items-center gap-2 text-sm border ${verifyResult.valid ? 'bg-[#7BC67B]/10 border-[#7BC67B]/30 text-[#7BC67B]' : 'bg-[#FF3333]/10 border-[#FF3333]/30 text-[#FF3333]'}`}>
                <CheckCircle className="w-4 h-4" />
                {verifyResult.valid ? `Chain verified: ${verifyResult.checked} rows valid` : 'Chain verification FAILED — integrity compromised'}
              </div>
            )}

            {/* Advanced Filters Panel */}
            <div className="space-y-4 pt-2">
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {/* Search current view */}
                <div className="relative flex items-center md:col-span-3 lg:col-span-2">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#666666]" />
                  <input
                    type="text"
                    placeholder="Filter current view by actor, action, resource, IP..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className={`w-full pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6] placeholder-[#666666]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'}`}
                  />
                </div>

                {/* Action dropdown */}
                <div>
                  <select
                    value={action}
                    onChange={(e) => setAction(e.target.value)}
                    className={`w-full px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
                  >
                    <option value="">All Actions</option>
                    <option value="camera.create">Camera Create</option>
                    <option value="camera.acl.grant">ACL Grant</option>
                    <option value="camera.acl.revoke">ACL Revoke</option>
                    <option value="camera.disable">Camera Disable</option>
                    <option value="admin.user.disabled">User Disabled</option>
                    <option value="admin.user.role">Role Change</option>
                    <option value="gateway.create">Gateway Create</option>
                    <option value="gateway.disable">Gateway Disable</option>
                    <option value="viewer.token.issued">Token Issued</option>
                    <option value="privacy.notice.accept">Privacy Accept</option>
                    <option value="session.revoke">Session Revoke</option>
                    <option value="break_glass.open">Break-Glass Open</option>
                    <option value="break_glass.close">Break-Glass Close</option>
                    <option value="mfa.reset">MFA Reset</option>
                  </select>
                </div>

                {/* Actor Type */}
                <div>
                  <select
                    value={actorType}
                    onChange={(e) => setActorType(e.target.value)}
                    className={`w-full px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
                  >
                    <option value="">All Actor Types</option>
                    <option value="user">User</option>
                    <option value="gateway">Gateway</option>
                    <option value="system">System</option>
                    <option value="break_glass">Break Glass</option>
                    <option value="service_token_monitor">Service Token Monitor</option>
                  </select>
                </div>

                {/* Severity */}
                <div>
                  <select
                    value={severity}
                    onChange={(e) => setSeverity(e.target.value)}
                    className={`w-full px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
                  >
                    <option value="">All Severities</option>
                    <option value="informational">Informational</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>

                {/* Category */}
                <div>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className={`w-full px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
                  >
                    <option value="">All Categories</option>
                    <option value="authentication">Authentication</option>
                    <option value="authorization">Authorization</option>
                    <option value="data_access">Data Access</option>
                    <option value="admin">Admin</option>
                    <option value="system">System</option>
                    <option value="compliance">Compliance</option>
                  </select>
                </div>

                {/* Outcome */}
                <div>
                  <select
                    value={outcome}
                    onChange={(e) => setOutcome(e.target.value)}
                    className={`w-full px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
                  >
                    <option value="">All Outcomes</option>
                    <option value="success">Success</option>
                    <option value="failure">Failure</option>
                    <option value="denied">Denied</option>
                    <option value="error">Error</option>
                  </select>
                </div>

                {/* Actor ID Input */}
                <div>
                  <input
                    type="text"
                    placeholder="Actor UUID"
                    value={actorId}
                    onChange={(e) => setActorId(e.target.value)}
                    className={`w-full px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6] placeholder-[#666666]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'}`}
                  />
                </div>

                {/* Session ID Input */}
                <div>
                  <input
                    type="text"
                    placeholder="Session UUID"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    className={`w-full px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6] placeholder-[#666666]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'}`}
                  />
                </div>

                {/* Resource Input */}
                <div>
                  <input
                    type="text"
                    placeholder="Resource Name"
                    value={resource}
                    onChange={(e) => setResource(e.target.value)}
                    className={`w-full px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6] placeholder-[#666666]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'}`}
                  />
                </div>
              </div>

              {/* Date/Time Range & Reset */}
              <div className="flex flex-col sm:flex-row gap-3 justify-between items-start sm:items-center">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-mono uppercase tracking-wider ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>From:</span>
                    <input
                      type="datetime-local"
                      value={tsFrom}
                      onChange={(e) => setTsFrom(e.target.value)}
                      className={`px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-mono uppercase tracking-wider ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>To:</span>
                    <input
                      type="datetime-local"
                      value={tsTo}
                      onChange={(e) => setTsTo(e.target.value)}
                      className={`px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[#F07C1E] border rounded-none ${d ? 'bg-[#1A1A1A] border-[#222222] text-[#F0EAD6]' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
                    />
                  </div>
                </div>

                <button
                  onClick={() => {
                    setAction('');
                    setActorType('');
                    setActorId('');
                    setSeverity('');
                    setCategory('');
                    setOutcome('');
                    setResource('');
                    setSessionId('');
                    setTsFrom('');
                    setTsTo('');
                  }}
                  className={`px-4 py-2 border text-xs font-medium transition-colors rounded-none ${d ? 'border-[#222222] text-[#666666] hover:text-[#F0EAD6] hover:border-[#F07C1E]' : 'border-neutral-200 text-neutral-500 hover:text-neutral-900 hover:border-neutral-400'}`}
                >
                  Clear Filters
                </button>
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${d ? 'border-[#222222] bg-[#0A0A0A]' : 'border-neutral-200 bg-neutral-50'}`}>
                  {['Timestamp', 'Actor', 'Action', 'Resource', 'IP', 'Risk'].map(h => (
                    <th key={h} className={`text-left px-6 py-3 text-xs font-mono uppercase tracking-wider ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className={`divide-y ${d ? 'divide-[#222222]' : 'divide-neutral-100'}`}>
                {loading && filtered.length === 0 ? (
                  <tr><td colSpan={6} className="px-6 py-12 text-center text-[#666666]">Loading audit logs...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={6} className="px-6 py-12 text-center text-[#666666]">No audit events found</td></tr>
                ) : filtered.map(log => (
                  <tr key={log.id} className={`transition-colors ${d ? 'hover:bg-[#1A1A1A]' : 'hover:bg-neutral-50'}`}>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-[#F0EAD6]' : 'text-neutral-600'}`}>{log.ts ? new Date(log.ts).toLocaleString('en-US', { hour12: false }) : '—'}</td>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>
                      <div className="space-y-1">
                        <CopyableValue label="actor ID" value={log.actor_id} />
                        <span className={`inline-block text-xs ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>({log.actor_type})</span>
                      </div>
                    </td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-[#F0EAD6]' : 'text-neutral-600'}`}>{log.action}</td>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-[#F0EAD6]' : 'text-neutral-600'}`}>
                      <CopyableValue label="resource ID" value={log.resource} />
                    </td>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>{log.ip || '—'}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-mono border ${riskColor(log.action)}`}>
                        {log.action.includes('disable') || log.action.includes('denied') || log.action.includes('break_glass') ? 'HIGH' : log.action.includes('grant') || log.action.includes('role') || log.action.includes('rotate') ? 'MEDIUM' : 'LOW'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div className="p-4 text-center border-t border-t-[#222222]">
              <button
                onClick={loadMore}
                className="px-6 py-2 bg-[rgba(240,124,30,0.08)] hover:bg-[rgba(240,124,30,0.12)] border border-[#222222] hover:border-[#F07C1E] rounded-none text-[#F07C1E] text-sm font-medium transition-all"
              >
                Load More
              </button>
            </div>
          )}
        </div>
      ) : tab === 'compliance' ? (
        /* Compliance & DPA Tab */
        <div className="space-y-6">
          {/* DPA Export */}
          <div className={`border rounded-none p-6 ${d ? 'bg-[#111111] border-[#222222]' : 'bg-[#FFFFFF] border-neutral-200'}`}>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[rgba(240,124,30,0.08)] rounded-none flex items-center justify-center">
                  <FileStack className="w-5 h-5 text-[#F07C1E]" />
                </div>
                <div>
                  <h3 className={`font-semibold ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>DPA Artefact Export</h3>
                  <p className={`text-sm ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>Generate compliance documents: ROPA, PIAs, processor DPAs, breach logs, retention policies, signage attestations</p>
                </div>
              </div>
              <button
                onClick={handleDpaExport}
                disabled={dpaExporting}
                className="flex items-center gap-2 px-4 py-2.5 bg-[#F07C1E] hover:bg-[#C45E0A] text-[#0A0A0A] rounded-none text-sm font-medium disabled:opacity-50 transition-colors shadow-none"
              >
                <Download className="w-4 h-4" />
                {dpaExporting ? 'Exporting...' : 'Export DPA Bundle'}
              </button>
            </div>
            <p className={`text-xs ${d ? 'text-[#666666]' : 'text-neutral-400'}`}>POST /api/v1/admin/dpa/export · Signed bundle includes all compliance artefact types</p>
          </div>

          {/* Bystander Signage Attestation — per core-features §7 + v4 §16.12 */}
          <div className={`border rounded-none p-6 ${d ? 'bg-[#111111] border-[#222222]' : 'bg-[#FFFFFF] border-neutral-200'}`}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-[rgba(240,124,30,0.08)] rounded-none flex items-center justify-center">
                <MapPin className="w-5 h-5 text-[#F07C1E]" />
              </div>
              <div>
                <h3 className={`font-semibold ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>Bystander Signage Attestation</h3>
                <p className={`text-sm ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>Record that physical privacy signs are posted at each camera site (PH DPA §16.12)</p>
              </div>
            </div>

            {sitesLoading ? (
              <div className="text-center py-8 text-[#666666]">Loading sites...</div>
            ) : sites.length === 0 ? (
              <div className={`text-center py-8 rounded-none border border-dashed ${d ? 'bg-[#1A1A1A] border-[#222222]' : 'bg-neutral-50 border-neutral-200'}`}>
                <MapPin className={`w-10 h-10 mx-auto mb-2 ${d ? 'text-[#666666]' : 'text-neutral-300'}`} />
                <p className={d ? 'text-[#666666]' : 'text-neutral-500 text-sm'}>Site listing is planned; signage attestation is unavailable until sites are available.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {sites.map(site => (
                  <div key={site.id} className={`flex items-center justify-between p-4 rounded-none border ${d ? 'bg-[#1A1A1A] border-[#222222]' : 'bg-neutral-50 border-neutral-200'}`}>
                    <div>
                      <h4 className={`font-medium ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>{site.name}</h4>
                      {site.address && <p className={`text-sm ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>{site.address}</p>}
                      {site.bystander_signage_attested_at ? (
                        <p className="text-xs text-[#7BC67B] mt-1 flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" /> Attested: {new Date(site.bystander_signage_attested_at).toLocaleDateString()}
                        </p>
                      ) : (
                        <p className="text-xs text-[#F4B266] mt-1 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" /> Not yet attested
                        </p>
                      )}
                    </div>
                    {!site.bystander_signage_attested_at && (
                      <button
                        onClick={() => handleSignageAttest(site.id, site.name)}
                        className="px-4 py-2 bg-[rgba(240,124,30,0.08)] hover:bg-[rgba(240,124,30,0.12)] border border-[#222222] hover:border-[#F07C1E] rounded-none text-[#F07C1E] text-sm font-medium transition-colors"
                      >
                        Attest Signage
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* DSR Request Ledger Tab — per ux-product-spec.md */
        <div className={`border rounded-none overflow-hidden ${d ? 'bg-[#111111] border-[#222222]' : 'bg-[#FFFFFF] border-neutral-200'}`}>
          <div className={`p-6 border-b ${d ? 'border-[#222222]' : 'border-neutral-200'}`}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-[rgba(240,124,30,0.08)] rounded-none flex items-center justify-center">
                <FileStack className="w-5 h-5 text-[#F07C1E]" />
              </div>
              <div>
                <h3 className={`font-semibold ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>Data Subject Request Ledger</h3>
                <p className={`text-sm ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>Track DSR requests (access, correction, deletion, objection, restriction) per RA 10173 / NPC guidelines</p>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${d ? 'border-[#222222] bg-[#0A0A0A]' : 'border-neutral-200 bg-neutral-50'}`}>
                  {['Received', 'Due', 'Type', 'Subject', 'Contact', 'Status', 'Outcome'].map(h => (
                    <th key={h} className={`text-left px-6 py-3 text-xs font-mono uppercase tracking-wider ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className={`divide-y ${d ? 'divide-[#222222]' : 'divide-neutral-100'}`}>
                {dsrLoading ? (
                  <tr><td colSpan={7} className="px-6 py-12 text-center text-[#666666]">Loading DSR requests...</td></tr>
                ) : dsrRequests.length === 0 ? (
                  <tr><td colSpan={7} className="px-6 py-12 text-center text-[#666666]">No DSR requests found</td></tr>
                ) : dsrRequests.map(dsr => (
                  <tr key={dsr.id} className={`transition-colors ${d ? 'hover:bg-[#1A1A1A]' : 'hover:bg-neutral-50'}`}>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-[#F0EAD6]' : 'text-neutral-600'}`}>{new Date(dsr.received_at).toLocaleDateString()}</td>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-[#F0EAD6]' : 'text-neutral-600'}`}>{new Date(dsr.due_at).toLocaleDateString()}</td>
                    <td className={`px-6 py-4 text-sm font-medium ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>{dsr.request_type}</td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-[#F0EAD6]' : 'text-neutral-600'}`}>{dsr.subject_type}</td>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-[#F0EAD6]' : 'text-neutral-600'}`}>{dsr.requester_contact}</td>
                    <td className="px-6 py-4"><span className={`px-2 py-0.5 rounded-sm text-xs font-mono ${dsrStatusColor(dsr.status)}`}>{dsr.status}</span></td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>{dsr.outcome || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
