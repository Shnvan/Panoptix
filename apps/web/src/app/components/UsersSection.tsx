import { Users, Shield, Eye, Search, XCircle, CheckCircle, KeyRound, UserPlus, Mail, Loader2, Inbox } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { useAdminUsers } from '../../lib/hooks';
import { api, ApiError } from '../../lib/api';
import type { VisitorAccessRequest } from '../../lib/types';
import { useCallback, useEffect, useState } from 'react';
import { LoadErrorPanel } from './LoadErrorPanel';

type AccessRequestDecision = 'approve' | 'reject';

function accessRequestDecisionError(err: unknown, action: AccessRequestDecision): string {
  if (err instanceof ApiError) {
    if (err.detail === 'user-disabled') {
      return 'This email belongs to a disabled Panoptix account. Re-enable the account explicitly before approval or invite actions.';
    }
    if (err.detail === 'github-invites-not-configured') {
      return 'GitHub organization invites are not configured in this environment. The request was not approved or invited.';
    }
    if (err.detail === 'access-request-not-pending') {
      return 'This access request was already decided. Refresh the pending list.';
    }
    if (err.detail === 'access-request-not-found') {
      return 'This access request no longer exists. Refresh the pending list.';
    }
    if (err.detail === 'Request validation failed' || err.status === 422 || err.status === 400) {
      return action === 'reject'
        ? 'Enter a clear rejection reason before rejecting this request.'
        : 'Check the approval note and try again.';
    }
    if (err.status >= 500 || err.status === 503) {
      return 'The access-request service is temporarily unavailable. Try again later.';
    }
    return err.detail;
  }
  if (err instanceof TypeError) {
    return 'The access-request service could not be reached. Check the connection and try again.';
  }
  return action === 'approve' ? 'Access request approval failed.' : 'Access request rejection failed.';
}

