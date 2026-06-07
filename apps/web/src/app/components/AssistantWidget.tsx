import {
  Bot,
  LoaderCircle,
  MessageCircle,
  Minus,
  RotateCcw,
  Send,
  ShieldAlert,
  Trash2,
  X,
} from 'lucide-react';
import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api, ApiError } from '../../lib/api';
import type { AssistantMessage, AssistantStatusResponse } from '../../lib/types';
import { useTheme } from '../../lib/theme';

const QUICK_REPLIES = [
  'Summarize current system health.',
  'Are any gateway heartbeats stale?',
  'What checks should I run after a deployment?',
];

const WELCOME =
  'I can explain Panoptix operations and summarize sanitized health, gateway, camera, alert, and backup state.';

interface DisplayMessage extends AssistantMessage {
  id: number;
  at: Date;
}

interface ViewportBounds {
  height: number;
  offsetLeft: number;
  offsetTop: number;
  width: number;
}

function readViewportBounds(): ViewportBounds {
  const viewport = window.visualViewport;
  return {
    height: viewport?.height ?? window.innerHeight,
    offsetLeft: viewport?.offsetLeft ?? 0,
    offsetTop: viewport?.offsetTop ?? 0,
    width: viewport?.width ?? window.innerWidth,
  };
}

export function AssistantWidget() {
  const { theme } = useTheme();
  const [status, setStatus] = useState<AssistantStatusResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [consented, setConsented] = useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestCount, setRequestCount] = useState(0);
  const [viewport, setViewport] = useState(readViewportBounds);
  const nextId = useRef(1);
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    api.getAssistantStatus()
      .then((next) => { if (active) setStatus(next); })
      .catch(() => { if (active) setStatus(null); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, pending, error, open]);

  useEffect(() => {
    const visualViewport = window.visualViewport;
    const updateViewport = () => setViewport(readViewportBounds());
    window.addEventListener('resize', updateViewport);
    visualViewport?.addEventListener('resize', updateViewport);
    return () => {
      window.removeEventListener('resize', updateViewport);
      visualViewport?.removeEventListener('resize', updateViewport);
    };
  }, []);

  const sessionLimit = status?.page_session_limit ?? 50;
  const remaining = Math.max(0, sessionLimit - requestCount);
  const warning = useMemo(() => {
    if (remaining === 0) return 'Page-session request limit reached. Reloading starts a new local UI session.';
    if (remaining === 1) return 'Final assistant request remaining in this page session.';
    if (remaining <= 5) return `${remaining} assistant requests remaining in this page session.`;
    if (remaining === 10) return '10 assistant requests remaining in this page session.';
    return null;
  }, [remaining]);

  if (!status?.enabled) return null;

  const addMessage = (role: AssistantMessage['role'], content: string) => {
    const message: DisplayMessage = {
      id: nextId.current++,
      role,
      content,
      at: new Date(),
    };
    setMessages((current) => [...current, message]);
    return message;
  };

  const requestAnswer = async (history: DisplayMessage[]) => {
    if (pending || remaining <= 0) return;
    setPending(true);
    setError(null);
    setRequestCount((count) => count + 1);
    try {
      const bounded = history.slice(-status.max_history_messages).map(({ role, content }) => ({
        role,
        content,
      }));
      const result = await api.sendAssistantChat(bounded);
      addMessage('assistant', result.message);
    } catch (err) {
      if (err instanceof ApiError) {
        const friendly: Record<string, string> = {
          'assistant-rate-limited': 'The assistant is temporarily rate limited. Wait before retrying.',
          'assistant-provider-rate-limited': 'The model provider is busy. Try again in about 30 seconds.',
          'assistant-provider-timeout': 'The assistant timed out before responding.',
          'assistant-provider-unavailable': 'The assistant provider is currently unavailable.',
          'audit-log-write-failed': 'The request was blocked because secure audit logging is unavailable.',
        };
        setError(friendly[err.detail] ?? 'The assistant could not generate a response.');
      } else {
        setError('The assistant could not be reached.');
      }
    } finally {
      setPending(false);
    }
  };

  const send = async (value: string) => {
    const content = value.trim();
    if (!content || pending || remaining <= 0 || content.length > 2000) return;
    const userMessage: DisplayMessage = {
      id: nextId.current++,
      role: 'user',
      content,
      at: new Date(),
    };
    const nextHistory = [...messages, userMessage];
    setMessages(nextHistory);
    setInput('');
    await requestAnswer(nextHistory);
  };

  const retry = () => {
    if (messages[messages.length - 1]?.role === 'user') requestAnswer(messages);
  };

  const clear = () => {
    setMessages([]);
    setInput('');
    setError(null);
  };

  const d = theme === 'dark';
  const compactViewport = viewport.width < 640;
  const launcherPosition = compactViewport ? {
    bottom: 'auto',
    left: viewport.width - 76,
    right: 'auto',
    top: viewport.height - 76,
  } : {};
  const panelPosition = compactViewport ? {
    bottom: 'auto',
    height: Math.max(300, viewport.height - 24),
    left: 12,
    right: 'auto',
    top: 12,
    width: Math.max(280, viewport.width - 24),
  } : {};

  return createPortal((
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open Panoptix operations assistant"
        style={{ zIndex: 9999, ...launcherPosition }}
        className={`fixed bottom-5 right-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-orange-500 text-white shadow-2xl shadow-orange-500/30 transition hover:bg-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 ${
          open ? 'pointer-events-none scale-90 opacity-0' : 'scale-100 opacity-100'
        }`}
      >
        <MessageCircle className="h-6 w-6" />
      </button>

      <section
        aria-label="Panoptix operations assistant"
        style={{ zIndex: 10000, ...panelPosition }}
        className={`fixed flex flex-col overflow-hidden border shadow-2xl transition-[opacity,transform] duration-200 ${
          open ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-4 opacity-0'
        } ${
          d
            ? 'border-neutral-700 bg-neutral-950 text-white'
            : 'border-neutral-200 bg-white text-neutral-900'
        } bottom-3 right-3 h-[min(700px,calc(100vh-1.5rem))] w-[min(430px,calc(100vw-1.5rem))] rounded-2xl`}
      >
        <header className="flex items-center justify-between border-b border-neutral-700/50 bg-gradient-to-r from-orange-500/20 to-transparent px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-500 text-white">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">Panoptix Operations Assistant</h2>
              <p className="text-xs text-neutral-400">Admin-only, read-only guidance</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button type="button" onClick={clear} aria-label="Clear assistant conversation"
              className="rounded-lg p-2 text-neutral-400 hover:bg-neutral-500/10 hover:text-orange-500">
              <Trash2 className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => setOpen(false)} aria-label="Minimize assistant"
              className="rounded-lg p-2 text-neutral-400 hover:bg-neutral-500/10 hover:text-orange-500">
              <Minus className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close assistant"
              className="rounded-lg p-2 text-neutral-400 hover:bg-neutral-500/10 hover:text-orange-500">
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        {!consented ? (
          <div className="flex flex-1 items-center justify-center p-5">
            <div className={`w-full rounded-2xl border p-5 ${d ? 'border-neutral-700 bg-neutral-900' : 'border-neutral-200 bg-neutral-50'}`}>
              <ShieldAlert className="mb-3 h-8 w-8 text-orange-500" />
              <h3 className="mb-2 font-semibold">Before you continue</h3>
              <p className="mb-3 text-sm text-neutral-400">
                Responses are AI-generated and may be inaccurate. Requests use sanitized operational
                summaries and are sent to the configured model provider.
              </p>
              <p className="mb-5 text-sm font-medium text-orange-500">
                Never paste credentials, tokens, RTSP URLs, personal information, or incident-sensitive evidence.
              </p>
              <div className="flex gap-2">
                <button type="button" onClick={() => setOpen(false)}
                  className="flex-1 rounded-xl border border-neutral-600 px-4 py-2 text-sm">
                  Cancel
                </button>
                <button type="button" onClick={() => setConsented(true)}
                  className="flex-1 rounded-xl bg-orange-500 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-400">
                  Continue
                </button>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="border-b border-neutral-700/40 px-4 py-2 text-xs text-neutral-400">
              Sanitized operational data only. The assistant cannot perform actions.
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
              <MessageBubble role="assistant" content={WELCOME} at={new Date()} />
              {messages.map((message) => (
                <MessageBubble key={message.id} {...message} />
              ))}
              {messages.length === 0 && (
                <div className="flex flex-wrap gap-2">
                  {QUICK_REPLIES.map((reply) => (
                    <button key={reply} type="button" onClick={() => send(reply)}
                      className="rounded-full border border-orange-500/30 bg-orange-500/10 px-3 py-2 text-left text-xs text-orange-500 hover:bg-orange-500/20">
                      {reply}
                    </button>
                  ))}
                </div>
              )}
              {pending && (
                <div className="flex items-center gap-2 text-sm text-neutral-400">
                  <LoaderCircle className="h-4 w-4 animate-spin text-orange-500" />
                  Reviewing sanitized Panoptix state...
                </div>
              )}
              {error && (
                <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
                  <p>{error}</p>
                  {messages[messages.length - 1]?.role === 'user' && remaining > 0 && (
                    <button type="button" onClick={retry}
                      className="mt-2 flex items-center gap-1 font-semibold text-orange-500">
                      <RotateCcw className="h-3.5 w-3.5" /> Retry
                    </button>
                  )}
                </div>
              )}
              {warning && (
                <p role="status" className="rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-500">
                  {warning}
                </p>
              )}
              <div ref={messageEndRef} />
            </div>

            <form
              className="border-t border-neutral-700/50 p-3"
              onSubmit={(event) => {
                event.preventDefault();
                send(input);
              }}
            >
              <div className={`flex items-end gap-2 rounded-xl border p-2 ${d ? 'border-neutral-700 bg-neutral-900' : 'border-neutral-200 bg-neutral-50'}`}>
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value.slice(0, 2000))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      send(input);
                    }
                  }}
                  rows={2}
                  maxLength={2000}
                  disabled={pending || remaining <= 0}
                  aria-label="Message Panoptix operations assistant"
                  placeholder="Ask about health, gateways, alerts, or backups..."
                  className="max-h-28 min-h-11 flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-neutral-500"
                />
                <button type="submit" disabled={!input.trim() || pending || remaining <= 0}
                  aria-label="Send assistant message"
                  className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-500 text-white disabled:cursor-not-allowed disabled:opacity-40">
                  <Send className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-2 flex justify-between text-[11px] text-neutral-500">
                <span>{remaining}/{sessionLimit} page-session requests</span>
                <span>{input.length}/2000</span>
              </div>
            </form>
          </>
        )}
      </section>
    </>
  ), document.body);
}

