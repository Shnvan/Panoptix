import { X, Camera, MapPin, Eye, Signal, RefreshCw, Flag } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { api, ApiError } from '../../lib/api';
import { useState } from 'react';

interface CameraDetailModalProps {
  camera: { camera_id: string; display_name: string; livekit_room_name: string; source_type?: string | null };
  onClose: () => void;
}

export function CameraDetailModal({ camera, onClose }: CameraDetailModalProps) {
  const { theme } = useTheme();
  const [tokenStatus, setTokenStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [tokenError, setTokenError] = useState<string | null>(null);

  const requestViewToken = async () => {
    setTokenStatus('loading');
    setTokenError(null);
    try {
      await api.getCameraViewToken(camera.camera_id);
      setTokenStatus('ready');
    } catch (err) {
      setTokenStatus('error');
      setTokenError(err instanceof ApiError ? err.detail : 'Failed to get stream token');
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ backgroundColor: theme === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className={`border rounded-2xl max-w-6xl w-full overflow-hidden shadow-2xl ${
          theme === 'dark'
            ? 'bg-gradient-to-br from-slate-900 to-slate-800 border-slate-700/50'
            : 'bg-white border-slate-200'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`flex items-center justify-between p-6 border-b ${
          theme === 'dark' ? 'border-slate-700/50' : 'border-slate-200'
        }`}>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-cyan-500/20 rounded-xl flex items-center justify-center">
              <Camera className="w-6 h-6 text-cyan-500" />
            </div>
            <div>
              <h2 className={`text-xl font-bold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
                {camera.display_name}
              </h2>
              <div className={`flex items-center gap-2 text-sm mt-1 ${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
              }`}>
                <MapPin className="w-3 h-3" />
                <span>Room: {camera.livekit_room_name}</span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${
              theme === 'dark' ? 'bg-slate-800/50 hover:bg-slate-700/50' : 'bg-slate-100 hover:bg-slate-200'
            }`}
            aria-label="Close modal"
          >
            <X className={`w-5 h-5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`} />
          </button>
        </div>

        {/* Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-6">
          {/* Video Panel */}
          <div className="lg:col-span-2 space-y-4">
            <div className="aspect-video bg-slate-950 rounded-xl overflow-hidden relative">
              <div className="absolute inset-0 bg-gradient-to-br from-slate-900 to-slate-950">
                <div className="absolute inset-0 flex items-center justify-center">
                  <Camera className="w-24 h-24 text-slate-700" />
                </div>
                <motion.div
                  className="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-50"
                  animate={{ y: [0, 400, 0] }}
                  transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
                />
              </div>
              <div className="absolute top-4 left-4 flex items-center gap-2 bg-red-500/90 backdrop-blur-sm px-3 py-1.5 rounded-lg">
                <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
                <span className="text-xs font-bold text-white">LIVE</span>
              </div>
              <div className="absolute bottom-4 left-4 bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded-lg font-mono text-xs text-white">
                {new Date().toLocaleString('en-US', { hour12: false })}
              </div>
            </div>

            {/* Controls */}
            <div className="flex gap-3">
              <button
                onClick={requestViewToken}
                disabled={tokenStatus === 'loading'}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/30 rounded-xl text-cyan-500 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${tokenStatus === 'loading' ? 'animate-spin' : ''}`} />
                <span className="text-sm font-medium">
                  {tokenStatus === 'loading' ? 'Requesting...' : tokenStatus === 'ready' ? 'Token Ready' : 'Request Stream'}
                </span>
              </button>
              <button className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 border rounded-xl transition-colors ${
                theme === 'dark'
                  ? 'bg-slate-800/50 hover:bg-slate-700/50 border-slate-700/50 text-white'
                  : 'bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-700'
              }`}>
                <Flag className="w-4 h-4" />
                <span className="text-sm font-medium">Flag Event</span>
              </button>
            </div>

            {tokenError && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {tokenError}
              </div>
            )}
          </div>

          {/* Metadata Panel */}
          <div className="space-y-4">
            <div className={`border rounded-xl p-4 space-y-3 ${
              theme === 'dark' ? 'bg-slate-800/50 border-slate-700/50' : 'bg-slate-50 border-slate-200'
            }`}>
              <h3 className={`font-semibold flex items-center gap-2 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
                <Signal className="w-4 h-4 text-emerald-400" /> Stream Info
              </h3>
              <div className="space-y-2">
                {[
                  ['Status', tokenStatus === 'ready' ? 'Connected' : 'Awaiting'],
                  ['Source', camera.source_type || 'RTSP'],
                  ['Room', camera.livekit_room_name],
                  ['Resolution', '1920×1080'],
                  ['FPS', '30'],
                ].map(([label, val]) => (
                  <div key={label} className="flex justify-between text-sm">
                    <span className={theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}>{label}</span>
                    <span className={`font-medium ${theme === 'dark' ? 'text-white' : 'text-slate-700'}`}>{val}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className={`border rounded-xl p-4 space-y-3 ${
              theme === 'dark' ? 'bg-slate-800/50 border-slate-700/50' : 'bg-slate-50 border-slate-200'
            }`}>
              <h3 className={`font-semibold flex items-center gap-2 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
                <Eye className="w-4 h-4 text-cyan-500" /> Access
              </h3>
              <div className="space-y-2 text-sm">
                {['Security Team', 'Admin Staff'].map((team) => (
                  <div key={team} className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span className={theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}>{team}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
