import { useCallback, useEffect, useRef, useState } from 'react';

const TOKEN_KEY = 'kenya-tours-live-chat';
const POLL_OPEN_MS = 5000;
const POLL_IDLE_MS = 30000;
const QUICK_REPLIES = [
  'How do I book a safari?',
  'Payment and M-Pesa help',
  'I need to change my booking',
];

function readToken() {
  try {
    return window.localStorage.getItem(TOKEN_KEY) || '';
  } catch (error) {
    return '';
  }
}

function writeToken(token) {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_KEY);
    }
  } catch (error) {
    /* Storage can be blocked in private mode; the thread then lives for one visit. */
  }
}

function timeLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

async function chatRequest(path, { method = 'GET', token = '', data } = {}) {
  const headers = { Accept: 'application/json' };
  if (token) headers['X-Chat-Token'] = token;
  if (data) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {
    method,
    headers,
    ...(data ? { body: JSON.stringify(data) } : {}),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Chat is unavailable right now (HTTP ${response.status}).`);
  return result;
}

function ChatIcon({ className = '' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9.6 9.6 0 0 1-3.2-.6L3 21l1.7-4.6A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z" />
    </svg>
  );
}

function SendIcon({ className = '' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  );
}

function WhatsAppIcon({ className = '' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12.04 2a9.9 9.9 0 0 0-8.5 14.94L2 22l5.2-1.5A9.9 9.9 0 1 0 12.04 2Zm0 1.8a8.1 8.1 0 1 1-4.13 15.06l-.3-.18-3.05.88.9-2.96-.19-.31A8.1 8.1 0 0 1 12.04 3.8Zm-3.2 4c-.17 0-.45.06-.68.31-.24.25-.9.87-.9 2.12s.92 2.45 1.05 2.62c.13.16 1.8 2.86 4.4 3.9 2.15.85 2.59.68 3.06.63.47-.04 1.51-.61 1.72-1.2.21-.6.21-1.1.15-1.21-.06-.1-.23-.17-.49-.3-.25-.12-1.5-.73-1.73-.82-.23-.08-.4-.12-.57.13-.16.25-.65.82-.8.99-.14.16-.29.18-.54.06-.25-.13-1.06-.39-2.02-1.24-.75-.66-1.25-1.47-1.4-1.72-.14-.25-.01-.39.11-.51.11-.11.25-.29.38-.44.12-.15.16-.25.25-.42.08-.16.04-.31-.02-.44-.06-.12-.57-1.37-.78-1.87-.19-.45-.38-.4-.53-.4h-.46Z" />
    </svg>
  );
}

export default function LiveChat({ whatsappHref = '' }) {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState(readToken);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [unread, setUnread] = useState(0);

  const tokenRef = useRef(token);
  const openRef = useRef(open);
  const lastIdRef = useRef(0);
  const logRef = useRef(null);
  const inputRef = useRef(null);

  tokenRef.current = token;
  openRef.current = open;

  const mergeMessages = useCallback((incoming) => {
    if (!Array.isArray(incoming) || incoming.length === 0) return;
    setMessages((current) => {
      const seen = new Set(current.map((message) => message.id));
      const merged = [...current];
      incoming.forEach((message) => {
        if (!seen.has(message.id)) merged.push(message);
      });
      merged.sort((a, b) => a.id - b.id);
      return merged;
    });
    lastIdRef.current = Math.max(lastIdRef.current, ...incoming.map((message) => message.id));
  }, []);

  const sync = useCallback(async () => {
    const activeToken = tokenRef.current;
    if (!activeToken) return;
    try {
      const result = await chatRequest(`/api/support/chat?after=${lastIdRef.current}`, { token: activeToken });
      if (!result.token) {
        // The thread is gone (database reset or an expired token): start over quietly.
        writeToken('');
        tokenRef.current = '';
        lastIdRef.current = 0;
        setToken('');
        setMessages([]);
        setUnread(0);
        return;
      }
      const incoming = result.messages || [];
      const staffReplies = incoming.filter((message) => message.sender === 'staff');
      if (staffReplies.length && !openRef.current) {
        setUnread((count) => count + staffReplies.length);
      }
      // The "we picked it up" note only clears once the team actually answers.
      if (staffReplies.length) setWaiting(false);
      mergeMessages(incoming);
    } catch (syncError) {
      if (openRef.current) setError(syncError.message);
    }
  }, [mergeMessages]);

  useEffect(() => {
    if (!token) return undefined;
    const tick = () => {
      if (document.hidden) return;
      sync();
    };
    tick();
    const interval = window.setInterval(tick, open ? POLL_OPEN_MS : POLL_IDLE_MS);
    document.addEventListener('visibilitychange', tick);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [token, open, sync]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    window.setTimeout(() => inputRef.current?.focus(), 60);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages, open, waiting]);

  function togglePanel() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setUnread(0);
    setError('');
    sync();
  }

  async function send(event, preset) {
    event?.preventDefault();
    const body = String(preset ?? draft).trim();
    if (!body || sending) return;

    setSending(true);
    setError('');
    try {
      const result = await chatRequest('/api/support/chat', {
        method: 'POST',
        token,
        data: { body, token, name, email, page: window.location.pathname },
      });
      writeToken(result.token);
      tokenRef.current = result.token;
      setToken(result.token);
      mergeMessages(result.messages || []);
      if (!preset) setDraft('');
      setWaiting(true);
    } catch (sendError) {
      setError(sendError.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="live-chat-launcher"
        aria-expanded={open}
        aria-controls="live-chat-panel"
        aria-label={open ? 'Close live chat support' : 'Open live chat support'}
        onClick={togglePanel}
      >
        {open ? <span aria-hidden="true" className="live-chat-launcher__close">×</span> : <ChatIcon className="live-chat-launcher__icon" />}
        <span className="live-chat-launcher__label">{open ? 'Close chat' : 'Chat with us'}</span>
        {!open && unread > 0 && <span className="live-chat-badge">{unread > 9 ? '9+' : unread}</span>}
      </button>

      {open && (
        <section className="live-chat-panel" id="live-chat-panel" role="dialog" aria-label="Live chat with kenyaBook support">
          <header className="live-chat-panel__header">
            <div>
              <p className="live-chat-panel__title">kenyaBook support</p>
              <p className="live-chat-panel__subtitle">Usually replies within a few minutes</p>
            </div>
            <button className="live-chat-panel__close" type="button" aria-label="Close live chat" onClick={() => setOpen(false)}>×</button>
          </header>

          <div className="live-chat-log" ref={logRef} aria-live="polite">
            {messages.length === 0 && (
              <div className="live-chat-welcome">
                <p className="live-chat-welcome__title">Karibu! How can we help?</p>
                <p className="live-chat-welcome__text">Ask about safaris, stays, M-Pesa payments, or an existing booking. A member of our team replies here.</p>
                <div className="live-chat-quick">
                  {QUICK_REPLIES.map((reply) => (
                    <button key={reply} type="button" className="live-chat-quick__item" onClick={(event) => send(event, reply)}>{reply}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message) => (
              <div className={`live-chat-bubble live-chat-bubble--${message.sender === 'staff' ? 'staff' : 'visitor'}`} key={message.id}>
                <p className="live-chat-bubble__body">{message.body}</p>
                <p className="live-chat-bubble__meta">
                  {message.sender === 'staff' ? message.author || 'Support team' : 'You'} · {timeLabel(message.created_at)}
                </p>
              </div>
            ))}

            {waiting && messages.length > 0 && (
              <p className="live-chat-waiting" role="status">Message sent. A team member is picking it up…</p>
            )}
          </div>

          {error && <p className="live-chat-error" role="alert">{error}</p>}

          <form className="live-chat-composer" onSubmit={(event) => send(event)}>
            {detailsOpen ? (
              <div className="live-chat-details">
                <input aria-label="Your name" className="live-chat-input" maxLength={100} onChange={(event) => setName(event.target.value)} placeholder="Your name" value={name} />
                <input aria-label="Your email" className="live-chat-input" maxLength={160} onChange={(event) => setEmail(event.target.value)} placeholder="Email for follow-up" type="email" value={email} />
              </div>
            ) : (
              <button className="live-chat-details-toggle" type="button" onClick={() => setDetailsOpen(true)}>Add your name and email for follow-up</button>
            )}

            <div className="live-chat-composer__row">
              <textarea
                aria-label="Your message"
                className="live-chat-input live-chat-input--message"
                maxLength={2000}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Write your message…"
                ref={inputRef}
                rows={2}
                value={draft}
              />
              <button className="live-chat-send" disabled={sending || !draft.trim()} type="submit">
                <SendIcon className="live-chat-send__icon" />
                <span>{sending ? 'Sending' : 'Send'}</span>
              </button>
            </div>
          </form>

          {whatsappHref && (
            <a className="live-chat-whatsapp" href={whatsappHref} rel="noopener noreferrer" target="_blank">
              <WhatsAppIcon className="live-chat-whatsapp__icon" />
              <span>Prefer WhatsApp? Message our team there.</span>
            </a>
          )}
        </section>
      )}
    </>
  );
}
