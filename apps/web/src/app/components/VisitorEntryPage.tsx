import { useEffect, useState } from 'react';
import { ArrowRight, Eye, ShieldCheck } from 'lucide-react';
import { api } from '../../lib/api';
import type { VisitorCollectRequest, VisitorNoticeResponse } from '../../lib/types';

interface VisitorEntryPageProps {
  protectedAppHref: string;
}

type NoticeState = 'loading' | 'ready' | 'unavailable';

function browserTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

function visitorCollectBody(noticeVersion: string): VisitorCollectRequest {
  return {
    notice_version: noticeVersion,
    notice_acknowledged: true,
    page_path: window.location.pathname || '/',
    screen_width: window.screen.width || null,
    screen_height: window.screen.height || null,
    timezone: browserTimezone(),
    language: navigator.language || null,
  };
}

export function VisitorEntryPage({ protectedAppHref }: VisitorEntryPageProps) {
  const [notice, setNotice] = useState<VisitorNoticeResponse | null>(null);
  const [noticeState, setNoticeState] = useState<NoticeState>('loading');
  const [continuing, setContinuing] = useState(false);
  const [statusText, setStatusText] = useState('Loading the visitor security notice.');

  useEffect(() => {
    let active = true;

    api.getVisitorNotice()
      .then((nextNotice) => {
        if (!active) return;
        setNotice(nextNotice);
        setNoticeState('ready');
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
        await api.collectVisitorVisit(visitorCollectBody(notice.notice_version));
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
