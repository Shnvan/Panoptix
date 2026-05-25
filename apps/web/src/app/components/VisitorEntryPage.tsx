import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Eye, ShieldCheck } from 'lucide-react';
import { api } from '../../lib/api';
import type { VisitorCollectRequest, VisitorNoticeResponse } from '../../lib/types';

interface VisitorEntryPageProps {
  protectedAppHref: string;
}

type NoticeState = 'loading' | 'ready' | 'unavailable';

interface NavigatorNetworkInformation {
  effectiveType?: string;
  downlink?: number;
  rtt?: number;
  saveData?: boolean;
}

interface NavigatorWithEntryHints extends Navigator {
  connection?: NavigatorNetworkInformation;
  mozConnection?: NavigatorNetworkInformation;
  webkitConnection?: NavigatorNetworkInformation;
  globalPrivacyControl?: boolean;
}

interface EntryTimingValues {
  noticeLoadedAtMs: number | null;
  continueClickedAtMs: number;
  collectStartedAtMs: number;
}

function browserTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

function elapsedSince(startedAt: number): number {
  return Math.max(0, Math.round(performance.now() - startedAt));
}

function browserColorScheme(): 'light' | 'dark' | 'no-preference' {
  if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark';
  if (window.matchMedia?.('(prefers-color-scheme: light)').matches) return 'light';
  return 'no-preference';
}

function browserLanguages(): string[] {
  return Array.from(new Set((navigator.languages || [navigator.language]).filter(Boolean))).slice(0, 10);
}

function browserNetworkContext(): VisitorCollectRequest['network_context'] {
  const nav = navigator as NavigatorWithEntryHints;
  const connection = nav.connection || nav.mozConnection || nav.webkitConnection;
  return {
    effective_type: connection?.effectiveType || null,
    downlink_mbps: typeof connection?.downlink === 'number' ? connection.downlink : null,
    rtt_ms: typeof connection?.rtt === 'number' ? connection.rtt : null,
    save_data: typeof connection?.saveData === 'boolean' ? connection.saveData : null,
  };
}

async function visitorCollectBody(
  noticeVersion: string,
  timing: EntryTimingValues,
): Promise<VisitorCollectRequest> {
  const webrtc = await collectWebRtcContext();
  return {
    notice_version: noticeVersion,
    notice_acknowledged: true,
    page_path: window.location.pathname || '/',
    screen_width: window.screen.width || null,
    screen_height: window.screen.height || null,
    timezone: browserTimezone(),
    language: navigator.language || null,
    referrer: document.referrer || null,
    viewport_width: window.innerWidth || null,
    viewport_height: window.innerHeight || null,
    device_pixel_ratio: window.devicePixelRatio || null,
    touch_supported: 'ontouchstart' in window || navigator.maxTouchPoints > 0,
    max_touch_points: navigator.maxTouchPoints || 0,
    color_scheme: browserColorScheme(),
    cookies_enabled: navigator.cookieEnabled,
    do_not_track: navigator.doNotTrack || null,
    global_privacy_control: (navigator as NavigatorWithEntryHints).globalPrivacyControl ?? null,
    languages: browserLanguages(),
    network_context: browserNetworkContext(),
    timing_context: {
      notice_loaded_at_ms: timing.noticeLoadedAtMs,
      continue_clicked_at_ms: timing.continueClickedAtMs,
      collect_started_at_ms: timing.collectStartedAtMs,
      webrtc_elapsed_ms: webrtc.elapsed_ms,
    },
    webrtc_context: webrtc.context,
  };
}

function isPrivateIp(ip: string): boolean {
  if (ip.includes(':')) {
    const lower = ip.toLowerCase();
    return lower === '::1' || lower.startsWith('fc') || lower.startsWith('fd') || lower.startsWith('fe80');
  }
  const parts = ip.split('.').map((part) => Number(part));
  if (parts.length !== 4 || parts.some((part) => Number.isNaN(part))) return false;
  return (
    parts[0] === 10 ||
    parts[0] === 127 ||
    (parts[0] === 169 && parts[1] === 254) ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
    (parts[0] === 192 && parts[1] === 168)
  );
}

function looksLikeIp(value: string): boolean {
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(value)) {
    return value.split('.').every((part) => Number(part) >= 0 && Number(part) <= 255);
  }
  return /^[0-9a-f:]+$/i.test(value) && value.includes(':');
}

function addUnique(values: string[], value: string) {
  if (!values.includes(value) && values.length < 10) {
    values.push(value);
  }
}

function parseWebRtcCandidate(
  candidateLine: string,
  state: NonNullable<VisitorCollectRequest['webrtc_context']>,
) {
  state.candidate_count = Math.min(100, (state.candidate_count || 0) + 1);
  if (candidateLine.includes('.local')) {
    state.mdns_hostname_seen = true;
  }

  const parts = candidateLine.trim().split(/\s+/);
  const typIndex = parts.findIndex((part) => part === 'typ');
  const candidateType = typIndex >= 0 ? parts[typIndex + 1] || 'unknown' : 'unknown';
  addUnique(state.candidate_types || [], candidateType);

  const candidateIp = parts[4];
  if (!candidateIp || !looksLikeIp(candidateIp)) return;
  if (candidateType === 'relay') {
    addUnique(state.relay_ip_candidates || [], candidateIp);
  } else if (isPrivateIp(candidateIp)) {
    addUnique(state.local_ip_candidates || [], candidateIp);
  } else {
    addUnique(state.public_ip_candidates || [], candidateIp);
  }
}

