import { X, Camera, MapPin, Eye, Signal, RefreshCw, Flag } from 'lucide-react';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { api, ApiError } from '../../lib/api';
import { useState } from 'react';
import { LiveKitRoom, useTracks, VideoTrack } from '@livekit/components-react';
import { Track } from 'livekit-client';
import type { ViewerTokenResponse } from '../../lib/types';

interface CameraDetailModalProps {
  camera: { camera_id: string; display_name: string; livekit_room_name: string; source_type?: string | null };
  onClose: () => void;
}

function VideoPlayer() {
  const tracks = useTracks([Track.Source.Camera]);

  if (tracks.length === 0) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#0A0A0A]">
        <RefreshCw className="w-8 h-8 text-[#F07C1E] animate-spin" />
        <span className="text-xs font-mono uppercase tracking-wider text-[#666666]">
          Establishing secure stream tunnel...
        </span>
      </div>
    );
  }

  return (
    <VideoTrack
      trackRef={tracks[0]}
      className="w-full h-full object-contain"
    />
  );
}

export function CameraDetailModal({ camera, onClose }: CameraDetailModalProps) {
  const { theme } = useTheme();
  const d = theme === 'dark';
  const [tokenStatus, setTokenStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [tokenData, setTokenData] = useState<ViewerTokenResponse | null>(null);

  const requestViewToken = async () => {
    setTokenStatus('loading');
    setTokenError(null);
    setTokenData(null);
    try {
      const data = await api.getCameraViewToken(camera.camera_id);
      setTokenData(data);
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
      style={{ backgroundColor: d ? 'rgba(10,10,10,0.85)' : 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className={`border max-w-6xl w-full overflow-hidden shadow-xl rounded-none ${
          d ? 'bg-[#111111] border-[#222222]' : 'bg-[#FFFFFF] border-slate-200'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`flex items-center justify-between p-6 border-b ${
          d ? 'border-[#222222]' : 'border-slate-200'
        }`}>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-[rgba(240,124,30,0.08)] rounded-none flex items-center justify-center">
              <Camera className="w-6 h-6 text-[#F07C1E]" />
            </div>
            <div>
              <h2 className={`text-xl font-bold ${d ? 'text-[#F0EAD6]' : 'text-slate-900'}`}>
                {camera.display_name}
              </h2>
              <div className={`flex items-center gap-2 text-sm mt-1 ${
                d ? 'text-[#666666]' : 'text-slate-500'
              }`}>
                <MapPin className="w-3 h-3 text-[#F07C1E]" />
                <span>Room: {camera.livekit_room_name}</span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className={`w-10 h-10 rounded-none flex items-center justify-center transition-colors border ${
              d ? 'bg-[#1A1A1A] border-[#222222] hover:bg-[#222222] text-[#666666] hover:text-[#F0EAD6]' : 'bg-slate-50 border-slate-200 hover:bg-slate-100 text-slate-500 hover:text-slate-900'
            }`}
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-6">
          {/* Video Panel */}
          <div className="lg:col-span-2 space-y-4">
            <div className="aspect-video bg-[#0A0A0A] border border-[#222222] overflow-hidden relative rounded-none">
              {tokenStatus !== 'ready' ? (
                <div className="absolute inset-0 bg-[#0A0A0A]">
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                    <Camera className="w-16 h-16 text-[#1A1A1A]" />
                    <span className="text-xs font-mono uppercase tracking-wider text-[#666666]">
                      {tokenStatus === 'loading' ? 'Requesting secure tunnel...' : 'Feed offline · Tunnel closed'}
                    </span>
                  </div>
                </div>
              ) : (
                tokenData && (
                  <LiveKitRoom
                    serverUrl={tokenData.livekit_url}
                    token={tokenData.token}
                    connect={true}
                    audio={false}
                    video={false}
                    className="w-full h-full"
                  >
                    <VideoPlayer />
                  </LiveKitRoom>
                )
              )}

              {/* Status Badge */}
              <div className={`absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 border rounded-none text-xs font-mono font-bold ${
                tokenStatus === 'ready'
                  ? 'bg-[#7BC67B]/10 border-[#7BC67B]/30 text-[#7BC67B]'
                  : 'bg-[#FF3333]/10 border-[#FF3333]/30 text-[#FF3333]'
              }`}>
                <div className={`w-2 h-2 rounded-full ${tokenStatus === 'ready' ? 'bg-[#7BC67B]' : 'bg-[#FF3333]'}`} />
                <span>{tokenStatus === 'ready' ? 'LIVE TUNNEL ACTIVE' : 'TUNNEL CLOSED'}</span>
              </div>

              <div className="absolute bottom-4 left-4 bg-black/70 px-3 py-1.5 font-mono text-xs text-white">
                {new Date().toLocaleString('en-US', { hour12: false })}
              </div>
            </div>

            {/* Controls */}
            <div className="flex gap-3">
              <button
                onClick={requestViewToken}
                disabled={tokenStatus === 'loading'}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-[#F07C1E] hover:bg-[#C45E0A] text-[#0A0A0A] rounded-none text-sm font-medium transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${tokenStatus === 'loading' ? 'animate-spin' : ''}`} />
                <span>
                  {tokenStatus === 'loading' ? 'Requesting...' : tokenStatus === 'ready' ? 'Tunnel Reset' : 'Establish Stream Tunnel'}
                </span>
              </button>
              <button className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 border rounded-none transition-colors ${
                d
                  ? 'bg-[#1A1A1A] hover:bg-[#222222] border-[#222222] text-[#F0EAD6]'
                  : 'bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-700'
              }`}>
                <Flag className="w-4 h-4 text-[#FF3333]" />
                <span className="text-sm font-medium">Flag Security Incident</span>
              </button>
            </div>

            {tokenError && (
              <div className="p-3 rounded-none bg-[#FF3333]/10 border border-[#FF3333]/30 text-[#FF3333] text-sm font-mono">
                Error: {tokenError}
              </div>
            )}
          </div>

          {/* Metadata Panel */}
          <div className="space-y-4">
            <div className={`border rounded-none p-4 space-y-3 ${
              d ? 'bg-[#1A1A1A] border-[#222222]' : 'bg-slate-50 border-slate-200'
            }`}>
              <h3 className={`font-semibold flex items-center gap-2 ${d ? 'text-[#F0EAD6]' : 'text-slate-900'}`}>
                <Signal className="w-4 h-4 text-[#7BC67B]" /> Stream Context
              </h3>
              <div className="space-y-2">
                {[
                  ['Tunnel State', tokenStatus === 'ready' ? 'Connected' : 'Closed'],
                  ['Ingest Type', camera.source_type || 'RTSP Source'],
                  ['LiveKit Room', camera.livekit_room_name],
                  ['Watermark', 'Active (Analyst ID)'],
                ].map(([label, val]) => (
                  <div key={label} className="flex justify-between text-sm">
                    <span className={d ? 'text-[#666666]' : 'text-slate-500'}>{label}</span>
                    <span className={`font-mono ${d ? 'text-[#F0EAD6]' : 'text-slate-700'}`}>{val}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className={`border rounded-none p-4 text-xs font-mono ${
              d ? 'bg-[rgba(240,124,30,0.08)] border-[#222222] text-[#F07C1E]' : 'bg-amber-50 border-amber-200 text-amber-800'
            }`}>
              Tunnel encryption active (HMAC-SHA256). LiveKit subscriber tunnel prevents local client media publishing (PH DPA compliance mandate).
            </div>

            <div className={`border rounded-none p-4 space-y-3 ${
              d ? 'bg-[#1A1A1A] border-[#222222]' : 'bg-slate-50 border-slate-200'
            }`}>
              <h3 className={`font-semibold flex items-center gap-2 ${d ? 'text-[#F0EAD6]' : 'text-slate-900'}`}>
                <Eye className="w-4 h-4 text-[#F07C1E]" /> Authorized Roles
              </h3>
              <div className="space-y-2 text-sm">
                {['Security Operations Center (SOC)', 'Compliance Officer', 'System Administrator'].map((team) => (
                  <div key={team} className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-[#7BC67B]" />
                    <span className={d ? 'text-[#F0EAD6]' : 'text-slate-600'}>{team}</span>
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
