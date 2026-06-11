import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Eye, Flag, MapPin, RefreshCw, Signal, X } from 'lucide-react';
import { LiveKitRoom, useTracks, VideoTrack } from '@livekit/components-react';
import { Track } from 'livekit-client';
import { motion } from 'motion/react';
import { useTheme } from '../../lib/theme';
import { api, ApiError } from '../../lib/api';
import type { ViewerTokenResponse } from '../../lib/types';
import {
  nextPlaybackAttempt,
  playbackStateForRoomEvent,
  playbackStateForTrack,
  type PlaybackState,
} from './cameraPlayback';

interface CameraDetailModalProps {
  camera: {
    camera_id: string;
    display_name: string;
    livekit_room_name: string;
    source_type?: string | null;
  };
  onClose: () => void;
}

const PUBLISHER_TRACK_TIMEOUT_MS = 12_000;

function VideoPlayer({
  onTrackState,
  onFrameRendered,
}: {
  onTrackState: (available: boolean) => void;
  onFrameRendered: () => void;
}) {
  const tracks = useTracks([Track.Source.Camera]);

  useEffect(() => {
    onTrackState(tracks.length > 0);
  }, [onTrackState, tracks.length]);

  const handleVideoFrameCheck = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = event.currentTarget;
    if (video.videoWidth > 0 && video.videoHeight > 0) {
      onFrameRendered();
    }
  };

  if (tracks.length === 0) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#0A0A0A]">
        <RefreshCw className="h-8 w-8 animate-spin text-[#F07C1E]" />
        <span className="text-xs font-mono uppercase text-[#666666]">
          Waiting for camera publisher...
        </span>
      </div>
    );
  }

  return (
    <VideoTrack
      trackRef={tracks[0]}
      className="h-full w-full object-contain"
      onPlay={handleVideoFrameCheck}
      onTimeUpdate={handleVideoFrameCheck}
      onResize={handleVideoFrameCheck}
    />
  );
}

