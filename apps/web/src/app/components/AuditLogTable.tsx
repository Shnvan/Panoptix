import { FileText, Download, Search, CheckCircle, ShieldCheck, ClipboardList, ScrollText, XCircle, MapPin, FileStack, AlertTriangle } from 'lucide-react';
import { useTheme } from '../../lib/theme';
import { useAdminAudit } from '../../lib/hooks';
import { api, ApiError } from '../../lib/api';
import { useState, useEffect } from 'react';
import type { DsrRequest, Site } from '../../lib/types';

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
  const [actionFilter, setActionFilter] = useState<string | undefined>();
  const [searchQuery, setSearchQuery] = useState('');
  const [verifyResult, setVerifyResult] = useState<{ valid: boolean; checked: number } | null>(null);
  const [verifying, setVerifying] = useState(false);
  const { logs, loading, loadMore, hasMore } = useAdminAudit(actionFilter);

  // Compliance state
  const [sites, setSites] = useState<Site[]>([]);
  const [sitesLoading, setSitesLoading] = useState(false);
  const [dpaExporting, setDpaExporting] = useState(false);
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // DSR state
  const [dsrRequests, setDsrRequests] = useState<DsrRequest[]>([]);
  const [dsrLoading, setDsrLoading] = useState(false);

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 5000);
  };

  useEffect(() => {
    if (tab === 'compliance') {
      setSitesLoading(true);
      setSites([]);
      setSitesLoading(false);
    }
    if (tab === 'dsr') {
      setDsrLoading(true);
      setDsrRequests([]);
      setDsrLoading(false);
    }
  }, [tab]);

  const riskColor = (action: string) => {
    if (action.includes('disable') || action.includes('denied') || action.includes('break_glass'))
      return d ? 'bg-red-500/20 text-red-400 border-red-500/30' : 'bg-red-50 text-red-700 border-red-200';
    if (action.includes('grant') || action.includes('role') || action.includes('rotate'))
      return d ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' : 'bg-amber-50 text-amber-700 border-amber-200';
    return d ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-emerald-50 text-emerald-700 border-emerald-200';
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
      showMsg('DPA artefact bundle exported successfully', 'success');
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'DPA export failed', 'error');
    }
    setDpaExporting(false);
  };

  const handleSignageAttest = async (siteId: string, siteName: string) => {
    try {
      await api.attestSignage(siteId);
      showMsg(`Signage attestation recorded for "${siteName}"`, 'success');
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'Signage attestation failed', 'error');
    }
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
    if (status === 'completed' || status === 'closed') return 'bg-emerald-500/20 text-emerald-400';
    if (status === 'overdue') return 'bg-red-500/20 text-red-400';
    return 'bg-amber-500/20 text-amber-400';
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>Audit & Compliance</h2>
        <p className={d ? 'text-slate-400' : 'text-slate-500'}>Review security events, manage compliance records, and track data subject requests</p>
      </div>

      {/* Status messages */}
      {msg && (
        <div className={`p-3 rounded-xl text-sm flex items-center gap-2 ${
          msg.type === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
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
            <button key={t.id} onClick={() => setTab(t.id)} className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${tab === t.id
              ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/25'
              : d ? 'bg-slate-800/50 text-slate-400 hover:text-white' : 'bg-slate-100 text-slate-500 hover:text-slate-900'
            }`}><Icon className="w-4 h-4" />{t.label}</button>
          );
        })}
      </div>

      {tab === 'audit' ? (
        <div className={`backdrop-blur-xl border rounded-xl overflow-hidden ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
          {/* Header */}
          <div className={`p-6 border-b ${d ? 'border-slate-700/50' : 'border-slate-200'}`}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-cyan-500/20 rounded-xl flex items-center justify-center"><FileText className="w-5 h-5 text-cyan-500" /></div>
                <div>
                  <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Security Event Timeline</h3>
                  <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>{logs.length} events loaded · Tamper-evident HMAC chain</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={handleVerify} disabled={verifying} className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 rounded-xl text-emerald-500 text-sm font-medium disabled:opacity-50">
                  <ShieldCheck className="w-4 h-4" />{verifying ? 'Verifying...' : 'Verify Chain'}
                </button>
                <button onClick={handleExport} className="flex items-center gap-2 px-4 py-2 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 rounded-xl text-cyan-500 text-sm font-medium">
                  <Download className="w-4 h-4" /> Export JSONL
                </button>
              </div>
            </div>

            {verifyResult && (
              <div className={`mb-4 p-3 rounded-xl flex items-center gap-2 text-sm ${verifyResult.valid ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border border-red-500/20 text-red-400'}`}>
                <CheckCircle className="w-4 h-4" />
                {verifyResult.valid ? `Chain verified: ${verifyResult.checked} rows valid` : 'Chain verification FAILED — integrity compromised'}
              </div>
            )}

            {/* Filters */}
            <div className="flex gap-3 flex-wrap">
              <div className="relative flex-1 min-w-48">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input type="text" placeholder="Search by actor, action, resource, IP..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                  className={`w-full rounded-xl pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50 ${d ? 'bg-slate-800/50 border border-slate-700/50 text-white placeholder-slate-400' : 'bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400'}`} />
              </div>
              <select value={actionFilter || ''} onChange={(e) => setActionFilter(e.target.value || undefined)}
                className={`px-4 py-2 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50 ${d ? 'bg-slate-800/50 border border-slate-700/50 text-white' : 'bg-slate-50 border border-slate-200 text-slate-900'}`}>
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
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${d ? 'border-slate-700/50 bg-slate-900/50' : 'border-slate-200 bg-slate-50'}`}>
                  {['Timestamp', 'Actor', 'Action', 'Resource', 'IP', 'Risk'].map(h => (
                    <th key={h} className={`text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider ${d ? 'text-slate-400' : 'text-slate-500'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className={`divide-y ${d ? 'divide-slate-700/50' : 'divide-slate-100'}`}>
                {loading && filtered.length === 0 ? (
                  <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-400">Loading audit logs...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-400">No audit events found</td></tr>
                ) : filtered.map(log => (
                  <tr key={log.id} className={`transition-colors ${d ? 'hover:bg-slate-800/30' : 'hover:bg-slate-50'}`}>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-slate-300' : 'text-slate-600'}`}>{log.ts ? new Date(log.ts).toLocaleString('en-US', { hour12: false }) : '—'}</td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-white' : 'text-slate-900'}`}>{log.actor_id?.slice(0, 12) || '—'}</td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>{log.action}</td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>{log.resource || '—'}</td>
                    <td className={`px-6 py-4 text-sm font-mono ${d ? 'text-slate-400' : 'text-slate-500'}`}>{log.ip || '—'}</td>
                    <td className="px-6 py-4"><span className={`inline-flex items-center px-3 py-1 rounded-lg text-xs font-semibold border ${riskColor(log.action)}`}>{log.action.includes('disable') || log.action.includes('denied') || log.action.includes('break_glass') ? 'HIGH' : log.action.includes('grant') || log.action.includes('role') || log.action.includes('rotate') ? 'MEDIUM' : 'LOW'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div className="p-4 text-center">
              <button onClick={loadMore} className="px-6 py-2 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 rounded-xl text-cyan-500 text-sm font-medium">Load More</button>
            </div>
          )}
        </div>
      ) : tab === 'compliance' ? (
        /* Compliance & DPA Tab */
        <div className="space-y-6">
          {/* DPA Export */}
          <div className={`backdrop-blur-xl border rounded-xl p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-500/20 rounded-xl flex items-center justify-center"><FileStack className="w-5 h-5 text-blue-500" /></div>
                <div>
                  <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>DPA Artefact Export</h3>
                  <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>Generate compliance documents: ROPA, PIAs, processor DPAs, breach logs, retention policies, signage attestations</p>
                </div>
              </div>
              <button onClick={handleDpaExport} disabled={dpaExporting}
                className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-400 hover:to-purple-500 text-white rounded-xl text-sm font-medium shadow-lg shadow-blue-500/25 disabled:opacity-50 transition-all">
                <Download className="w-4 h-4" /> {dpaExporting ? 'Exporting...' : 'Export DPA Bundle'}
              </button>
            </div>
            <p className={`text-xs ${d ? 'text-slate-500' : 'text-slate-400'}`}>POST /api/v1/admin/dpa/export · Signed bundle includes all artefact types</p>
          </div>

          {/* Bystander Signage Attestation — per core-features §7 + v4 §16.12 */}
          <div className={`backdrop-blur-xl border rounded-xl p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-amber-500/20 rounded-xl flex items-center justify-center"><MapPin className="w-5 h-5 text-amber-500" /></div>
              <div>
                <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Bystander Signage Attestation</h3>
                <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>Record that physical privacy signs are posted at each camera site (PH DPA §16.12)</p>
              </div>
            </div>

            {sitesLoading ? (
              <div className="text-center py-8 text-slate-400">Loading sites...</div>
            ) : sites.length === 0 ? (
              <div className={`text-center py-8 rounded-xl ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
                <MapPin className={`w-10 h-10 mx-auto mb-2 ${d ? 'text-slate-600' : 'text-slate-300'}`} />
                <p className={d ? 'text-slate-400' : 'text-slate-500'}>Site listing is not wired to the backend yet</p>
              </div>
            ) : (
              <div className="space-y-3">
                {sites.map(site => (
                  <div key={site.id} className={`flex items-center justify-between p-4 rounded-xl ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
                    <div>
                      <h4 className={`font-medium ${d ? 'text-white' : 'text-slate-900'}`}>{site.name}</h4>
                      {site.address && <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>{site.address}</p>}
                      {site.bystander_signage_attested_at ? (
                        <p className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" /> Attested: {new Date(site.bystander_signage_attested_at).toLocaleDateString()}
                        </p>
                      ) : (
                        <p className="text-xs text-amber-400 mt-1 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" /> Not yet attested
                        </p>
                      )}
                    </div>
                    {!site.bystander_signage_attested_at && (
                      <button onClick={() => handleSignageAttest(site.id, site.name)}
                        className="px-4 py-2 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/30 rounded-xl text-amber-400 text-sm font-medium">
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
        <div className={`backdrop-blur-xl border rounded-xl overflow-hidden ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
          <div className={`p-6 border-b ${d ? 'border-slate-700/50' : 'border-slate-200'}`}>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-500/20 rounded-xl flex items-center justify-center"><FileStack className="w-5 h-5 text-purple-500" /></div>
              <div>
                <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Data Subject Request Ledger</h3>
                <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>Track DSR requests (access, correction, deletion, objection, restriction) per RA 10173 / NPC guidelines</p>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={`border-b ${d ? 'border-slate-700/50 bg-slate-900/50' : 'border-slate-200 bg-slate-50'}`}>
                  {['Received', 'Due', 'Type', 'Subject', 'Contact', 'Status', 'Outcome'].map(h => (
                    <th key={h} className={`text-left px-6 py-3 text-xs font-semibold uppercase tracking-wider ${d ? 'text-slate-400' : 'text-slate-500'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className={`divide-y ${d ? 'divide-slate-700/50' : 'divide-slate-100'}`}>
                {dsrLoading ? (
                  <tr><td colSpan={7} className="px-6 py-12 text-center text-slate-400">Loading DSR requests...</td></tr>
                ) : dsrRequests.length === 0 ? (
                  <tr><td colSpan={7} className="px-6 py-12 text-center text-slate-400">DSR request listing is not wired to the backend yet</td></tr>
                ) : dsrRequests.map(dsr => (
                  <tr key={dsr.id} className={`transition-colors ${d ? 'hover:bg-slate-800/30' : 'hover:bg-slate-50'}`}>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>{new Date(dsr.received_at).toLocaleDateString()}</td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>{new Date(dsr.due_at).toLocaleDateString()}</td>
                    <td className={`px-6 py-4 text-sm font-medium ${d ? 'text-white' : 'text-slate-900'}`}>{dsr.request_type}</td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>{dsr.subject_type}</td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>{dsr.requester_contact}</td>
                    <td className="px-6 py-4"><span className={`px-3 py-1 rounded-lg text-xs font-semibold ${dsrStatusColor(dsr.status)}`}>{dsr.status}</span></td>
                    <td className={`px-6 py-4 text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>{dsr.outcome || '—'}</td>
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
