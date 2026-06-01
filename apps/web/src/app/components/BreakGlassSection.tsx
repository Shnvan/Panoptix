import { ShieldAlert, Clock, AlertTriangle, CheckCircle, XCircle, KeyRound, RefreshCw } from 'lucide-react';
import { motion } from 'motion/react';
import { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../../lib/theme';
import { api, ApiError } from '../../lib/api';
import { useBreakGlassStatus } from '../../lib/hooks';

/**
 * Break-Glass Emergency Admin — v4 §16.6 + core-features §4
 *
 * MVP Required:
 * - Open/close break-glass window
 * - 90-minute auto-disable countdown
 * - Hardware security key requirement warning
 * - Rotation checklist on close
 * - Every action during the window is logged and flagged
 * - Status fetched from GET /admin/internal/break-glass-status
 */
export function BreakGlassSection() {
  const { theme } = useTheme();
  const d = theme === 'dark';
  const { status: bgStatus, loading: statusLoading, refetch: refetchStatus } = useBreakGlassStatus();

  const [isOpen, setIsOpen] = useState(false);
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const [autoDisableAt, setAutoDisableAt] = useState<string | null>(null);
  const [timeRemaining, setTimeRemaining] = useState<string>('');

  const [reason, setReason] = useState('');
  const [closeReason, setCloseReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [showOpenConfirm, setShowOpenConfirm] = useState(false);
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Sync local state from break-glass status endpoint
  useEffect(() => {
    if (!bgStatus) return;
    setIsOpen(bgStatus.is_open);
    if (bgStatus.current_window) {
      setOpenedAt(bgStatus.current_window.opened_at);
      setAutoDisableAt(bgStatus.current_window.auto_disable_at);
    } else {
      setOpenedAt(null);
      setAutoDisableAt(null);
    }
  }, [bgStatus]);

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 6000);
  };

  // Countdown timer
  useEffect(() => {
    if (!autoDisableAt) return;
    const interval = setInterval(() => {
      const remaining = new Date(autoDisableAt).getTime() - Date.now();
      if (remaining <= 0) {
        setTimeRemaining('EXPIRED');
        setIsOpen(false);
        clearInterval(interval);
      } else {
        const mins = Math.floor(remaining / 60000);
        const secs = Math.floor((remaining % 60000) / 1000);
        setTimeRemaining(`${mins}m ${secs}s`);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [autoDisableAt]);

  const handleOpen = useCallback(async () => {
    if (!reason.trim()) return;
    setLoading(true);
    try {
      const res = await api.openBreakGlass(reason);
      setIsOpen(true);
      setOpenedAt(res.opened_at);
      setAutoDisableAt(res.auto_disable_at);
      setReason('');
      setShowOpenConfirm(false);
      showMsg('Break-glass window opened. 90-minute countdown started.', 'success');
      refetchStatus();
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'Failed to open break-glass window', 'error');
    }
    setLoading(false);
  }, [reason, refetchStatus]);

  const handleClose = useCallback(async () => {
    if (!closeReason.trim()) return;
    setLoading(true);
    try {
      await api.closeBreakGlass(closeReason);
      setIsOpen(false);
      setOpenedAt(null);
      setAutoDisableAt(null);
      setCloseReason('');
      setShowCloseModal(false);
      showMsg('Break-glass window closed. Complete the rotation checklist below.', 'success');
      refetchStatus();
    } catch (err) {
      showMsg(err instanceof ApiError ? err.detail : 'Failed to close break-glass window', 'error');
    }
    setLoading(false);
  }, [closeReason, refetchStatus]);

  const rotationChecklist = [
    'Rotate audit HMAC key',
    'Rotate LiveKit API keys',
    'Rotate Cloudflare Access service tokens',
    'Rotate all gateway credentials',
    'Review all actions taken during the break-glass window',
    'Document incident in incident report',
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className={`text-2xl font-bold mb-1 flex items-center gap-3 ${d ? 'text-white' : 'text-neutral-900'}`}>
            <ShieldAlert className="w-7 h-7 text-red-500" />
            Break-Glass Emergency Access
          </h2>
          <p className={d ? 'text-neutral-400' : 'text-neutral-500'}>
            Emergency admin access for when normal admin access fails. All actions are logged and flagged.
          </p>
        </div>
        <button onClick={() => refetchStatus()} disabled={statusLoading}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${d ? 'bg-neutral-800 hover:bg-neutral-700 text-neutral-300' : 'bg-neutral-100 hover:bg-neutral-200 text-neutral-700'}`}>
          <RefreshCw className={`w-4 h-4 ${statusLoading ? 'animate-spin' : ''}`} /> Refresh Status
        </button>
      </div>

      {/* Status messages */}
      {msg && (
        <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
          msg.type === 'error' ? 'bg-red-500/10 border border-red-500/20 text-red-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
        }`}>
          {msg.type === 'error' ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          {msg.text}
        </div>
      )}

      {/* Current Status */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className={`backdrop-blur-xl border rounded-lg p-6 ${
          isOpen
            ? 'bg-gradient-to-br from-red-900/30 to-orange-900/20 border-red-500/30'
            : d ? 'bg-gradient-to-br from-neutral-900/90 to-neutral-800/90 border-neutral-700/50' : 'bg-white border-neutral-200'
        }`}
      >
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className={`w-14 h-14 rounded-lg flex items-center justify-center ${
              isOpen ? 'bg-red-500/20' : d ? 'bg-neutral-800/50' : 'bg-neutral-100'
            }`}>
              <ShieldAlert className={`w-7 h-7 ${isOpen ? 'text-red-400 animate-pulse' : d ? 'text-neutral-500' : 'text-neutral-400'}`} />
            </div>
            <div>
              <h3 className={`text-lg font-bold ${isOpen ? 'text-red-400' : d ? 'text-white' : 'text-neutral-900'}`}>
                {isOpen ? '🔴 BREAK-GLASS ACTIVE' : 'Break-Glass Inactive'}
              </h3>
              {isOpen && openedAt && (
                <p className={`text-sm ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
                  Opened: {new Date(openedAt).toLocaleString()}
                </p>
              )}
              {!isOpen && (
                <p className={d ? 'text-neutral-400' : 'text-neutral-500'}>No active emergency window</p>
              )}
            </div>
          </div>

          {isOpen && (
            <div className="flex items-center gap-4">
              <div className={`text-center px-4 py-2 rounded-lg ${
                timeRemaining === 'EXPIRED' ? 'bg-red-500/20' : 'bg-amber-500/20'
              }`}>
                <div className="flex items-center gap-2">
                  <Clock className={`w-5 h-5 ${timeRemaining === 'EXPIRED' ? 'text-red-400' : 'text-amber-400'}`} />
                  <span className={`text-xl font-mono font-bold ${timeRemaining === 'EXPIRED' ? 'text-red-400' : 'text-amber-400'}`}>
                    {timeRemaining}
                  </span>
                </div>
                <p className="text-xs text-neutral-400 mt-0.5">Auto-disable countdown</p>
              </div>
              <button onClick={() => setShowCloseModal(true)}
                className="px-4 py-2.5 bg-red-500 hover:bg-red-400 text-white rounded-lg text-sm font-medium transition-colors">
                Close Window
              </button>
            </div>
          )}
        </div>
      </motion.div>

      {/* Security requirements */}
      <div className={`backdrop-blur-xl border rounded-lg p-6 ${
        d ? 'bg-gradient-to-br from-neutral-900/90 to-neutral-800/90 border-neutral-700/50' : 'bg-white border-neutral-200'
      }`}>
        <h3 className={`font-semibold mb-4 flex items-center gap-2 ${d ? 'text-white' : 'text-neutral-900'}`}>
          <KeyRound className="w-5 h-5 text-amber-500" /> Security Requirements
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className={`p-4 rounded-lg ${d ? 'bg-neutral-800/50' : 'bg-neutral-50'}`}>
            <h4 className={`text-sm font-medium mb-2 ${d ? 'text-white' : 'text-neutral-900'}`}>To Open</h4>
            <ul className={`text-sm space-y-1.5 ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
              <li>• Sealed account (break-glass-prime@domain)</li>
              <li>• Hardware security key required</li>
              <li>• Cloudflare Access App C verification</li>
              <li>• Reason must be documented</li>
            </ul>
          </div>
          <div className={`p-4 rounded-lg ${d ? 'bg-neutral-800/50' : 'bg-neutral-50'}`}>
            <h4 className={`text-sm font-medium mb-2 ${d ? 'text-white' : 'text-neutral-900'}`}>Automatic Safeguards</h4>
            <ul className={`text-sm space-y-1.5 ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
              <li>• 90-minute auto-disable (enforced at request time)</li>
              <li>• All actions logged with break_glass actor type</li>
              <li>• External monitor checks every 5 minutes</li>
              <li>• Mandatory credential rotation on close</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Open button (only when not active) */}
      {!isOpen && (
        <div className="flex justify-center">
          <button onClick={() => setShowOpenConfirm(true)}
            className="px-6 py-3 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500 text-white rounded-lg shadow-lg shadow-red-500/25 transition-all text-sm font-medium flex items-center gap-2">
            <ShieldAlert className="w-5 h-5" /> Open Emergency Window
          </button>
        </div>
      )}

      {/* Rotation Checklist (shown always as reference) */}
      <div className={`backdrop-blur-xl border rounded-lg p-6 ${
        d ? 'bg-gradient-to-br from-neutral-900/90 to-neutral-800/90 border-neutral-700/50' : 'bg-white border-neutral-200'
      }`}>
        <h3 className={`font-semibold mb-4 flex items-center gap-2 ${d ? 'text-white' : 'text-neutral-900'}`}>
          <AlertTriangle className="w-5 h-5 text-amber-500" /> Rotation Checklist (Required on Close)
        </h3>
        <p className={`text-sm mb-4 ${d ? 'text-neutral-400' : 'text-neutral-500'}`}>
          When closing a break-glass window, the following credential rotations are mandatory:
        </p>
        <div className="space-y-2">
          {rotationChecklist.map((item, i) => (
            <div key={i} className={`flex items-center gap-3 p-3 rounded-lg ${d ? 'bg-neutral-800/50' : 'bg-neutral-50'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${d ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-700'}`}>
                {i + 1}
              </div>
              <span className={`text-sm ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>{item}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Open Confirm Modal */}
      {showOpenConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setShowOpenConfirm(false)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-neutral-900 border-red-500/30' : 'bg-white border-neutral-200'}`} onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-2 text-red-400 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5" /> Confirm Break-Glass Open
            </h3>
            <p className={`text-sm mb-4 ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
              ⚠ This opens a 90-minute emergency admin window. All actions will be audited with elevated scrutiny.
              A hardware security key is required. Credential rotation is mandatory on close.
            </p>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className={`text-sm font-medium ${d ? 'text-neutral-300' : 'text-neutral-700'}`}>Reason *</label>
                <textarea required value={reason} onChange={(e) => setReason(e.target.value)}
                  placeholder="Describe why emergency access is needed..."
                  className={`w-full rounded-lg px-4 py-2.5 text-sm min-h-20 focus:outline-none focus:ring-2 focus:ring-red-500/50 ${
                    d ? 'bg-neutral-800 border border-neutral-700 text-white placeholder-neutral-500' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'
                  }`} />
              </div>
              <div className="flex gap-2">
                <button onClick={() => setShowOpenConfirm(false)}
                  className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
                <button onClick={handleOpen} disabled={loading || !reason.trim()}
                  className="flex-1 py-2 bg-red-500 hover:bg-red-400 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                  {loading ? 'Opening...' : 'Open Emergency Window'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Close Modal */}
      {showCloseModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/50" onClick={() => setShowCloseModal(false)}>
          <div className={`border rounded-lg p-6 max-w-md w-full ${d ? 'bg-neutral-900 border-neutral-700' : 'bg-white border-neutral-200'}`} onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-2 text-amber-400">Close Break-Glass Window</h3>
            <p className={`text-sm mb-4 ${d ? 'text-neutral-300' : 'text-neutral-600'}`}>
              Closing requires completing the credential rotation checklist. Document the close reason below.
            </p>
            <div className="space-y-4">
              <textarea required value={closeReason} onChange={(e) => setCloseReason(e.target.value)}
                placeholder="Close reason and rotation status..."
                className={`w-full rounded-lg px-4 py-2.5 text-sm min-h-20 focus:outline-none focus:ring-2 focus:ring-amber-500/50 ${
                  d ? 'bg-neutral-800 border border-neutral-700 text-white placeholder-neutral-500' : 'bg-neutral-50 border border-neutral-200 text-neutral-900 placeholder-neutral-400'
                }`} />
              <div className="flex gap-2">
                <button onClick={() => setShowCloseModal(false)}
                  className={`flex-1 py-2 rounded-lg text-sm ${d ? 'bg-neutral-800 text-neutral-300' : 'bg-neutral-100 text-neutral-600'}`}>Cancel</button>
                <button onClick={handleClose} disabled={loading || !closeReason.trim()}
                  className="flex-1 py-2 bg-amber-500 hover:bg-amber-400 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                  {loading ? 'Closing...' : 'Close Window'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