function MessageBubble({ role, content, at }: Pick<DisplayMessage, 'role' | 'content' | 'at'>) {
  const assistant = role === 'assistant';
  return (
    <div className={`flex ${assistant ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-[88%] rounded-2xl px-3.5 py-3 text-sm ${
        assistant
          ? 'rounded-bl-md border border-neutral-700/50 bg-neutral-800/60'
          : 'rounded-br-md bg-orange-500 text-white'
      }`}>
        {assistant ? <SafeMarkdown text={content} /> : <p className="whitespace-pre-wrap break-words">{content}</p>}
        <time className={`mt-1.5 block text-[10px] ${assistant ? 'text-neutral-500' : 'text-orange-100'}`}>
          {at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </time>
      </div>
    </div>
  );
}

function SafeMarkdown({ text }: { text: string }) {
  return (
    <div className="space-y-1.5 break-words">
      {text.split('\n').map((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={index} className="h-1" />;
        if (/^[-*]\s+/.test(trimmed)) {
          return <div key={index} className="flex gap-2"><span>-</span><span>{inlineMarkdown(trimmed.slice(2))}</span></div>;
        }
        if (/^#{1,3}\s+/.test(trimmed)) {
          return <p key={index} className="font-semibold text-orange-400">{inlineMarkdown(trimmed.replace(/^#{1,3}\s+/, ''))}</p>;
        }
        return <p key={index}>{inlineMarkdown(line)}</p>;
      })}
    </div>
  );
}

function inlineMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index} className="rounded bg-black/30 px-1 py-0.5 font-mono text-xs">{part.slice(1, -1)}</code>;
    }
    return <Fragment key={index}>{part}</Fragment>;
  });
}
