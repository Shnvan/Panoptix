import { Users, Shield, Eye, Search, XCircle, CheckCircle, Construction, KeyRound } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { useAdminUsers } from '../../lib/hooks';
import { api, ApiError } from '../../lib/api';
import { useState } from 'react';

/**
 * Admin Users — per ux-product-spec.md:
 * - User list with role and disabled status
 * - Role/permission editing with confirmation
 * - MFA reset flow (NOT READY → "In Progress")
 * - Disable user action with warning that sessions + LiveKit terminate
 *
 * Per core-functionality: No self-registration. Users are added through the configured identity provider.
 */
export function UsersSection() {
  const { theme } = useTheme();
  const d = theme === 'dark';
  const { users, loading, refetch } = useAdminUsers();
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [roleModal, setRoleModal] = useState<{ userId: string; email: string } | null>(null);
  const [roleName, setRoleName] = useState('viewer');
  const [roleAction, setRoleAction] = useState<'grant' | 'revoke'>('grant');
  const [disableModal, setDisableModal] = useState<{ userId: string; email: string } | null>(null);
  const [disableReason, setDisableReason] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const show = (text: string, type: 'success' | 'error') => { setMsg({ text, type }); setTimeout(() => setMsg(null), 4000); };

  const handleRoleUpdate = async () => {
    if (!roleModal) return;
    try {
      await api.updateUserRole(roleModal.userId, roleAction, roleName);
      show(`Role "${roleName}" ${roleAction}ed for ${roleModal.email}`, 'success');
      setRoleModal(null); refetch();
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed to update role', 'error'); }
  };

  const handleDisable = async () => {
    if (!disableModal || !disableReason) return;
    try {
      const result = await api.disableUser(disableModal.userId, disableReason);
      show(`User disabled. ${result.sessions_revoked} session(s) revoked.`, 'success');
      setDisableModal(null); setDisableReason(''); refetch();
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed to disable user', 'error'); }
  };

  const filtered = users.filter((u) => !searchQuery || u.email.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>Users & Access Control</h2>
          <p className={d ? 'text-slate-400' : 'text-slate-500'}>Manage user roles, camera access, and account status</p>
        </div>
        <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>
          Users are added through the configured identity provider. No self-registration.
        </p>
      </div>

      {msg && (
        <div className={`p-3 rounded-xl text-sm flex items-center gap-2 ${msg.type === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'}`}>
          {msg.type === 'error' ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}{msg.text}
        </div>
      )}

      {/* MFA Reset — NOT IMPLEMENTED per BACKEND_STATUS.md */}
      <div className={`p-4 border rounded-xl flex items-center gap-3 ${d ? 'bg-amber-500/5 border-amber-500/20' : 'bg-amber-50 border-amber-200'}`}>
        <Construction className="w-5 h-5 text-amber-400 flex-shrink-0" />
        <div>
          <p className={`text-sm font-medium ${d ? 'text-amber-400' : 'text-amber-700'}`}>
            <KeyRound className="w-4 h-4 inline mr-1" />MFA Reset — In Progress
          </p>
          <p className={`text-xs ${d ? 'text-slate-400' : 'text-slate-500'}`}>
            POST /admin/users/:id/mfa/reset is not yet implemented. Users cannot reset their own MFA — this is admin-mediated only.
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input type="text" placeholder="Search users by email..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
          className={`w-full rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/50 ${d ? 'bg-slate-800/50 border border-slate-700/50 text-white placeholder-slate-400' : 'bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400'}`} />
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading users...</div>
      ) : filtered.length === 0 ? (
        <div className={`text-center py-12 border rounded-xl ${d ? 'bg-slate-900/50 border-slate-700/50' : 'bg-slate-50 border-slate-200'}`}>
          <Users className={`w-12 h-12 mx-auto mb-3 ${d ? 'text-slate-600' : 'text-slate-300'}`} />
          <p className={d ? 'text-slate-400' : 'text-slate-500'}>No users found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((user, i) => (
            <motion.div key={user.user_id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className={`backdrop-blur-xl border rounded-xl p-5 transition-all hover:shadow-lg ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-xl flex items-center justify-center">
                    <Users className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>{user.email.split('@')[0]}</h3>
                    <p className={`text-xs ${d ? 'text-slate-400' : 'text-slate-500'}`}>{user.email}</p>
                  </div>
                </div>
                <span className={`px-2.5 py-0.5 rounded-lg text-xs font-semibold ${user.disabled_at ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'}`}>
                  {user.disabled_at ? 'disabled' : 'active'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <div className={`flex items-center gap-1 text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}><Shield className="w-3 h-3" /> Roles</div>
                  <div className="flex flex-wrap gap-1">
                    {user.roles.length > 0 ? user.roles.map(r => (
                      <span key={r} className={`px-2 py-0.5 rounded text-xs font-medium ${d ? 'bg-cyan-500/20 text-cyan-400' : 'bg-cyan-50 text-cyan-700'}`}>{r}</span>
                    )) : <span className="text-xs text-slate-400">{user.role_default || 'none'}</span>}
                  </div>
                </div>
                <div>
                  <div className={`flex items-center gap-1 text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}><Eye className="w-3 h-3" /> Created</div>
                  <p className={`text-sm ${d ? 'text-white' : 'text-slate-900'}`}>{user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</p>
                </div>
              </div>

              <div className={`flex gap-2 pt-3 border-t ${d ? 'border-slate-700/50' : 'border-slate-100'}`}>
                <button onClick={() => setRoleModal({ userId: user.user_id, email: user.email })}
                  className={`flex-1 px-3 py-2 rounded-xl text-sm transition-colors ${d ? 'bg-slate-800/50 hover:bg-slate-700/50 text-white' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}>Edit Roles</button>
                {!user.disabled_at && (
                  <button onClick={() => setDisableModal({ userId: user.user_id, email: user.email })}
                    className="flex-1 px-3 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-xl text-sm text-red-400 transition-colors">Disable</button>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Role Modal */}
      {roleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setRoleModal(null)}>
          <div className={`border rounded-2xl p-6 max-w-md w-full ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-4 ${d ? 'text-white' : 'text-slate-900'}`}>Manage Role: {roleModal.email}</h3>
            <div className="space-y-4">
              <div className="flex gap-2">
                {(['grant', 'revoke'] as const).map(a => (
                  <button key={a} onClick={() => setRoleAction(a)} className={`flex-1 py-2 rounded-xl text-sm font-medium ${roleAction === a ? 'bg-cyan-500 text-white' : d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>{a.charAt(0).toUpperCase() + a.slice(1)}</button>
                ))}
              </div>
              <select value={roleName} onChange={e => setRoleName(e.target.value)} className={`w-full rounded-xl px-4 py-2.5 text-sm ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`}>
                <option value="admin">admin</option>
                <option value="viewer">viewer</option>
              </select>
              <p className="text-xs text-amber-400">⚠ This action is audited. Role changes take effect immediately. By default, no user holds both viewer and admin roles unless explicitly approved.</p>
              <div className="flex gap-2">
                <button onClick={() => setRoleModal(null)} className={`flex-1 py-2 rounded-xl text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
                <button onClick={handleRoleUpdate} className="flex-1 py-2 bg-cyan-500 hover:bg-cyan-400 text-white rounded-xl text-sm font-medium">Confirm</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Disable Modal */}
      {disableModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setDisableModal(null)}>
          <div className={`border rounded-2xl p-6 max-w-md w-full ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-2 text-red-400">Disable User</h3>
            <p className={`text-sm mb-4 ${d ? 'text-slate-300' : 'text-slate-600'}`}>
              ⚠ This will immediately revoke <strong>all active sessions</strong> and remove <strong>LiveKit participants</strong> for {disableModal.email} (within 10 seconds). This action is audited.
            </p>
            <textarea placeholder="Reason for disabling..." value={disableReason} onChange={e => setDisableReason(e.target.value)}
              className={`w-full rounded-xl px-4 py-2.5 text-sm mb-4 min-h-20 ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`} />
            <div className="flex gap-2">
              <button onClick={() => { setDisableModal(null); setDisableReason(''); }} className={`flex-1 py-2 rounded-xl text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
              <button onClick={handleDisable} disabled={!disableReason} className="flex-1 py-2 bg-red-500 hover:bg-red-400 text-white rounded-xl text-sm font-medium disabled:opacity-50">Disable User</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
