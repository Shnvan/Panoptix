import { Camera, Plus, Shield, UserPlus, XCircle, CheckCircle, Search, Trash2, Power, Copy, Filter, Loader2 } from 'lucide-react';
import { motion } from 'motion/react';
import { useMemo, useState } from 'react';
import { useTheme } from '../../lib/theme';
import { useAdminCameras } from '../../lib/hooks';
import { LoadErrorPanel } from './LoadErrorPanel';
import { api, ApiError } from '../../lib/api';
import type { CameraSourceType } from '../../lib/types';

type CreatedCameraPanel = {
  cameraId: string;
  displayName: string;
  livekitRoomName: string;
};

/**
 * Admin Camera Management - ux-product-spec.md "Admin cameras and gateways"
 * 
 * Required elements:
 * - Camera registration form: name, source type, gateway assignment (livekit_room_name)
 * - Grant/revoke camera ACL by user email
 * - Disable/retire camera with warning
 * - Enable camera (POST /admin/cameras/:id/enable)
 * 
 * All mutations are CSRF-protected and audited.
 */
export function CamerasManageSection() {
  const { theme } = useTheme();
  const { cameras, loading, error, refetch, loadMore, hasMore } = useAdminCameras();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [actionMsg, setActionMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [createdCamera, setCreatedCamera] = useState<CreatedCameraPanel | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'retired'>('all');
  const [sourceFilter, setSourceFilter] = useState<'all' | CameraSourceType>('all');

  // Create camera form state
  const [newName, setNewName] = useState('');
  const [newSourceType, setNewSourceType] = useState<CameraSourceType>('rtsp');
  const [newRoomName, setNewRoomName] = useState('');
  const [creating, setCreating] = useState(false);

  // ACL form state
  const [aclModal, setAclModal] = useState<{ cameraId: string; displayName: string } | null>(null);
  const [aclEmail, setAclEmail] = useState('');
  const [aclAction, setAclAction] = useState<'grant' | 'revoke'>('grant');

  // Disable modal
  const [disableModal, setDisableModal] = useState<{ cameraId: string; displayName: string } | null>(null);
  const [disableReason, setDisableReason] = useState('');

  const showMsg = (text: string, type: 'success' | 'error') => {
    setActionMsg({ text, type });
    setTimeout(() => setActionMsg(null), 4000);
  };

  const copyValue = (label: string, value: string) => {
    void navigator.clipboard?.writeText(value);
    showMsg(`${label} copied to clipboard`, 'success');
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName || !newRoomName) return;
    setCreating(true);
    try {
      const res = await api.createCamera(newName, newSourceType, newRoomName);
      setCreatedCamera({
        cameraId: res.camera_id,
        displayName: res.display_name || newName,
        livekitRoomName: res.livekit_room_name || newRoomName,
      });
      showMsg(`Camera "${res.display_name || newName}" created successfully`, 'success');
      setNewName(''); setNewRoomName(''); setShowCreateForm(false);
      refetch();
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : 'Failed to create camera';
      showMsg(detail, 'error');
    }
    setCreating(false);
  };

  const handleAcl = async () => {
    if (!aclModal || !aclEmail) return;
    try {
      await api.manageCameraAcl(aclModal.cameraId, aclAction, aclEmail);
      showMsg(`ACL ${aclAction} for ${aclEmail} on ${aclModal.displayName}`, 'success');
      setAclModal(null); setAclEmail('');
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'ACL operation failed', 'error');
    }
  };

  const handleDisable = async () => {
    if (!disableModal || !disableReason) return;
    try {
      await api.disableCamera(disableModal.cameraId, disableReason);
      showMsg(`Camera "${disableModal.displayName}" retired`, 'success');
      setDisableModal(null); setDisableReason('');
      refetch();
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'Failed to disable camera', 'error');
    }
  };

  const handleEnable = async (cameraId: string, displayName: string) => {
    try {
      await api.enableCamera(cameraId);
      showMsg(`Camera "${displayName}" enabled`, 'success');
      refetch();
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'Failed to enable camera', 'error');
    }
  };

  /**
   * Source types per v4 section 14.4.
   * 'phone','webcam','browser','browser_publisher','user_device','mobile_camera'
   * are permanently excluded (Inv 5).
   */
  const sourceTypes: CameraSourceType[] = [
    'rtsp', 'nvr_rtsp', 'onvif_profile_s', 'onvif_profile_t', 'synthetic_rtsp_test_source',
  ];

  const sourceTypeLabels: Record<CameraSourceType, string> = {
    rtsp: 'RTSP (Direct IP Camera)',
    nvr_rtsp: 'NVR RTSP',
    onvif_profile_s: 'ONVIF Profile S',
    onvif_profile_t: 'ONVIF Profile T',
    synthetic_rtsp_test_source: 'Synthetic Test Source (Dev/CI)',
  };

  const d = theme === 'dark';
  const filteredCameras = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return cameras.filter((cam) => {
      const isRetired = !!cam.retired_at;
      const statusMatches =
        statusFilter === 'all'
        || (statusFilter === 'active' && !isRetired)
        || (statusFilter === 'retired' && isRetired);
      const sourceMatches = sourceFilter === 'all' || cam.source_type === sourceFilter;
      const searchMatches = !q
        || cam.display_name.toLowerCase().includes(q)
        || cam.livekit_room_name.toLowerCase().includes(q)
        || cam.camera_id.toLowerCase().includes(q);
      return statusMatches && sourceMatches && searchMatches;
    });
  }, [cameras, searchQuery, sourceFilter, statusFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className={`text-2xl font-bold mb-1 ${d ? 'text-white' : 'text-neutral-900'}`}>Camera Management</h2>
          <p className={d ? 'text-neutral-400' : 'text-neutral-500'}>Register cameras, manage user access, and retire cameras</p>
        </div>
        <button onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-400 hover:to-amber-500 text-white rounded-lg shadow-lg shadow-orange-500/25 transition-all text-sm font-medium">
          <Plus className="w-4 h-4" /> Register Camera
        </button>
      </div>

      {/* Status messages */}
      {actionMsg && (
        <div role={actionMsg.type === 'error' ? 'alert' : 'status'} className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
          actionMsg.type === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
        }`}>
          {actionMsg.type === 'error' ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          {actionMsg.text}
        </div>
      )}

      {createdCamera && (
        <div className="p-4 bg-sky-500/10 border-2 border-sky-500/30 rounded-lg">
          <div className="flex items-start gap-3">
            <Camera className="w-5 h-5 text-sky-300 mt-0.5" />
            <div className="min-w-0 flex-1">
              <p className="font-bold text-sky-300 mb-1">Camera registered</p>
              <p className={`text-sm mb-3 ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
                Copy this camera ID for gateway assignment. The camera ID stays visible on the camera card.
              </p>
              <dl className="space-y-3">
                <div>
                  <dt className={`text-xs font-semibold uppercase tracking-wide ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>Camera name</dt>
                  <dd className={`text-sm font-medium ${d ? 'text-white' : 'text-neutral-900'}`}>{createdCamera.displayName}</dd>
                </div>
                <div>
                  <dt className={`text-xs font-semibold uppercase tracking-wide ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>Room name</dt>
                  <dd className={`text-sm font-medium ${d ? 'text-white' : 'text-neutral-900'}`}>{createdCamera.livekitRoomName}</dd>
                </div>
                <div>
                  <dt className={`text-xs font-semibold uppercase tracking-wide ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>Camera ID</dt>
                  <dd className="mt-1 flex flex-col gap-2 sm:flex-row sm:items-center">
                    <code className={`block min-w-0 flex-1 p-3 rounded-md text-sm font-mono break-all ${d ? 'bg-neutral-800 text-sky-300' : 'bg-neutral-100 text-sky-700'}`}>{createdCamera.cameraId}</code>
                    <button onClick={() => copyValue('Camera ID', createdCamera.cameraId)}
                      className="inline-flex items-center justify-center gap-2 px-3 py-2 bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 rounded-lg text-sky-300 text-sm font-medium">
                      <Copy className="w-3.5 h-3.5" /> Copy ID
                    </button>
                  </dd>
                </div>
              </dl>
              <button onClick={() => setCreatedCamera(null)} className="mt-3 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-neutral-300 text-sm">Dismiss</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Camera Form */}
      {showCreateForm && (
        <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
          className={`backdrop-blur-xl border rounded-lg p-6 ${
            d ? 'bg-gradient-to-br from-neutral-900/90 to-neutral-800/90 border-neutral-700/50' : 'bg-white border-neutral-200'
          }`}>
          <h3 className={`font-semibold mb-4 flex items-center gap-2 ${d ? 'text-white' : 'text-neutral-900'}`}>
            <Camera className="w-5 h-5 text-orange-500" /> Register New Camera
          </h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <label htmlFor="camera-display-name" className={`text-sm font-medium ${d ? 'text-neutral-300' : 'text-neutral-700'}`}>Display Name *</label>
                <input id="camera-display-name" type="text" required value={newName} onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Front Gate" className={`w-full rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${
                    d ? 'bg-neutral-800/50 border border-neutral-700/50 text-white placeholder-neutral-500' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'
                  }`} />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="camera-source-type" className={`text-sm font-medium ${d ? 'text-neutral-300' : 'text-neutral-700'}`}>Source Type *</label>
                <select id="camera-source-type" value={newSourceType} onChange={(e) => setNewSourceType(e.target.value as CameraSourceType)}
                  className={`w-full rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${
                    d ? 'bg-neutral-800/50 border border-neutral-700/50 text-white' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'
                  }`}>
                  {sourceTypes.map((t) => <option key={t} value={t}>{sourceTypeLabels[t]}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <label htmlFor="camera-room-name" className={`text-sm font-medium ${d ? 'text-neutral-300' : 'text-neutral-700'}`}>LiveKit Room Name *</label>
                <input id="camera-room-name" type="text" required value={newRoomName} onChange={(e) => setNewRoomName(e.target.value)}
                  placeholder="e.g. camera_front_gate" className={`w-full rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${
                    d ? 'bg-neutral-800/50 border border-neutral-700/50 text-white placeholder-neutral-500' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'
                  }`} />
              </div>
            </div>
            <p className="text-xs text-amber-400">Warning: this action is audited. Room name must be unique across all cameras.</p>
            <div className="flex gap-2">
              <button type="button" onClick={() => setShowCreateForm(false)}
                className={`px-4 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
              <button type="submit" disabled={creating}
                className="px-6 py-2 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-400 hover:to-amber-500 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                {creating ? 'Creating...' : 'Create Camera'}
              </button>
            </div>
          </form>
        </motion.div>
      )}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-center">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
          <input
            type="text"
            aria-label="Search cameras by name, room, or ID"
            placeholder="Search cameras by name, room, or ID..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className={`w-full rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${d ? 'bg-neutral-800/50 border border-neutral-700/50 text-white placeholder-neutral-400' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'}`}
          />
        </div>
        <select
          aria-label="Camera status filter"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as 'all' | 'active' | 'retired')}
          className={`rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${d ? 'bg-neutral-800/50 border border-neutral-700/50 text-white' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
        >
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="retired">Retired only</option>
        </select>
        <select
          aria-label="Camera source type filter"
          value={sourceFilter}
          onChange={(event) => setSourceFilter(event.target.value as 'all' | CameraSourceType)}
          className={`rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${d ? 'bg-neutral-800/50 border border-neutral-700/50 text-white' : 'bg-neutral-50 border border-neutral-200 text-neutral-900'}`}
        >
          <option value="all">All source types</option>
          {sourceTypes.map((t) => <option key={t} value={t}>{sourceTypeLabels[t]}</option>)}
        </select>
      </div>

      {/* Camera List */}
      {loading && cameras.length === 0 ? (
        <div className="text-center py-12 text-neutral-400">Loading cameras...</div>
      ) : error && cameras.length === 0 ? (
        <LoadErrorPanel title="Unable to load cameras" message={error} onRetry={refetch} />
      ) : cameras.length === 0 ? (
        <div className={`text-center py-16 border rounded-lg ${d ? 'bg-neutral-900/50 border-neutral-700/50' : 'bg-neutral-50 border-neutral-200'}`}>
          <Camera className={`w-16 h-16 mx-auto mb-4 ${d ? 'text-neutral-600' : 'text-neutral-300'}`} />
          <h3 className={`text-lg font-semibold mb-2 ${d ? 'text-white' : 'text-neutral-900'}`}>No Cameras Registered</h3>
          <p className={d ? 'text-neutral-400' : 'text-neutral-500'}>Use the "Register Camera" button above to add your first camera.</p>
        </div>
      ) : filteredCameras.length === 0 ? (
        <div className={`text-center py-12 border rounded-lg ${d ? 'bg-neutral-900/50 border-neutral-700/50' : 'bg-neutral-50 border-neutral-200'}`}>
          <Filter className={`w-12 h-12 mx-auto mb-3 ${d ? 'text-neutral-600' : 'text-neutral-300'}`} />
          <h3 className={`text-lg font-semibold mb-1 ${d ? 'text-white' : 'text-neutral-900'}`}>No cameras match the filters</h3>
          <p className={d ? 'text-neutral-400' : 'text-neutral-500'}>Clear search, status, or source filters to see loaded cameras.</p>
        </div>
      ) : (
        <>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredCameras.map((cam, i) => {
            const isRetired = !!cam.retired_at;
            return (
              <motion.div key={cam.camera_id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                className={`backdrop-blur-xl border rounded-lg p-5 transition-all hover:shadow-lg ${
                  d ? 'bg-gradient-to-br from-neutral-900/90 to-neutral-800/90 border-neutral-700/50 hover:shadow-orange-500/10' : 'bg-white border-neutral-200 hover:shadow-md'
                }`}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isRetired ? 'bg-red-500/20' : 'bg-orange-500/20'}`}>
                      <Camera className={`w-5 h-5 ${isRetired ? 'text-red-400' : 'text-orange-500'}`} />
                    </div>
                    <div>
                      <h3 className={`font-semibold ${d ? 'text-white' : 'text-neutral-900'}`}>{cam.display_name}</h3>
                      <p className={`text-xs ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>Room: {cam.livekit_room_name}</p>
                    </div>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    isRetired
                      ? 'bg-red-500/20 text-red-400'
                      : d ? 'bg-orange-500/20 text-orange-400' : 'bg-orange-50 text-orange-700'
                  }`}>{isRetired ? 'retired' : cam.source_type || 'rtsp'}</span>
                </div>

                <div className={`mb-3 rounded-lg p-3 ${d ? 'bg-neutral-950/40' : 'bg-neutral-50'}`}>
                  <div className={`flex items-center justify-between gap-2 text-xs mb-1 ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>
                    <span>Camera ID</span>
                    <span className="font-mono">Short: {cam.camera_id.slice(0, 8)}</span>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <code className={`min-w-0 flex-1 rounded-md px-2 py-1.5 text-xs font-mono break-all ${d ? 'bg-neutral-900 text-sky-300' : 'bg-white text-sky-700'}`}>{cam.camera_id}</code>
                    <button
                      onClick={() => copyValue('Camera ID', cam.camera_id)}
                      className={`inline-flex items-center justify-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs ${d ? 'bg-sky-500/15 text-sky-300 hover:bg-sky-500/25' : 'bg-sky-50 text-sky-700 hover:bg-sky-100'}`}
                    >
                      <Copy className="w-3 h-3" /> Copy
                    </button>
                  </div>
                </div>

                <div className={`text-sm mb-4 ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>
                  {cam.created_at ? <>Created: {new Date(cam.created_at).toLocaleDateString()}</> : 'Created: -'}
                </div>

                <div className={`flex gap-2 pt-3 border-t ${d ? 'border-neutral-700/50' : 'border-neutral-100'}`}>
                  <button onClick={() => setAclModal({ cameraId: cam.camera_id, displayName: cam.display_name })}
                    className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                      d ? 'bg-neutral-800/50 hover:bg-neutral-700/50 text-white' : 'bg-neutral-100 hover:bg-neutral-200 text-neutral-700'
                    }`}>
                    <UserPlus className="w-3.5 h-3.5" /> ACL
                  </button>
                  {isRetired ? (
                    <button onClick={() => handleEnable(cam.camera_id, cam.display_name)}
                      className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg text-sm text-emerald-400 transition-colors">
                      <Power className="w-3.5 h-3.5" /> Enable
                    </button>
                  ) : (
                    <button onClick={() => setDisableModal({ cameraId: cam.camera_id, displayName: cam.display_name })}
                      className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg text-sm text-red-400 transition-colors">
                      <Trash2 className="w-3.5 h-3.5" /> Retire
                    </button>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
        {hasMore && (
          <div className="pt-2 text-center">
            <button
              onClick={loadMore}
              disabled={loading}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm disabled:opacity-50 ${d ? 'bg-neutral-800 text-neutral-300 hover:bg-neutral-700' : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'}`}
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Load more cameras
            </button>
          </div>
        )}
        </>
      )}

      {/* ACL Modal */}
      {aclModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setAclModal(null)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-neutral-200'}`} onClick={(e) => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-2 ${d ? 'text-white' : 'text-neutral-900'}`}>
              <Shield className="w-5 h-5 text-orange-500 inline mr-2" />Camera ACL: {aclModal.displayName}
            </h3>
            <p className={`text-sm mb-4 ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>Grant or revoke a user's access to this camera.</p>
            <div className="space-y-4">
              <div className="flex gap-2">
                {(['grant', 'revoke'] as const).map((a) => (
                  <button key={a} onClick={() => setAclAction(a)}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                      aclAction === a ? 'bg-orange-500 text-white' : d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'
                    }`}>{a === 'grant' ? 'Grant Access' : 'Revoke Access'}</button>
                ))}
              </div>
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-neutral-300' : 'text-neutral-700'}`}>User Email</label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                  <input type="email" required value={aclEmail} onChange={(e) => setAclEmail(e.target.value)}
                    placeholder="user@school.edu" className={`w-full rounded-lg pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/50 ${
                      d ? 'bg-neutral-800 border border-neutral-700 text-white placeholder-neutral-500' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'
                    }`} />
                </div>
              </div>
              <p className="text-xs text-amber-400">Warning: this action is audited. Enforces one active grant per user/camera.</p>
              <div className="flex gap-2">
                <button onClick={() => setAclModal(null)} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
                <button onClick={handleAcl} disabled={!aclEmail}
                  className="flex-1 py-2 bg-orange-500 hover:bg-orange-400 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                  {aclAction === 'grant' ? 'Grant' : 'Revoke'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Disable Modal */}
      {disableModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setDisableModal(null)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-neutral-200'}`} onClick={(e) => e.stopPropagation()}>
            <h3 className={`text-lg font-bold mb-2 text-red-400`}>Retire Camera: {disableModal.displayName}</h3>
            <p className={`text-sm mb-4 ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
              Warning: this will immediately terminate all active viewer sessions for this camera within 10 seconds. This action is audited and cannot be undone.
            </p>
            <div className="space-y-4">
              <textarea placeholder="Reason for retiring this camera..." required
                value={disableReason} onChange={(e) => setDisableReason(e.target.value)}
                className={`w-full rounded-lg px-4 py-2.5 text-sm min-h-20 focus:outline-none focus:ring-2 focus:ring-red-500/50 ${
                  d ? 'bg-neutral-800 border border-neutral-700 text-white placeholder-neutral-500' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'
                }`} />
              <div className="flex gap-2">
                <button onClick={() => { setDisableModal(null); setDisableReason(''); }} className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
                <button onClick={handleDisable} disabled={!disableReason}
                  className="flex-1 py-2 bg-red-500 hover:bg-red-400 text-white rounded-lg text-sm font-medium disabled:opacity-50">Retire Camera</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
