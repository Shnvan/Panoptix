import { Maximize2, Minimize2, Wifi, WifiOff, RefreshCw, AlertTriangle, ShieldOff, ServerOff } from 'lucide-react';
import { motion } from 'motion/react';
import { useState, useRef, useCallback } from 'react';
import { useTheme } from '../../lib/theme';
import type { CameraTileStatus } from '../../lib/types';

interface CameraCardProps {
  id: string;
  name: string;
  location: string;
  status: CameraTileStatus;
  onExpand: () => void;
  viewerEmail?: string | null;
}

/**
 * Camera tile — per ux-product-spec.md + cctv-core-functionality-features.md §3
 *
 * Required states: loading, online, offline, reconnecting, unavailable,
 *   gateway_unavailable, permission_denied
 * Required: fullscreen button per tile (core-features §3)
 * Required: viewer identity watermark area (ux-product-spec, v4 §16.19)
 */
const statusConfig: Record<CameraTileStatus, { label: string; color: string; bg: string; icon: typeof Wifi; message: string }> = {
  loading:              { label: 'Loading',              color: 'text-slate-400',  bg: 'bg-slate-500/20',   icon: RefreshCw,      message: 'Connecting to camera...' },
  online:               { label: 'Online',               color: 'text-emerald-400', bg: 'bg-emerald-500/20', icon: Wifi,           message: '' },
  offline:              { label: 'Offline',              color: 'text-red-400',    bg: 'bg-red-500/20',     icon: WifiOff,        message: 'Camera feed is not available.' },
  reconnecting:         { label: 'Reconnecting',         color: 'text-amber-400',  bg: 'bg-amber-500/20',   icon: RefreshCw,      message: 'Restoring connection...' },
  unavailable:          { label: 'Unavailable',          color: 'text-red-400',    bg: 'bg-red-500/20',     icon: AlertTriangle,  message: 'Camera cannot be reached right now.' },
  gateway_unavailable:  { label: 'Gateway Unavailable',  color: 'text-orange-400', bg: 'bg-orange-500/20',  icon: ServerOff,      message: 'The on-site gateway is not responding. No action required by viewer.' },
  permission_denied:    { label: 'Permission Denied',    color: 'text-red-400',    bg: 'bg-red-500/20',     icon: ShieldOff,      message: 'You do not have access to this camera. Contact your administrator.' },
};

export function CameraCard({ id, name, location, status, onExpand, viewerEmail }: CameraCardProps) {
  const { theme } = useTheme();
  const d = theme === 'dark';
  const cfg = statusConfig[status];
  const Icon = cfg.icon;
  const cardRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = useCallback(async () => {
    if (!cardRef.current) return;
    try {
      if (!document.fullscreenElement) {
        await cardRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch { /* fullscreen not supported */ }
  }, []);

  return (
    <motion.div
      ref={cardRef}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`group relative backdrop-blur-xl border rounded-xl overflow-hidden transition-all hover:shadow-lg ${
        isFullscreen ? 'fixed inset-0 z-50 rounded-none' : ''
      } ${
        d ? 'bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-slate-700/50 hover:shadow-cyan-500/10'
          : 'bg-white border-slate-200 hover:shadow-md'
      }`}
      role="region"
      aria-label={`Camera: ${name} — Status: ${cfg.label}`}
    >
      {/* Video Area */}
      <div className={`relative aspect-video ${d ? 'bg-slate-900' : 'bg-slate-100'}`}>
        {status === 'online' ? (
          <div className="w-full h-full bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-2 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <Wifi className="w-8 h-8 text-emerald-400 animate-pulse" />
              </div>
              <p className="text-emerald-400 text-sm font-medium">Live Feed Active</p>
              <p className="text-slate-500 text-xs mt-1">Camera ID: {id.slice(0, 8)}</p>
            </div>
          </div>
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center p-4">
            <div className={`w-14 h-14 rounded-full ${cfg.bg} flex items-center justify-center mb-3`}>
              <Icon className={`w-7 h-7 ${cfg.color} ${status === 'reconnecting' || status === 'loading' ? 'animate-spin' : ''}`} />
            </div>
            <p className={`text-sm font-semibold ${cfg.color}`}>{cfg.label}</p>
            {cfg.message && (
              <p className={`text-xs text-center mt-1 max-w-48 ${d ? 'text-slate-400' : 'text-slate-500'}`}>{cfg.message}</p>
            )}
          </div>
        )}

        {/* Viewer identity watermark overlay — v4 §16.19 CSS overlay */}
        {viewerEmail && status === 'online' && (
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center opacity-15 select-none"
               aria-hidden="true">
            <p className="text-white text-lg font-mono rotate-[-20deg] whitespace-nowrap">
              {viewerEmail}
            </p>
          </div>
        )}

        {/* Status badge */}
        <div className="absolute top-3 left-3 flex items-center gap-1.5">
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg backdrop-blur-md ${
            d ? 'bg-black/50' : 'bg-white/80'
          }`}>
            <div className={`w-2 h-2 rounded-full ${
              status === 'online' ? 'bg-emerald-400 animate-pulse'
              : status === 'reconnecting' || status === 'loading' ? 'bg-amber-400 animate-pulse'
              : 'bg-red-400'
            }`} />
            <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
          </div>
        </div>

        {/* Fullscreen button — core-features §3 */}
        <button onClick={toggleFullscreen} title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          className={`absolute top-3 right-3 w-8 h-8 rounded-lg backdrop-blur-md flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity ${
            d ? 'bg-black/50 text-white hover:bg-black/70' : 'bg-white/80 text-slate-700 hover:bg-white'
          }`}>
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      {/* Info bar */}
      <div className={`p-4 ${d ? 'border-t border-slate-700/50' : 'border-t border-slate-100'}`}>
        <div className="flex items-center justify-between">
          <div className="min-w-0 flex-1">
            <h3 className={`font-semibold truncate ${d ? 'text-white' : 'text-slate-900'}`}>{name}</h3>
            <p className={`text-xs truncate ${d ? 'text-slate-400' : 'text-slate-500'}`}>Room: {location}</p>
          </div>
          <button onClick={onExpand} title="Expand camera details"
            className={`ml-3 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              d ? 'bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30' : 'bg-cyan-50 text-cyan-700 hover:bg-cyan-100'
            }`}>
            Details
          </button>
        </div>
      </div>
    </motion.div>
  );
}