/**
 * Admin Users - per ux-product-spec.md:
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
  const { users, loading, error: usersError, refetch, loadMore: loadMoreUsers, hasMore: hasMoreUsers } = useAdminUsers();
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [activeTab, setActiveTab] = useState<'requests' | 'users'>('users');
  const [accessRequestsLoaded, setAccessRequestsLoaded] = useState(false);
  const [defaultTabSelected, setDefaultTabSelected] = useState(false);
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
  const [accessRequestsError, setAccessRequestsError] = useState<string | null>(null);
  const [accessRequestsNextCursor, setAccessRequestsNextCursor] = useState<string | null>(null);
  const [accessRequestActionId, setAccessRequestActionId] = useState<string | null>(null);
  const [accessRequestModal, setAccessRequestModal] = useState<{ action: AccessRequestDecision; request: VisitorAccessRequest } | null>(null);
  const [accessDecisionNote, setAccessDecisionNote] = useState('');
  const [accessDecisionError, setAccessDecisionError] = useState<string | null>(null);

  const show = (text: string, type: 'success' | 'error') => { setMsg({ text, type }); setTimeout(() => setMsg(null), 6000); };
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

  const loadAccessRequests = useCallback(async (cursor?: string) => {
    setAccessRequestsLoading(true);
    setAccessRequestsError(null);
    try {
      const res = await api.listAdminAccessRequests(cursor, 50, 'pending');
      setAccessRequests((prev) => (cursor ? [...prev, ...res.items] : res.items));
      setAccessRequestsNextCursor(res.next_cursor);
    } catch (err) {
      if (!cursor) setAccessRequests([]);
      setAccessRequestsError(err instanceof ApiError ? err.detail : 'Access requests could not be loaded.');
    } finally {
      if (!cursor) setAccessRequestsLoaded(true);
      setAccessRequestsLoading(false);
    }
  }, []);

  useEffect(() => { void loadAccessRequests(); }, [loadAccessRequests]);

  useEffect(() => {
    if (!accessRequestsLoaded || defaultTabSelected) return;
    setActiveTab(accessRequests.length > 0 ? 'requests' : 'users');
    setDefaultTabSelected(true);
  }, [accessRequests.length, accessRequestsLoaded, defaultTabSelected]);

  const openAccessRequestDecision = (action: AccessRequestDecision, request: VisitorAccessRequest) => {
    setAccessDecisionError(null);
    setAccessDecisionNote(action === 'approve' ? 'Approved for Panoptix access' : 'Not approved for current rollout');
    setAccessRequestModal({ action, request });
  };

  const closeAccessRequestDecision = () => {
    if (accessRequestActionId) return;
    setAccessRequestModal(null);
    setAccessDecisionNote('');
    setAccessDecisionError(null);
  };

  const submitAccessRequestDecision = async () => {
    if (!accessRequestModal) return;
    const { action, request } = accessRequestModal;
    const note = accessDecisionNote.trim();
    if (action === 'reject' && !note) {
      setAccessDecisionError('Enter a rejection reason before rejecting this access request.');
      return;
    }
    setAccessRequestActionId(request.request_id);
    setAccessDecisionError(null);
    try {
      if (action === 'approve') {
        await api.approveAccessRequest(request.request_id, note || undefined);
        show(`Approved ${request.email} and started the invite workflow`, 'success');
        refetch();
      } else {
        await api.rejectAccessRequest(request.request_id, note);
        show(`Rejected access request for ${request.email}`, 'success');
      }
      setAccessRequestModal(null);
      setAccessDecisionNote('');
      await loadAccessRequests();
      setActiveTab('requests');
    } catch (err) {
      const message = accessRequestDecisionError(err, action);
      setAccessDecisionError(message);
      show(message, 'error');
    } finally {
      setAccessRequestActionId(null);
    }
  };

  const filtered = users.filter((u) => !searchQuery || u.email.toLowerCase().includes(searchQuery.toLowerCase()));
  const requestCountLabel = accessRequestsNextCursor ? `${accessRequests.length}+` : String(accessRequests.length);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-neutral-900'}`}>Users & Access Control</h2>
          <p className={d ? 'text-neutral-400' : 'text-neutral-500'}>Manage user roles, camera access, and account status</p>
        </div>
        <button onClick={() => setInviteModal(true)} className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-400 hover:to-amber-500 text-white rounded-lg shadow-lg shadow-orange-500/25 text-sm font-medium">
          <UserPlus className="w-4 h-4" /> Invite User
        </button>
      </div>

      {msg && (
        <div
          role={msg.type === 'error' ? 'alert' : 'status'}
          aria-live={msg.type === 'error' ? 'assertive' : 'polite'}
          className={`p-3 rounded-lg text-sm flex items-center gap-2 ${msg.type === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'}`}
        >
          {msg.type === 'error' ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}{msg.text}
        </div>
      )}

      <div className={`flex w-full max-w-md rounded-lg border p-1 ${d ? 'border-neutral-700/50 bg-neutral-900/70' : 'border-neutral-200 bg-neutral-100'}`} role="tablist" aria-label="Users and access views">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'requests'}
          onClick={() => setActiveTab('requests')}
          className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${activeTab === 'requests' ? 'bg-orange-500 text-white shadow-sm' : d ? 'text-neutral-300 hover:bg-neutral-800' : 'text-neutral-600 hover:bg-white'}`}
        >
          Access Requests ({requestCountLabel})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'users'}
          onClick={() => setActiveTab('users')}
          className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${activeTab === 'users' ? 'bg-orange-500 text-white shadow-sm' : d ? 'text-neutral-300 hover:bg-neutral-800' : 'text-neutral-600 hover:bg-white'}`}
        >
          Users
        </button>
      </div>

      {activeTab === 'requests' && (
        <div className={`border rounded-lg p-5 ${d ? 'bg-neutral-900/70 border-neutral-700/50' : 'bg-white border-neutral-200'}`} role="tabpanel">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h3 className={`font-semibold ${d ? 'text-white' : 'text-neutral-900'}`}>Access Requests</h3>
              <p className={`text-sm ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>Review public applications before an invite is sent.</p>
            </div>
            <button
              onClick={() => loadAccessRequests()}
              disabled={accessRequestsLoading}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm disabled:opacity-50 ${d ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700' : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'}`}
            >
              {accessRequestsLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Refresh
            </button>
          </div>
          {accessRequestsError && accessRequests.length === 0 && (
            <LoadErrorPanel
              title="Unable to load access requests"
              message={accessRequestsError}
              onRetry={() => { void loadAccessRequests(); }}
            />
          )}
          {accessRequestsLoading && accessRequests.length === 0 ? (
            <p className="text-sm text-neutral-400">Loading access requests...</p>
          ) : accessRequests.length === 0 && !accessRequestsError ? (
            <div className={`rounded-lg border p-8 text-center ${d ? 'border-neutral-700/50 bg-neutral-950/40' : 'border-neutral-200 bg-neutral-50'}`}>
              <Inbox className={`mx-auto mb-3 h-10 w-10 ${d ? 'text-neutral-600' : 'text-neutral-300'}`} />
              <p className="text-sm text-neutral-400">No pending access requests</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-neutral-700/40">
              <div className={`hidden grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,0.8fr)_auto] gap-4 border-b px-4 py-2 text-xs font-semibold uppercase tracking-wide md:grid ${d ? 'border-neutral-700/50 bg-neutral-950/60 text-neutral-400' : 'border-neutral-200 bg-neutral-50 text-neutral-500'}`}>
                <span>Applicant</span>
                <span>Organization</span>
                <span>Submitted</span>
                <span className="text-right">Decision</span>
              </div>
              <div className={d ? 'divide-y divide-neutral-800' : 'divide-y divide-neutral-200'}>
                {accessRequests.map((request) => (
                  <div key={request.request_id} className={`grid gap-3 px-4 py-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,0.8fr)_auto] md:items-center ${d ? 'bg-neutral-950/30' : 'bg-white'}`}>
                    <div className="min-w-0">
                      <p className={`truncate font-semibold ${d ? 'text-white' : 'text-neutral-900'}`}>{request.applicant_name}</p>
                      <p className={`truncate text-sm ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>{request.email}</p>
                      <p className={`mt-1 line-clamp-2 text-sm ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>{request.reason}</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        <span className={`px-2 py-1 rounded ${d ? 'bg-orange-500/15 text-orange-300' : 'bg-orange-50 text-orange-700'}`}>Role: {request.requested_role}</span>
                        {request.visitor_visit_id && <span className={`px-2 py-1 rounded ${d ? 'bg-cyan-500/15 text-cyan-300' : 'bg-cyan-50 text-cyan-700'}`}>Visitor linked</span>}
                      </div>
                    </div>
                    <div className={`text-sm ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>{request.organization || '-'}</div>
                    <div className={`text-sm ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>{request.created_at ? new Date(request.created_at).toLocaleString() : '-'}</div>
                    <div className="flex gap-2 md:justify-end">
                      <button
                        onClick={() => openAccessRequestDecision('approve', request)}
                        disabled={accessRequestActionId === request.request_id}
                        className="px-3 py-2 rounded-lg text-sm bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => openAccessRequestDecision('reject', request)}
                        disabled={accessRequestActionId === request.request_id}
                        className="px-3 py-2 rounded-lg text-sm bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {accessRequestsNextCursor && (
            <div className="pt-4 text-center">
              <button
                onClick={() => loadAccessRequests(accessRequestsNextCursor)}
                disabled={accessRequestsLoading}
                className={`px-3 py-2 rounded-lg text-sm disabled:opacity-50 ${d ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'}`}
              >
                {accessRequestsLoading ? 'Loading...' : 'Load more access requests'}
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'users' && (
        <div className="space-y-4" role="tabpanel">
          {/* Search */}
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <input type="text" aria-label="Search users by email" placeholder="Search users by email..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
              className={`w-full rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${d ? 'bg-neutral-800/50 border border-neutral-700/50 text-white placeholder-neutral-400' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'}`} />
          </div>

          {loading && users.length === 0 ? (
            <div className="text-center py-12 text-neutral-400">Loading users...</div>
          ) : usersError && users.length === 0 ? (
            <LoadErrorPanel title="Unable to load users" message={usersError} onRetry={refetch} />
          ) : filtered.length === 0 ? (
            <div className={`text-center py-12 border rounded-lg ${d ? 'bg-neutral-900/50 border-neutral-700/50' : 'bg-neutral-50 border-neutral-200'}`}>
              <Users className={`w-12 h-12 mx-auto mb-3 ${d ? 'text-neutral-600' : 'text-neutral-300'}`} />
              <p className={d ? 'text-neutral-400' : 'text-neutral-500'}>No users found</p>
            </div>
          ) : (
            <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filtered.map((user, i) => (
            <motion.div key={user.user_id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className={`backdrop-blur-xl border rounded-lg p-5 transition-all hover:shadow-lg ${d ? 'bg-gradient-to-br from-neutral-900/90 to-neutral-800/90 border-neutral-700/50' : 'bg-white border-neutral-200'}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-amber-600 rounded-lg flex items-center justify-center">
                    <Users className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className={`font-semibold ${d ? 'text-white' : 'text-neutral-900'}`}>{user.email.split('@')[0]}</h3>
                    <p className={`text-xs ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>{user.email}</p>
                  </div>
                </div>
                <span className={`px-2.5 py-0.5 rounded-md text-xs font-semibold ${user.disabled_at ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'}`}>
                  {user.disabled_at ? 'disabled' : 'active'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <div className={`flex items-center gap-1 text-xs mb-1 ${d ? 'text-neutral-400' : 'text-neutral-500'}`}><Shield className="w-3 h-3" /> Roles</div>
                  <div className="flex flex-wrap gap-1">
                    {user.roles.length > 0 ? user.roles.map(r => (
                      <span key={r} className={`px-2 py-0.5 rounded text-xs font-medium ${d ? 'bg-orange-500/20 text-orange-400' : 'bg-orange-50 text-orange-700'}`}>{r}</span>
                    )) : <span className="text-xs text-neutral-400">{user.role_default || 'none'}</span>}
                  </div>
                </div>
                <div>
                  <div className={`flex items-center gap-1 text-xs mb-1 ${d ? 'text-neutral-400' : 'text-neutral-500'}`}><Eye className="w-3 h-3" /> Created</div>
                  <p className={`text-sm ${d ? 'text-white' : 'text-neutral-900'}`}>{user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}</p>
                </div>
              </div>

              <div className={`flex gap-2 pt-3 border-t ${d ? 'border-neutral-700/50' : 'border-neutral-100'}`}>
                <button onClick={() => setRoleModal({ userId: user.user_id, email: user.email })}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm transition-colors ${d ? 'bg-neutral-800/50 hover:bg-neutral-700/50 text-white' : 'bg-neutral-100 hover:bg-neutral-200 text-neutral-700'}`}>Edit Roles</button>
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
            {hasMoreUsers && (
              <div className="pt-2 text-center">
                <button
                  onClick={loadMoreUsers}
                  disabled={loading}
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm disabled:opacity-50 ${d ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700' : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'}`}
                >
                  {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Load more users
                </button>
              </div>
            )}
            </>
          )}
        </div>
      )}

      {/* Access Request Decision Modal */}
      {accessRequestModal && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:items-center sm:p-6 bg-black/50"
          onClick={closeAccessRequestDecision}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="access-request-decision-title"
            aria-describedby="access-request-decision-summary"
            className={`relative z-10 my-4 max-h-[calc(100vh-2rem)] w-full max-w-lg overflow-y-auto border rounded-lg p-6 ${d ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'}`}
            onClick={e => e.stopPropagation()}
          >
            <h3
              id="access-request-decision-title"
              className={`text-lg font-bold mb-2 ${accessRequestModal.action === 'approve' ? 'text-emerald-400' : 'text-red-400'}`}
            >
              {accessRequestModal.action === 'approve' ? 'Approve Access Request' : 'Reject Access Request'}
            </h3>
            <div id="access-request-decision-summary" className={`mb-4 text-sm ${d ? 'text-slate-300' : 'text-slate-600'}`}>
              <p className="font-medium">{accessRequestModal.request.applicant_name}</p>
              <p>{accessRequestModal.request.email}</p>
              <p className="mt-2">
                Requested role: <span className="font-semibold">{accessRequestModal.request.requested_role}</span>
              </p>
              <p className="mt-2">
                {accessRequestModal.action === 'approve'
                  ? 'Approval sends the existing GitHub organization invite workflow. It does not bypass disabled-account checks.'
                  : 'Rejection stores the admin reason and removes the request from the pending queue.'}
              </p>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="access-request-decision-note" className={`text-sm font-medium ${d ? 'text-slate-300' : 'text-slate-700'}`}>
                {accessRequestModal.action === 'approve' ? 'Decision note (optional)' : 'Rejection reason *'}
              </label>
              <textarea
                id="access-request-decision-note"
                value={accessDecisionNote}
                onChange={(event) => setAccessDecisionNote(event.target.value)}
                maxLength={2000}
                rows={4}
                aria-invalid={!!accessDecisionError}
                aria-describedby="access-request-decision-error"
                className={`w-full rounded-lg px-4 py-2.5 text-sm min-h-24 ${d ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-50 border-slate-200 text-slate-900'} border`}
              />
            </div>
            {accessDecisionError && (
              <p id="access-request-decision-error" role="alert" className="mt-3 text-sm text-red-400">
                {accessDecisionError}
              </p>
            )}
            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              <button
                onClick={closeAccessRequestDecision}
                disabled={!!accessRequestActionId}
                className={`w-full py-2 rounded-lg text-sm disabled:opacity-50 sm:flex-1 ${d ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600'}`}
              >
                Cancel
              </button>
              <button
                onClick={submitAccessRequestDecision}
                disabled={!!accessRequestActionId}
                className={`w-full py-2 rounded-lg text-sm font-medium disabled:opacity-50 sm:flex-1 ${
                  accessRequestModal.action === 'approve'
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-white'
                    : 'bg-red-500 hover:bg-red-400 text-white'
                }`}
              >
                {accessRequestActionId
                  ? 'Saving...'
                  : accessRequestModal.action === 'approve'
                    ? 'Approve and Invite'
                    : 'Reject Request'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Role Modal */}
      {roleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setRoleModal(null)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-neutral-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-4 ${d ? 'text-white' : 'text-neutral-900'}`}>Manage Role: {roleModal.email}</h3>
            <div className="space-y-4">
              <div className="flex gap-2">
                {(['grant', 'revoke'] as const).map(a => (
                  <button key={a} onClick={() => setRoleAction(a)} className={`flex-1 py-2 rounded-lg text-sm font-medium ${roleAction === a ? 'bg-orange-500 text-white' : d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>{a.charAt(0).toUpperCase() + a.slice(1)}</button>
                ))}
              </div>
              <select value={roleName} onChange={e => setRoleName(e.target.value)} className={`w-full rounded-lg px-4 py-2.5 text-sm ${d ? 'bg-neutral-800 border-neutral-700 text-white' : 'bg-neutral-50 border-neutral-200 text-neutral-900'} border`}>
                <option value="admin">admin</option>
                <option value="viewer">viewer</option>
              </select>
              <p className="text-xs text-amber-400">Warning: this action is audited. Role changes take effect immediately.</p>
              <div className="flex gap-2">
                <button onClick={() => setRoleModal(null)} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
                <button onClick={handleRoleUpdate} className="flex-1 py-2 bg-orange-500 hover:bg-orange-400 text-white rounded-lg text-sm font-medium">Confirm</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MFA Reset Modal */}
      {mfaModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setMfaModal(null)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-neutral-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-2 ${d ? 'text-white' : 'text-neutral-900'}`}>Reset MFA: {mfaModal.email}</h3>
            <p className={`text-sm mb-4 ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
              Warning: this will reset the MFA configuration for this user. They will need to re-enroll MFA on their next login. This action is <strong>admin-mediated only</strong> and is audited.
            </p>
            <div className="flex gap-2">
              <button onClick={() => setMfaModal(null)} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
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
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-neutral-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-4 flex items-center gap-2 ${d ? 'text-white' : 'text-neutral-900'}`}>
              <Mail className="w-5 h-5 text-orange-500" /> Invite User
            </h3>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-neutral-300' : 'text-neutral-700'}`}>Email Address *</label>
                <input type="email" required value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="user@example.com"
                  className={`w-full rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${d ? 'bg-neutral-800 border-neutral-700 text-white' : 'bg-neutral-50 border-neutral-200 text-neutral-900'} border`} />
              </div>
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-neutral-300' : 'text-neutral-700'}`}>Roles (comma separated)</label>
                <input type="text" value={inviteRoles} onChange={e => setInviteRoles(e.target.value)} placeholder="viewer"
                  className={`w-full rounded-lg px-4 py-2.5 text-sm ${d ? 'bg-neutral-800 border-neutral-700 text-white' : 'bg-neutral-50 border-neutral-200 text-neutral-900'} border`} />
              </div>
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-neutral-300' : 'text-neutral-700'}`}>Reason (optional)</label>
                <input type="text" value={inviteReason} onChange={e => setInviteReason(e.target.value)} placeholder="New team member"
                  className={`w-full rounded-lg px-4 py-2.5 text-sm ${d ? 'bg-neutral-800 border-neutral-700 text-white' : 'bg-neutral-50 border-neutral-200 text-neutral-900'} border`} />
              </div>
              <p className="text-xs text-amber-400">Warning: this will create a user record and send a GitHub org invitation. Audited.</p>
              <div className="flex gap-2">
                <button onClick={() => setInviteModal(false)} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
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
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-neutral-200'}`} onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-2 text-red-400">Disable User</h3>
            <p className={`text-sm mb-4 ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
              Warning: this will immediately revoke <strong>all active sessions</strong> and remove <strong>LiveKit participants</strong> for {disableModal.email} within 10 seconds. This action is audited.
            </p>
            <textarea placeholder="Reason for disabling..." value={disableReason} onChange={e => setDisableReason(e.target.value)}
              className={`w-full rounded-lg px-4 py-2.5 text-sm mb-4 min-h-20 ${d ? 'bg-neutral-800 border-neutral-700 text-white' : 'bg-neutral-50 border-neutral-200 text-neutral-900'} border`} />
            <div className="flex gap-2">
              <button onClick={() => { setDisableModal(null); setDisableReason(''); }} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
              <button onClick={handleDisable} disabled={!disableReason} className="flex-1 py-2 bg-red-500 hover:bg-red-400 text-white rounded-lg text-sm font-medium disabled:opacity-50">Disable User</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