export function CameraDetailModal({ camera, onClose }: CameraDetailModalProps) {
  const { theme } = useTheme();
  const d = theme === 'dark';
  const [playbackState, setPlaybackState] = useState<PlaybackState>('idle');
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const [tokenData, setTokenData] = useState<ViewerTokenResponse | null>(null);
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const activeAttemptRef = useRef(0);
  const lastFrameTimeRef = useRef(0);

  const requestViewToken = async () => {
    const attempt = nextPlaybackAttempt(activeAttemptRef.current);
    activeAttemptRef.current = attempt;
    lastFrameTimeRef.current = 0;
    setTokenData(null);
    setPlaybackState('requesting_token');
    setPlaybackError(null);
    try {
      const data = await api.getCameraViewToken(camera.camera_id);
      if (activeAttemptRef.current !== attempt) return;
      setTokenData(data);
      setConnectionAttempt(attempt);
      setPlaybackState('connecting');
    } catch (err) {
      if (activeAttemptRef.current !== attempt) return;
      setTokenData(null);
      setPlaybackState('error');
      setPlaybackError(err instanceof ApiError ? err.detail : 'Failed to get stream token');
    }
  };

  const handleTrackState = useCallback((available: boolean) => {
    if (available) {
      setPlaybackError(null);
      if (lastFrameTimeRef.current === 0) {
        lastFrameTimeRef.current = Date.now();
      }
    }
    setPlaybackState((current) => playbackStateForTrack(current, available));
  }, []);

  const handleFrameRendered = useCallback(() => {
    lastFrameTimeRef.current = Date.now();
    setPlaybackState((prev) => {
      if (prev === 'waiting_for_frames' || prev === 'stalled') {
        return 'playing';
      }
      return prev;
    });
  }, []);

  useEffect(() => {
    if (playbackState !== 'waiting_for_publisher') return;
    const timeout = window.setTimeout(() => {
      const nextState = playbackStateForRoomEvent(
        activeAttemptRef.current,
        connectionAttempt,
        'publisher_timeout',
      );
      if (!nextState) return;
      setPlaybackState(nextState);
      setPlaybackError(
        'No camera publisher joined the LiveKit room before the timeout. Check the gateway, camera assignment, and edge-agent publisher.',
      );
    }, PUBLISHER_TRACK_TIMEOUT_MS);
    return () => window.clearTimeout(timeout);
  }, [connectionAttempt, playbackState]);

  useEffect(() => {
    if (playbackState !== 'waiting_for_frames' && playbackState !== 'playing') {
      return;
    }
    const interval = window.setInterval(() => {
      if (lastFrameTimeRef.current > 0 && Date.now() - lastFrameTimeRef.current > 5000) {
        setPlaybackState('stalled');
        setPlaybackError('Video playback stalled. Check the gateway, camera assignment, and edge-agent publisher.');
      }
    }, 1000);
    return () => window.clearInterval(interval);
  }, [playbackState]);

  const stateLabel: Record<PlaybackState, string> = {
    idle: 'NOT CONNECTED',
    requesting_token: 'REQUESTING ACCESS',
    connecting: 'CONNECTING',
    waiting_for_publisher: 'WAITING FOR CAMERA',
    waiting_for_frames: 'WAITING FOR FRAMES',
    playing: 'LIVE',
    stalled: 'PLAYBACK STALLED',
    offline: 'CAMERA OFFLINE',
    error: 'CONNECTION ERROR',
  };
  const panelMessage: Record<PlaybackState, string> = {
    idle: 'Stream not started',
    requesting_token: 'Requesting short-lived viewer access...',
    connecting: 'Connecting to LiveKit...',
    waiting_for_publisher: 'Connected. Waiting for the gateway camera publisher...',
    waiting_for_frames: 'Camera track received. Waiting for video frames...',
    playing: 'Live camera track received',
    stalled: 'Video playback stalled. Gateway FFmpeg might be hung or stopped.',
    offline: 'Camera publisher unavailable',
    error: 'Unable to establish stream',
  };
  const isPending =
    playbackState === 'requesting_token'
    || playbackState === 'connecting'
    || playbackState === 'waiting_for_publisher'
    || playbackState === 'waiting_for_frames';
  const stateTone = playbackState === 'playing' ? 'success' : isPending ? 'pending' : 'error';

  const handleConnectionFailure = (attempt: number, message: string) => {
    const nextState = playbackStateForRoomEvent(
      activeAttemptRef.current,
      attempt,
      'connection_error',
    );
    if (!nextState) return;
    setPlaybackState(nextState);
    setPlaybackError(message);
    setTokenData(null);
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
        className={`w-full max-w-6xl overflow-hidden border shadow-xl ${
          d ? 'border-[#222222] bg-[#111111]' : 'border-neutral-200 bg-white'
        }`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className={`flex items-center justify-between border-b p-6 ${d ? 'border-[#222222]' : 'border-neutral-200'}`}>
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center bg-[rgba(240,124,30,0.08)]">
              <Camera className="h-6 w-6 text-[#F07C1E]" />
            </div>
            <div>
              <h2 className={`text-xl font-bold ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>
                {camera.display_name}
              </h2>
              <div className={`mt-1 flex items-center gap-2 text-sm ${d ? 'text-[#666666]' : 'text-neutral-500'}`}>
                <MapPin className="h-3 w-3 text-[#F07C1E]" />
                <span>Room: {camera.livekit_room_name}</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className={`flex h-10 w-10 items-center justify-center border transition-colors ${
              d
                ? 'border-[#222222] bg-[#1A1A1A] text-[#666666] hover:bg-[#222222] hover:text-[#F0EAD6]'
                : 'border-neutral-200 bg-neutral-50 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900'
            }`}
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-6 p-6 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <div className="relative aspect-video overflow-hidden border border-[#222222] bg-[#0A0A0A]">
              {!tokenData ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[#0A0A0A]">
                  <Camera className="h-16 w-16 text-[#1A1A1A]" />
                  <span className="text-xs font-mono uppercase text-[#666666]" aria-live="polite">
                    {panelMessage[playbackState]}
                  </span>
                </div>
              ) : (
                <LiveKitRoom
                  key={connectionAttempt}
                  serverUrl={tokenData.livekit_url}
                  token={tokenData.token}
                  connect={true}
                  connectOptions={{ websocketTimeout: 10_000 }}
                  audio={false}
                  video={false}
                  className="h-full w-full"
                  onConnected={() => {
                    const nextState = playbackStateForRoomEvent(
                      activeAttemptRef.current,
                      connectionAttempt,
                      'connected',
                    );
                    if (nextState) setPlaybackState(nextState);
                  }}
                  onDisconnected={() => handleConnectionFailure(
                    connectionAttempt,
                    'The LiveKit connection closed. Request a fresh viewer token and try again.',
                  )}
                  onError={(error) => handleConnectionFailure(
                    connectionAttempt,
                    error.message || 'LiveKit connection failed',
                  )}
                >
                  <VideoPlayer onTrackState={handleTrackState} onFrameRendered={handleFrameRendered} />
                </LiveKitRoom>
              )}

              <div
                className={`absolute left-4 top-4 flex items-center gap-2 border px-3 py-1.5 text-xs font-mono font-bold ${
                  stateTone === 'success'
                    ? 'border-[#7BC67B]/30 bg-[#7BC67B]/10 text-[#7BC67B]'
                    : stateTone === 'pending'
                      ? 'border-[#F07C1E]/30 bg-[#F07C1E]/10 text-[#F07C1E]'
                      : 'border-[#FF3333]/30 bg-[#FF3333]/10 text-[#FF3333]'
                }`}
                aria-live="polite"
              >
                <div className={`h-2 w-2 rounded-full ${
                  stateTone === 'success' ? 'bg-[#7BC67B]' : stateTone === 'pending' ? 'bg-[#F07C1E]' : 'bg-[#FF3333]'
                }`} />
                <span>{stateLabel[playbackState]}</span>
              </div>

              <div className="absolute bottom-4 left-4 bg-black/70 px-3 py-1.5 text-xs font-mono text-white">
                {new Date().toLocaleString('en-US', { hour12: false })}
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => { void requestViewToken(); }}
                disabled={playbackState === 'requesting_token'}
                className="flex flex-1 items-center justify-center gap-2 bg-[#F07C1E] px-4 py-3 text-sm font-medium text-[#0A0A0A] transition-colors hover:bg-[#C45E0A] disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${playbackState === 'requesting_token' ? 'animate-spin' : ''}`} />
                <span>
                  {playbackState === 'requesting_token' ? 'Requesting...' : tokenData ? 'Restart Stream' : 'Establish Stream'}
                </span>
              </button>
              <button
                type="button"
                className={`flex flex-1 items-center justify-center gap-2 border px-4 py-3 transition-colors ${
                  d
                    ? 'border-[#222222] bg-[#1A1A1A] text-[#F0EAD6] hover:bg-[#222222]'
                    : 'border-neutral-200 bg-neutral-50 text-neutral-700 hover:bg-neutral-100'
                }`}
              >
                <Flag className="h-4 w-4 text-[#FF3333]" />
                <span className="text-sm font-medium">Flag Security Incident</span>
              </button>
            </div>

            {playbackError && (
              <div role="alert" className="border border-[#FF3333]/30 bg-[#FF3333]/10 p-3 text-sm font-mono text-[#FF3333]">
                Error: {playbackError}
              </div>
            )}
          </div>

          <div className="space-y-4">
            <div className={`space-y-3 border p-4 ${d ? 'border-[#222222] bg-[#1A1A1A]' : 'border-neutral-200 bg-neutral-50'}`}>
              <h3 className={`flex items-center gap-2 font-semibold ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>
                <Signal className="h-4 w-4 text-[#7BC67B]" /> Stream Context
              </h3>
              <div className="space-y-2">
                {[
                  ['Playback State', stateLabel[playbackState]],
                  ['Ingest Type', camera.source_type || 'RTSP Source'],
                  ['LiveKit Room', camera.livekit_room_name],
                  ['Viewer Token', tokenData ? 'Issued (short-lived)' : 'Not active'],
                ].map(([label, value]) => (
                  <div key={label} className="flex justify-between gap-4 text-sm">
                    <span className={d ? 'text-[#666666]' : 'text-neutral-500'}>{label}</span>
                    <span className={`break-all text-right font-mono ${d ? 'text-[#F0EAD6]' : 'text-neutral-700'}`}>{value}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className={`border p-4 text-xs font-mono ${
              d ? 'border-[#222222] bg-[rgba(240,124,30,0.08)] text-[#F07C1E]' : 'border-amber-200 bg-amber-50 text-amber-800'
            }`}>
              Browser playback is subscriber-only. LiveKit/WebRTC protects media in transit; RTSP credentials and publisher access remain on the gateway.
            </div>

            <div className={`space-y-3 border p-4 ${d ? 'border-[#222222] bg-[#1A1A1A]' : 'border-neutral-200 bg-neutral-50'}`}>
              <h3 className={`flex items-center gap-2 font-semibold ${d ? 'text-[#F0EAD6]' : 'text-neutral-900'}`}>
                <Eye className="h-4 w-4 text-[#F07C1E]" /> Access Control
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-start gap-2">
                  <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#7BC67B]" />
                  <span className={d ? 'text-[#F0EAD6]' : 'text-neutral-600'}>Backend camera ACL checked before token issuance</span>
                </div>
                <div className="flex items-start gap-2">
                  <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#7BC67B]" />
                  <span className={d ? 'text-[#F0EAD6]' : 'text-neutral-600'}>Viewer token grants subscribe-only room access</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
