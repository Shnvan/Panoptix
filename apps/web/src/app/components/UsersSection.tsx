import { Users, Shield, Eye, Search, XCircle, CheckCircle, KeyRound, UserPlus, Mail } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { useAdminUsers } from '../../lib/hooks';
import { api, ApiError } from '../../lib/api';
import type { VisitorAccessRequest } from '../../lib/types';
import { useCallback, useEffect, useState } from 'react';

/**
 * Admin Users — per ux-product-spec.md:
 * - User list with role and disabled status
 * - Role/permission editing with confirmation
 * - MFA reset flow (wired to POST /admin/users/:id/mfa/reset)
 * - User invite (wired to POST /admin/users/invite)
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
  const [mfaModal, setMfaModal] = useState<{ userId: string; email: string } | null>(null);
  const [mfaLoading, setMfaLoading] = useState(false);
  const [inviteModal, setInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRoles, setInviteRoles] = useState('viewer');
  const [inviteReason, setInviteReason] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [accessRequests, setAccessRequests] = useState<VisitorAccessRequest[]>([]);
  const [accessRequestsLoading, setAccessRequestsLoading] = useState(false);
  const [accessRequestActionId, setAccessRequestActionId] = useState<string | null>(null);

  const show = (text: string, type: 'success' | 'error') => { setMsg({ text, type }); setTimeout(() => setMsg(null), 4000); };
  const userActionError = (err: unknown, fallback: string) => {
    if (err instanceof ApiError && err.detail === 'user-disabled') {
      return 'This Panoptix account is disabled. Re-enable it explicitly before changing roles or sending another invite.';
    }
    return err instanceof ApiError ? err.detail : fallback;
  };

  const handleRoleUpdate = async () => {
    if (!roleModal) return;
    try {
      await api.updateUserRole(roleModal.userId, roleAction, roleName);
      show(`Role "${roleName}" ${roleAction}ed for ${roleModal.email}`, 'success');
      setRoleModal(null); refetch();
    } catch (err) { show(userActionError(err, 'Failed to update role'), 'error'); }
  };

  const handleDisable = async () => {
    if (!disableModal || !disableReason) return;
    try {
      const result = await api.disableUser(disableModal.userId, disableReason);
      show(`User disabled. ${result.sessions_revoked} session(s) revoked.`, 'success');
      setDisableModal(null); setDisableReason(''); refetch();
    } catch (err) { show(err instanceof ApiError ? err.detail : 'Failed to disable user', 'error'); }
  };

  const handleMfaReset = async () => {
    if (!mfaModal) return;
    setMfaLoading(true);
    try {
      await api.resetUserMfa(mfaModal.userId);
      show(`MFA reset for ${mfaModal.email}`, 'success');
      setMfaModal(null);
    } catch (err) { show(userActionError(err, 'MFA reset failed'), 'error'); }
    setMfaLoading(false);
  };

  const handleInvite = async () => {
    if (!inviteEmail) return;
    setInviteLoading(true);
    try {
      const res = await api.inviteUser({
        email: inviteEmail,
        role_names: inviteRoles.split(',').map(r => r.trim()).filter(Boolean),
        reason: inviteReason || undefined,
      });
      show(`Invited ${res.email}. Next: ${res.next_step}`, 'success');
      setInviteModal(false); setInviteEmail(''); setInviteRoles('viewer'); setInviteReason('');
      refetch();
    } catch (err) { show(userActionError(err, 'Invite failed'), 'error'); }
    setInviteLoading(false);
  };

  const loadAccessRequests = useCallback(async () => {
    setAccessRequestsLoading(true);
    try {
      const res = await api.listAdminAccessRequests(undefined, 50, 'pending');
      setAccessRequests(res.items);
    } catch {
      setAccessRequests([]);
    } finally {
      setAccessRequestsLoading(false);
    }
  }, []);

  useEffect(() => { void loadAccessRequests(); }, [loadAccessRequests]);

  const handleApproveAccessRequest = async (request: VisitorAccessRequest) => {
    if (!window.confirm(`Approve access request for ${request.email} and send a GitHub invite?`)) return;
    const decisionNote = window.prompt('Decision note (optional)', 'Approved for Panoptix access') || undefined;
    setAccessRequestActionId(request.request_id);
    try {
      await api.approveAccessRequest(request.request_id, decisionNote);
      show(`Approved ${request.email} and sent invite workflow`, 'success');
      await loadAccessRequests();
      refetch();
    } catch (err) {
      show(userActionError(err, 'Access request approval failed'), 'error');
    } finally {
      setAccessRequestActionId(null);
    }
  };

  const handleRejectAccessRequest = async (request: VisitorAccessRequest) => {
    const decisionNote = window.prompt(`Reason for rejecting ${request.email}`, 'Not approved for current rollout');
    if (decisionNote === null) return;
    setAccessRequestActionId(request.request_id);
    try {
      await api.rejectAccessRequest(request.request_id, decisionNote || undefined);
      show(`Rejected access request for ${request.email}`, 'success');
      await loadAccessRequests();
    } catch (err) {
      show(err instanceof ApiError ? err.detail : 'Access request rejection failed', 'error');
    } finally {
      setAccessRequestActionId(null);
    }
  };

  const filtered = users.filter((u) => !searchQuery || u.email.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-slate-900'}`}>Users & Access Control</h2>
          <p className={d ? 'text-slate-400' : 'text-slate-500'}>Manage user roles, camera access, and account status</p>
        </div>
        <button onClick={() => setInviteModal(true)} className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-400 hover:to-amber-500 text-white rounded-lg shadow-lg shadow-orange-500/25 text-sm font-medium">
          <UserPlus className="w-4 h-4" /> Invite User
        </button>
      </div>

      {msg && (
        <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${msg.type === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'}`}>
          {msg.type === 'error' ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}{msg.text}
        </div>
      )}

      <div className={`border rounded-lg p-5 ${d ? 'bg-slate-900/70 border-slate-700/50' : 'bg-white border-slate-200'}`}>
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>Access Requests</h3>
            <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>Public applications from the entry page require admin approval before an invite is sent.</p>
          </div>
          <button onClick={loadAccessRequests} className={`px-3 py-2 rounded-lg text-sm ${d ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}>
            Refresh
          </button>
        </div>
        {accessRequestsLoading ? (
          <p className="text-sm text-slate-400">Loading access requests...</p>
        ) : accessRequests.length === 0 ? (
          <p className="text-sm text-slate-400">No pending access requests</p>
        ) : (
          <div className="space-y-3">
            {accessRequests.map((request) => (
              <div key={request.request_id} className={`rounded-lg border p-4 ${d ? 'border-slate-700/50 bg-slate-950/40' : 'border-slate-200 bg-slate-50'}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>{request.applicant_name}</p>
                    <p className={`text-sm ${d ? 'text-slate-400' : 'text-slate-500'}`}>{request.email}</p>
                    <p className={`mt-1 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>{request.reason}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className={`px-2 py-1 rounded ${d ? 'bg-orange-500/15 text-orange-300' : 'bg-orange-50 text-orange-700'}`}>Role: {request.requested_role}</span>
                      {request.organization && <span className={`px-2 py-1 rounded ${d ? 'bg-slate-800 text-slate-300' : 'bg-white text-slate-600'}`}>{request.organization}</span>}
                      {request.visitor_visit_id && <span className={`px-2 py-1 rounded ${d ? 'bg-cyan-500/15 text-cyan-300' : 'bg-cyan-50 text-cyan-700'}`}>Visitor linked</span>}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleApproveAccessRequest(request)}
                      disabled={accessRequestActionId === request.request_id}
                      className="px-3 py-2 rounded-lg text-sm bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleRejectAccessRequest(request)}
                      disabled={accessRequestActionId === request.request_id}
                      className="px-3 py-2 rounded-lg text-sm bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input type="text" placeholder="Search users by email..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
          className={`w-full rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${d ? 'bg-slate-800/50 border border-slate-700/50 text-white placeholder-slate-400' : 'bg-slate-50 border border-slate-200 text-slate-900 placeholder-slate-400'}`} />
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading users...</div>
      ) : filtered.length === 0 ? (
        <div className={`text-center py-12 border rounded-lg ${d ? 'bg-slate-900/50 border-slate-700/50' : 'bg-slate-50 border-slate-200'}`}>
          <Users className={`w-12 h-12 mx-auto mb-3 ${d ? 'text-slate-600' : 'text-slate-300'}`} />
          <p className={d ? 'text-slate-400' : 'text-slate-500'}>No users found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((user, i) => (
            <motion.div key={user.user_id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className={`backdrop-blur-xl border rounded-lg p-5 transition-all hover:shadow-lg ${d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50' : 'bg-white border-slate-200'}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-amber-600 rounded-lg flex items-center justify-center">
                    <Users className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className={`font-semibold ${d ? 'text-white' : 'text-slate-900'}`}>{user.email.split('@')[0]}</h3>
                    <p className={`text-xs ${d ? 'text-slate-400' : 'text-slate-500'}`}>{user.email}</p>
                  </div>
                </div>
                <span className={`px-2.5 py-0.5 rounded-md text-xs font-semibold ${user.disabled_at ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'}`}>
                  {user.disabled_at ? 'disabled' : 'active'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <div className={`flex items-center gap-1 text-xs mb-1 ${d ? 'text-slate-400' : 'text-slate-500'}`}><Shield className="w-3 h-3" /> Roles</div>
                  <div className="flex flex-wrap gap-1">
                    {user.roles.length > 0 ? user.roles.map(r => (
                      <span key={r} className={`px-2 py-0.5 rounded text-xs font-medium ${d ? 'bg-orange-500/20 text-orange-400' : 'bg-orange-50 text-orange-700'}`}>{r}</span>
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
                  className={`flex-1 px-3 py-2 rounded-lg text-sm transition-colors ${d ? 'bg-slate-800/50 hover:bg-slate-700/50 text-white' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'}`}>Edit Roles</button>
                <button onClick={() => setMfaModal({ userId: user.user_id, email: user.email })}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm transition-colors ${d ? 'bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 text-amber-400' : 'bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-700'}`}>
                  <KeyRound className="w-3 h-3 inline mr-1" />MFA Reset
                </button>
                {!user.disabled_at && (
                  <button onClick={() => setDisableModal({ userId: user.user_id, email: user.email })}
                    className="px-3 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg text-sm text-red-400 transition-colors">Disable</button>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Role Modal */}
      {roleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setRoleModal(null)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-4 ${d ? 'text-white' : 'text-slate-900'}`}>Manage Role: {roleModal.email}</h3>
            <div className="space-y-4">
              <div className="flex gap-2">
                {(['grant', 'revoke'] as const).map(a => (
                  <button key={a} onClick={() => setRoleAction(a)} className={`flex-1 py-2 rounded-lg text-sm font-medium ${roleAction === a ? 'bg-orange-500 text-white' : d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>{a.charAt(0).toUpperCase() + a.slice(1)}</button>
                ))}
              </div>
              <select value={roleName} onChange={e => setRoleName(e.target.value)} className={`w-full rounded-lg px-4 py-2.5 text-sm ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`}>
                <option value="admin">admin</option>
                <option value="viewer">viewer</option>
              </select>
              <p className="text-xs text-amber-400">⚠ This action is audited. Role changes take effect immediately.</p>
              <div className="flex gap-2">
                <button onClick={() => setRoleModal(null)} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
                <button onClick={handleRoleUpdate} className="flex-1 py-2 bg-orange-500 hover:bg-orange-400 text-white rounded-lg text-sm font-medium">Confirm</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MFA Reset Modal */}
      {mfaModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setMfaModal(null)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-2 ${d ? 'text-white' : 'text-slate-900'}`}>Reset MFA: {mfaModal.email}</h3>
            <p className={`text-sm mb-4 ${d ? 'text-slate-300' : 'text-slate-600'}`}>
              ⚠ This will reset the MFA configuration for this user. They will need to re-enroll MFA on their next login. This action is <strong>admin-mediated only</strong> and is audited.
            </p>
            <div className="flex gap-2">
              <button onClick={() => setMfaModal(null)} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
              <button onClick={handleMfaReset} disabled={mfaLoading} className="flex-1 py-2 bg-amber-500 hover:bg-amber-400 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                {mfaLoading ? 'Resetting...' : 'Confirm Reset'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Invite User Modal */}
      {inviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setInviteModal(false)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-4 flex items-center gap-2 ${d ? 'text-white' : 'text-slate-900'}`}>
              <Mail className="w-5 h-5 text-orange-500" /> Invite User
            </h3>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-slate-300' : 'text-slate-700'}`}>Email Address *</label>
                <input type="email" required value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="user@example.com"
                  className={`w-full rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`} />
              </div>
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-slate-300' : 'text-slate-700'}`}>Roles (comma separated)</label>
                <input type="text" value={inviteRoles} onChange={e => setInviteRoles(e.target.value)} placeholder="viewer"
                  className={`w-full rounded-lg px-4 py-2.5 text-sm ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`} />
              </div>
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-slate-300' : 'text-slate-700'}`}>Reason (optional)</label>
                <input type="text" value={inviteReason} onChange={e => setInviteReason(e.target.value)} placeholder="New team member"
                  className={`w-full rounded-lg px-4 py-2.5 text-sm ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`} />
              </div>
              <p className="text-xs text-amber-400">⚠ This will create a user record and send a GitHub org invitation. Audited.</p>
              <div className="flex gap-2">
                <button onClick={() => setInviteModal(false)} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
                <button onClick={handleInvite} disabled={inviteLoading || !inviteEmail} className="flex-1 py-2 bg-orange-500 hover:bg-orange-400 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                  {inviteLoading ? 'Inviting...' : 'Send Invite'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Disable Modal */}
      {disableModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setDisableModal(null)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-2 text-red-400">Disable User</h3>
            <p className={`text-sm mb-4 ${d ? 'text-slate-300' : 'text-slate-600'}`}>
              ⚠ This will immediately revoke <strong>all active sessions</strong> and remove <strong>LiveKit participants</strong> for {disableModal.email} (within 10 seconds). This action is audited.
            </p>
            <textarea placeholder="Reason for disabling..." value={disableReason} onChange={e => setDisableReason(e.target.value)}
              className={`w-full rounded-lg px-4 py-2.5 text-sm mb-4 min-h-20 ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`} />
            <div className="flex gap-2">
              <button onClick={() => { setDisableModal(null); setDisableReason(''); }} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}>Cancel</button>
              <button onClick={handleDisable} disabled={!disableReason} className="flex-1 py-2 bg-red-500 hover:bg-red-400 text-white rounded-lg text-sm font-medium disabled:opacity-50">Disable User</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
