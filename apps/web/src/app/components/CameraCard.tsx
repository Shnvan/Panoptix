import { Camera, Maximize2, Signal, WifiOff, AlertTriangle, ShieldX, Loader2 } from 'lucide-react';
import { motion } from 'motion/react';
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

const statusConfig: Record<CameraTileStatus, {
  label: string;
  color: string;
  icon: typeof Signal;
  pulse: boolean;
}> = {
  online: { label: 'Live', color: 'bg-emerald-500', icon: Signal, pulse: true },
  offline: { label: 'Offline', color: 'bg-red-500', icon: WifiOff, pulse: false },
  reconnecting: { label: 'Reconnecting', color: 'bg-amber-500', icon: Loader2, pulse: true },
  unavailable: { label: 'Unavailable', color: 'bg-neutral-500', icon: AlertTriangle, pulse: false },
  gateway_unavailable: { label: 'Gateway Down', color: 'bg-red-500', icon: AlertTriangle, pulse: false },
  permission_denied: { label: 'No Access', color: 'bg-red-500', icon: ShieldX, pulse: false },
  loading: { label: 'Loading', color: 'bg-neutral-500', icon: Loader2, pulse: true },
};

/**
 * Camera tile component — per ux-product-spec.md and
 * cctv-core-functionality-features.md §3.
 *
 * All 7 tile states (loading, online, offline, reconnecting,
 * unavailable, gateway_unavailable, permission_denied) are visualized.
 *
 * No getUserMedia / MediaRecorder (Inv 1/5/6).
 * Viewer only — subscribes, does not publish.
 */
export function CameraCard({ id, name, location, status, onExpand }: CameraCardProps) {
  const { theme } = useTheme();
  const cfg = statusConfig[status];
  const StatusIcon = cfg.icon;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={{ y: -2 }}
      className={`relative rounded-lg overflow-hidden cursor-pointer group transition-all duration-300 hover:shadow-xl hover:shadow-orange-500/10 ${
        theme === 'dark'
          ? 'bg-gradient-to-br from-neutral-900 to-neutral-800 border border-neutral-700/50'
          : 'bg-white border border-neutral-200 shadow-sm'
      }`}
      onClick={onExpand}
    >
      {/* Video placeholder */}
      <div className="aspect-video bg-neutral-950 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-neutral-900 to-neutral-950">
          <div className="absolute inset-0 flex items-center justify-center">
            <Camera className="w-16 h-16 text-neutral-700" />
          </div>
          {/* Scan line animation */}
          <motion.div
            className="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-orange-400 to-transparent opacity-30"
            animate={{ y: [0, 300, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
          />
        </div>

        {/* Status Badge */}
        <div className="absolute top-3 left-3 flex items-center gap-2">
          <div className={`flex items-center gap-1.5 ${cfg.color} backdrop-blur-sm px-2.5 py-1 rounded-md`}>
            {cfg.pulse && <div className="w-2 h-2 rounded-full bg-white animate-pulse" />}
            <StatusIcon className="w-3 h-3 text-white" />
            <span className="text-xs font-bold text-white">{cfg.label}</span>
          </div>
        </div>

        {/* Camera ID overlay */}
        <div className="absolute bottom-3 left-3 bg-black/70 backdrop-blur-sm px-2.5 py-1 rounded-md font-mono text-xs text-white">
          {id.slice(0, 8)}
        </div>

        {/* Expand button */}
        <div className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="bg-orange-500/20 backdrop-blur-sm p-2 rounded-md border border-orange-500/30 text-orange-400 hover:bg-orange-500/30 transition-colors">
            <Maximize2 className="w-4 h-4" />
          </div>
        </div>
      </div>

      {/* Info bar */}
      <div className={`px-4 py-3 ${theme === 'dark' ? '' : ''}`}>
        <h4 className={`font-semibold text-sm truncate ${theme === 'dark' ? 'text-white' : 'text-neutral-900'}`}>{name}</h4>
        <p className={`text-xs truncate mt-0.5 ${theme === 'dark' ? 'text-neutral-400' : 'text-neutral-500'}`}>{location}</p>
      </div>
    </motion.div>
  );
}
