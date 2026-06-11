export type PlaybackState =
  | 'idle'
  | 'requesting_token'
  | 'connecting'
  | 'waiting_for_publisher'
  | 'waiting_for_frames'
  | 'playing'
  | 'stalled'
  | 'offline'
  | 'error';

export type RoomPlaybackEvent = 'connected' | 'connection_error' | 'publisher_timeout';

export function nextPlaybackAttempt(activeAttempt: number): number {
  return activeAttempt + 1;
}

export function playbackStateForRoomEvent(
  activeAttempt: number,
  eventAttempt: number,
  event: RoomPlaybackEvent,
): PlaybackState | null {
  if (activeAttempt !== eventAttempt) return null;
  if (event === 'connected') return 'waiting_for_publisher';
  if (event === 'publisher_timeout') return 'offline';
  return 'error';
}

export function playbackStateForTrack(
  current: PlaybackState,
  available: boolean,
): PlaybackState {
  if (available) {
    if (current === 'playing' || current === 'stalled' || current === 'waiting_for_frames') {
      return current;
    }
    return 'waiting_for_frames';
  }
  return current === 'playing' || current === 'waiting_for_frames' || current === 'stalled'
    ? 'waiting_for_publisher'
    : current;
}
