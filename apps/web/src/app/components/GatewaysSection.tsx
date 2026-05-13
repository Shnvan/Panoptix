import { Server, Plus, XCircle, CheckCircle, Key, Wifi, Clock, RotateCw, Camera, AlertTriangle, Radio } from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';
import { useTheme } from '../../lib/theme';
import { api, ApiError } from '../../lib/api';

export function GatewaysSection() {
  const { theme } = useTheme();
  const d = theme === 'dark';
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [fingerprint, setFingerprint] = useState('');
  const [creating, setCreating] = useState(false);
  const [oneTimeToken, setOneTimeToken] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [disableModal, setDisableModal] = useState<{ id: string; name: string } | null>(null);
  const [disableReason, setDisableReason] = useState('');
  const [assignModal, setAssignModal] = useState<{ id: string; name: string } | null>(null);
  const [assignCameraId, setAssignCameraId] = useState('');
  const [assignAction, setAssignAction] = useState<'grant' | 'revoke'>('grant');
  const [cmdModal, setCmdModal] = useState<{ id: string; name: string } | null>(null);
  const [commands, setCommands] = useState<Array<{ command_id: string; kind: string; status: string; issued_at: string | null }>>([]);
  const [cmdLoading, setCmdLoading] = useState(false);

  const show = (text: string, type: 'success' | 'error') => { setMsg({ text, type }); setTimeout(() => setMsg(null), 4000); };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) return;
    setCreating(true);
    try {
      const res = await api.createGateway(name, fingerprint || undefined);
      setOneTimeToken(res.service_token);
      show(`Gateway "${name}" created`, 'success');
      setName(''); setFingerprint('');
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed', 'error'); }
    setCreating(false);
  };

  const handleDisable = async () => {
    if (!disableModal || !disableReason) return;
    try {
      await api.disableGateway(disableModal.id, disableReason);
      show(`Gateway "${disableModal.name}" disabled`, 'success');
      setDisableModal(null); setDisableReason('');
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed', 'error'); }
  };

  const handleAssign = async () => {
    if (!assignModal || !assignCameraId) return;
    try {
      await api.manageGatewayCameraAssignment(assignModal.id, assignAction, assignCameraId);
      show(`Camera ${assignAction === 'grant' ? 'assigned to' : 'removed from'} ${assignModal.name}`, 'success');
      setAssignModal(null); setAssignCameraId('');
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed', 'error'); }
  };

  const loadCommands = async (gwId: string, gwName: string) => {
    setCmdModal({ id: gwId, name: gwName });
    setCmdLoading(true);
    try {
      const res = await api.listGatewayCommands(gwId);
      setCommands(res.items.map(c => ({ command_id: c.command_id, kind: c.kind, status: c.status, issued_at: c.issued_at })));
    } catch { setCommands([]); }
    setCmdLoading(false);
  };

  const cancelCmd = async (gwId: string, cmdId: string) => {
    try {
      await api.cancelGatewayCommand(gwId, cmdId);
      show('Command cancelled', 'success');
      if (cmdModal) loadCommands(cmdModal.id, cmdModal.name);
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed', 'error'); }
  };

  const runCleanup = async () => {
    try {
      const res = await api.cleanupCommands();
      show(`Cleaned up ${res.expired_count} expired commands`, 'success');
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed', 'error'); }
  };

  const handleRotate = async (gwId: string, gwName: string) => {
    try {
      const res = await api.rotateGatewayCredential(gwId, 'Routine credential rotation');
      setOneTimeToken(res.service_token);
      show(`Credential rotated for "${gwName}". Copy the new token immediately.`, 'success');
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Credential rotation failed', 'error'); }
  };

  const runMaintenance = async () => {
    try {
      const res = await api.runMaintenance();
      show(`Maintenance: ${res.expired_commands} expired, ${res.stops_enqueued} stops enqueued`, 'success');
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed', 'error'); }
  };

  // Placeholder gateways (real list endpoint not available yet — BACKEND_STATUS says create/disable only)
  const placeholderGateways = [
    { id: 'placeholder-1', name: 'Gateway Alpha', status: 'enabled' as const },
    { id: 'placeholder-2', name: 'Gateway Beta', status: 'enabled' as const },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>Gateway Management</h2>
          <p className={d ? 'text-slate-400' : 'text-slate-500'}>Register gateways, manage assignments, and monitor commands</p>
        </div>
        <div className="flex gap-2">
          <button onClick={runMaintenance} className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${d ? 'bg-slate-800 hover:bg-slate-700 text-slate-300' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}>
            <RotateCw className="w-4 h-4" /> Run Maintenance
          </button>
          <button onClick={runCleanup} className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${d ? 'bg-slate-800 hover:bg-slate-700 text-slate-300' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}>
            <Clock className="w-4 h-4" /> Cleanup Expired
          </button>
          <button onClick={() => setShowCreate(!showCreate)} className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-xl shadow-lg shadow-cyan-500/25 text-sm font-medium">
            <Plus className="w-4 h-4" /> Register Gateway
          </button>
        </div>
      </div>

      {msg && (
        <div className={`p-3 rounded-xl text-sm flex items-center gap-2 ${msg.type === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'}`}>
          {msg.type === 'error' ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          {msg.text}
        </div>
      )}

      {/* One-time token display */}
      {oneTimeToken && (
        <div className="p-4 bg-amber-500/10 border-2 border-amber-500/30 rounded-xl">
          <div className="flex items-start gap-3">
            <Key className="w-5 h-5 text-amber-400 mt-0.5" />
            <div>
              <p className="text-amber-400 font-bold mb-1">⚠ One-Time Service Token — Copy Now!</p>
              <p className={`text-sm mb-3 ${d ? 'text-slate-300' : 'text-slate-600'}`}>This token is shown <strong>only once</strong>. It will not be displayed again. Store it securely on the gateway device.</p>
              <code className={`block p-3 rounded-lg text-sm font-mono break-all ${d ? 'bg-slate-800 text-emerald-400' : 'bg-slate-100 text-emerald-700'}`}>{oneTimeToken}</code>
              <button onClick={() => { navigator.clipboard.writeText(oneTimeToken); show('Token copied to clipboard', 'success'); }}
                className="mt-3 px-4 py-2 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/30 rounded-xl text-amber-400 text-sm font-medium">Copy Token</button>
              <button onClick={() => setOneTimeToken(null)} className="mt-3 ml-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-xl text-slate-300 text-sm">Dismiss</button>
            </div>
          </div>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`backdrop-blur-xl border rounded-xl p-6 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
          <h3 className={`font-semibold mb-4 flex items-center gap-2 ${d ? 'text-white' : 'text-slate-900'}`}><Server className="w-5 h-5 text-cyan-500" /> Register New Gateway</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-slate-300' : 'text-slate-700'}`}>Gateway Name *</label>
                <input type="text" required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Campus-GW-01"
                  className={`w-full rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50 ${d ? 'bg-slate-800/50 border border-slate-700/50 text-white placeholder-slate-500' : 'bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400'}`} />
              </div>
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-slate-300' : 'text-slate-700'}`}>mTLS Fingerprint (optional)</label>
                <input type="text" value={fingerprint} onChange={(e) => setFingerprint(e.target.value)} placeholder="SHA-256 fingerprint"
                  className={`w-full rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50 ${d ? 'bg-slate-800/50 border border-slate-700/50 text-white placeholder-slate-500' : 'bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400'}`} />
              </div>
            </div>
            <p className="text-xs text-amber-400">⚠ A one-time service token will be generated. You must copy it immediately.</p>
            <div className="flex gap-2">
              <button type="button" onClick={() => setShowCreate(false)} className={`px-4 py-2 rounded-xl text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
              <button type="submit" disabled={creating} className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl text-sm font-medium disabled:opacity-50">{creating ? 'Creating...' : 'Create Gateway'}</button>
            </div>
          </form>
        </motion.div>
      )}

      {/* Gateway cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {placeholderGateways.map((gw, i) => (
          <motion.div key={gw.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className={`backdrop-blur-xl border rounded-xl p-5 ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-emerald-500/20 rounded-xl flex items-center justify-center"><Server className="w-5 h-5 text-emerald-400" /></div>
              <div>
                <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>{gw.name}</h3>
                <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /><span className="text-xs text-emerald-400">{gw.status}</span></div>
              </div>
            </div>
            {/* Gateway health dashboard — per core-features §4 */}
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div><div className={`flex items-center gap-1 text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}><Wifi className="w-3 h-3" /> Heartbeat</div><p className={`text-sm font-medium ${d ? 'text-white' : 'text-slate-900'}`}>Active</p></div>
              <div><div className={`flex items-center gap-1 text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}><Clock className="w-3 h-3" /> Last Seen</div><p className={`text-sm font-medium ${d ? 'text-white' : 'text-slate-900'}`}>Just now</p></div>
            </div>
            {/* Control-channel state — per ux-product-spec.md */}
            <div className={`p-3 rounded-xl mb-3 ${d ? 'bg-slate-800/50' : 'bg-slate-50'}`}>
              <div className={`flex items-center gap-1 text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}>
                <Radio className="w-3 h-3" /> Control Channel
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className={`text-sm font-medium ${d ? 'text-emerald-400' : 'text-emerald-600'}`}>WebSocket Connected</span>
              </div>
              <p className={`text-xs mt-1 ${d ? 'text-slate-500' : 'text-slate-400'}`}>
                Outbound TLS · Commands delivered in real-time
              </p>
            </div>
            {/* Cert expiry (pilot) */}
            <div className={`flex items-center gap-2 text-xs mb-4 ${d ? 'text-slate-400' : 'text-slate-500'}`}>
              <Key className="w-3 h-3" />
              <span>Credential: Service Token (MVP) · mTLS: Pilot</span>
            </div>
            <div className={`flex flex-wrap gap-2 pt-3 border-t ${d ? 'border-slate-700/50' : 'border-slate-100'}`}>
              <button onClick={() => setAssignModal({ id: gw.id, name: gw.name })} className={`flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-xl text-xs transition-colors ${d ? 'bg-slate-800/50 hover:bg-slate-700/50 text-white' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}><Camera className="w-3 h-3" /> Assign</button>
              <button onClick={() => loadCommands(gw.id, gw.name)} className={`flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-xl text-xs transition-colors ${d ? 'bg-slate-800/50 hover:bg-slate-700/50 text-white' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}><AlertTriangle className="w-3 h-3" /> Cmds</button>
              <button onClick={() => handleRotate(gw.id, gw.name)} className={`flex-1 flex items-center justify-center gap-1 px-2 py-2 rounded-xl text-xs transition-colors ${d ? 'bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 text-amber-400' : 'bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-700'}`}><RotateCw className="w-3 h-3" /> Rotate</button>
              <button onClick={() => setDisableModal({ id: gw.id, name: gw.name })} className="flex-1 flex items-center justify-center gap-1 px-2 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-xl text-xs text-red-400"><XCircle className="w-3 h-3" /> Disable</button>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Disable Modal */}
      {disableModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setDisableModal(null)}>
          <div className={`border rounded-2xl p-6 max-w-md w-full ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-2 text-red-400">Disable Gateway: {disableModal.name}</h3>
            <p className={`text-sm mb-4 ${d ? 'text-slate-300' : 'text-slate-600'}`}>⚠ This will immediately stop all active publish sessions (within 10 seconds). This action is audited.</p>
            <textarea placeholder="Reason..." value={disableReason} onChange={e => setDisableReason(e.target.value)} className={`w-full rounded-xl px-4 py-2 text-sm min-h-20 mb-4 ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`} />
            <div className="flex gap-2">
              <button onClick={() => { setDisableModal(null); setDisableReason(''); }} className={`flex-1 py-2 rounded-xl text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
              <button onClick={handleDisable} disabled={!disableReason} className="flex-1 py-2 bg-red-500 hover:bg-red-400 text-white rounded-xl text-sm font-medium disabled:opacity-50">Disable</button>
            </div>
          </div>
        </div>
      )}

      {/* Assign Camera Modal */}
      {assignModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setAssignModal(null)}>
          <div className={`border rounded-2xl p-6 max-w-md w-full ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-4 ${d ? 'text-white' : 'text-slate-900'}`}>Camera Assignment: {assignModal.name}</h3>
            <div className="space-y-4">
              <div className="flex gap-2">
                {(['grant', 'revoke'] as const).map(a => (
                  <button key={a} onClick={() => setAssignAction(a)} className={`flex-1 py-2 rounded-xl text-sm font-medium ${assignAction === a ? 'bg-cyan-500 text-white' : d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>{a === 'grant' ? 'Assign Camera' : 'Remove Camera'}</button>
                ))}
              </div>
              <input type="text" placeholder="Camera ID (UUID)" value={assignCameraId} onChange={e => setAssignCameraId(e.target.value)} className={`w-full rounded-xl px-4 py-2.5 text-sm ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`} />
              <p className="text-xs text-amber-400">⚠ Enforces one active assignment per gateway/camera.</p>
              <div className="flex gap-2">
                <button onClick={() => setAssignModal(null)} className={`flex-1 py-2 rounded-xl text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
                <button onClick={handleAssign} disabled={!assignCameraId} className="flex-1 py-2 bg-cyan-500 hover:bg-cyan-400 text-white rounded-xl text-sm font-medium disabled:opacity-50">{assignAction === 'grant' ? 'Assign' : 'Remove'}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Command Queue Modal */}
      {cmdModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setCmdModal(null)}>
          <div className={`border rounded-2xl p-6 max-w-2xl w-full max-h-[80vh] overflow-auto ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-4 ${d ? 'text-white' : 'text-slate-900'}`}>Commands: {cmdModal.name}</h3>
            {cmdLoading ? <p className="text-slate-400">Loading...</p> : commands.length === 0 ? <p className="text-slate-400">No commands found</p> : (
              <table className="w-full text-sm">
                <thead><tr className={`border-b ${d ? 'border-slate-700' : 'border-slate-200'}`}>
                  {['Kind', 'Status', 'Issued', 'Actions'].map(h => <th key={h} className={`text-left px-3 py-2 text-xs font-semibold uppercase ${d ? 'text-slate-400' : 'text-slate-500'}`}>{h}</th>)}
                </tr></thead>
                <tbody>{commands.map(c => (
                  <tr key={c.command_id} className={`border-b ${d ? 'border-slate-800' : 'border-slate-100'}`}>
                    <td className={`px-3 py-2 ${d ? 'text-white' : 'text-slate-900'}`}>{c.kind}</td>
                    <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${c.status === 'pending' ? 'bg-amber-500/20 text-amber-400' : c.status === 'accepted' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-500/20 text-slate-400'}`}>{c.status}</span></td>
                    <td className={`px-3 py-2 font-mono text-xs ${d ? 'text-slate-400' : 'text-slate-500'}`}>{c.issued_at ? new Date(c.issued_at).toLocaleString() : '—'}</td>
                    <td className="px-3 py-2">{c.status === 'pending' && <button onClick={() => cancelCmd(cmdModal.id, c.command_id)} className="text-xs text-red-400 hover:text-red-300">Cancel</button>}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
            <button onClick={() => setCmdModal(null)} className={`mt-4 px-4 py-2 rounded-xl text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