async function collectWebRtcContext(): Promise<{
  elapsed_ms: number;
  context: NonNullable<VisitorCollectRequest['webrtc_context']>;
}> {
  const startedAt = performance.now();
  const context: NonNullable<VisitorCollectRequest['webrtc_context']> = {
    available: typeof RTCPeerConnection !== 'undefined',
    tested: false,
    candidate_count: 0,
    candidate_types: [],
    local_ip_candidates: [],
    public_ip_candidates: [],
    relay_ip_candidates: [],
    mdns_hostname_seen: false,
    error: null,
  };

  if (typeof RTCPeerConnection === 'undefined') {
    context.error = 'not_supported';
    return { elapsed_ms: elapsedSince(startedAt), context };
  }

  let pc: RTCPeerConnection | null = null;
  try {
    pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
    context.tested = true;
    pc.createDataChannel('panoptix-entry');

    await new Promise<void>((resolve) => {
      const timeout = window.setTimeout(resolve, 1400);
      pc!.onicecandidate = (event) => {
        if (event.candidate?.candidate) {
          parseWebRtcCandidate(event.candidate.candidate, context);
        }
        if (!event.candidate) {
          window.clearTimeout(timeout);
          resolve();
        }
      };
      pc!.createOffer()
        .then((offer) => pc!.setLocalDescription(offer))
        .catch(() => {
          context.error = 'failed';
          window.clearTimeout(timeout);
          resolve();
        });
    });
  } catch {
    context.error = context.tested ? 'failed' : 'blocked';
  } finally {
    pc?.close();
  }

  return { elapsed_ms: elapsedSince(startedAt), context };
}

export function VisitorEntryPage({ protectedAppHref }: VisitorEntryPageProps) {
  const [notice, setNotice] = useState<VisitorNoticeResponse | null>(null);
  const [noticeState, setNoticeState] = useState<NoticeState>('loading');
  const [continuing, setContinuing] = useState(false);
  const [statusText, setStatusText] = useState('Loading the visitor security notice.');
  const pageStartedAt = useRef(performance.now());
  const noticeLoadedAtMs = useRef<number | null>(null);

  useEffect(() => {
    let active = true;

    api.getVisitorNotice()
      .then((nextNotice) => {
        if (!active) return;
        setNotice(nextNotice);
        setNoticeState('ready');
        noticeLoadedAtMs.current = elapsedSince(pageStartedAt.current);
        setStatusText('Continue to the protected sign-in flow when ready.');
      })
      .catch(() => {
        if (!active) return;
        setNoticeState('unavailable');
        setStatusText('The visitor notice is temporarily unavailable. You can still continue to secure sign-in.');
      });

    return () => {
      active = false;
    };
  }, []);

  const continueToProtectedApp = async () => {
    if (continuing || noticeState === 'loading') return;
    setContinuing(true);

    if (notice) {
      setStatusText('Recording this entry visit before secure sign-in.');
      try {
        const continueClickedAtMs = elapsedSince(pageStartedAt.current);
        const collectStartedAtMs = elapsedSince(pageStartedAt.current);
        await api.collectVisitorVisit(
          await visitorCollectBody(notice.notice_version, {
            noticeLoadedAtMs: noticeLoadedAtMs.current,
            continueClickedAtMs,
            collectStartedAtMs,
          }),
        );
      } catch {
        setStatusText('Entry recording is temporarily unavailable. Continuing to secure sign-in.');
      }
    }

    window.location.assign(protectedAppHref);
  };

  return (
    <main className="min-h-full bg-slate-950 text-slate-100">
      <section className="mx-auto flex min-h-full w-full max-w-6xl flex-col justify-center px-6 py-12 lg:px-10">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)] lg:items-center">
          <div className="max-w-2xl">
            <div className="mb-8 flex items-center gap-4">
              <img src="/logo.png" alt="" className="h-14 w-14 rounded-lg shadow-lg shadow-orange-500/20" />
              <div>
                <p className="text-sm font-medium text-orange-300">Panoptix</p>
                <p className="text-sm text-slate-400">Secure CCTV monitoring entry</p>
              </div>
            </div>

            <h1 className="max-w-xl text-4xl font-semibold text-white sm:text-5xl">
              Security notice before sign-in
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-300">
              This public entry step records limited browser and network context for access security before
              Cloudflare Access opens the protected Panoptix sign-in flow.
            </p>

            <div className="mt-8 flex flex-wrap gap-4 text-sm text-slate-300">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-300" />
                Protected system remains behind Cloudflare Access
              </div>
              <div className="flex items-center gap-2">
                <Eye className="h-4 w-4 text-cyan-300" />
                Visitor notice is shown before collection
              </div>
            </div>
          </div>

          <div className="border border-slate-700 bg-slate-900/80 p-6 shadow-2xl shadow-black/20 sm:p-8">
            <div className="border-b border-slate-800 pb-5">
              <p className="text-sm font-medium text-slate-400">Visitor notice</p>
              <h2 className="mt-2 text-2xl font-semibold text-white">
                {notice?.title || 'Panoptix Visitor Security Notice'}
              </h2>
            </div>

            <div className="min-h-40 py-6 text-sm leading-7 text-slate-300">
              {noticeState === 'loading' && <p>Fetching the current notice.</p>}
              {noticeState === 'ready' && <p>{notice?.body}</p>}
              {noticeState === 'unavailable' && (
                <p>
                  The current notice could not be loaded. Continuing will take you to the protected sign-in
                  flow without blocking access.
                </p>
              )}
            </div>

            <div className="border-t border-slate-800 pt-5">
              <p aria-live="polite" className="min-h-6 text-sm text-slate-400">
                {statusText}
              </p>
              <button
                type="button"
                onClick={continueToProtectedApp}
                disabled={noticeState === 'loading' || continuing}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 bg-orange-500 px-4 py-3 font-semibold text-slate-950 transition hover:bg-orange-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
              >
                {continuing ? 'Continuing' : 'Continue to secure sign-in'}
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
