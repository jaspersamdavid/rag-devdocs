import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { askQuestion, checkHealth } from './api';
import type { Message, SourceChunk } from './types';

const THINKING_PHRASES = [
  'Searching documentation...',
  'Analyzing sources...',
  'Retrieving relevant chunks...',
  'Processing query...',
  'Synthesizing answer...',
];

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [showSources, setShowSources] = useState(false);
  const [activeSources, setActiveSources] = useState<SourceChunk[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const isEmptyState = messages.filter((m) => !m.isLoading).length === 0;

  useEffect(() => {
    checkHealth().then(setIsConnected).catch(() => setIsConnected(false));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const lastAssistant = messages
      .filter((m) => !m.isLoading && m.role === 'assistant')
      .pop();
    if (lastAssistant?.sources && lastAssistant.sources.length > 0) {
      setActiveSources(lastAssistant.sources);
      setShowSources(true);
    }
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const question = input.trim();
    setInput('');
    setIsLoading(true);

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: question,
    };

    const loadingMessage: Message = {
      id: 'loading',
      role: 'assistant',
      content: '',
      isLoading: true,
    };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);

    try {
      const response = await askQuestion(question);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === 'loading'
            ? {
                id: Date.now().toString(),
                role: 'assistant',
                content: response.answer,
                sources: response.sources,
              }
            : msg
        )
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to get response';
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === 'loading'
            ? {
                id: Date.now().toString(),
                role: 'assistant',
                content: `I encountered an error: ${errorMessage}`,
                sources: [],
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--color-bg-primary)' }}>
      {/* Sidebar */}
      <Sidebar isConnected={isConnected} />

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {isEmptyState ? (
          /* Empty state — centered greeting */
          <div className="flex-1 flex flex-col items-center justify-center px-4">
            <div className="w-full max-w-[640px] flex flex-col items-center">
              <div className="mb-8 flex flex-col items-center">
                <div className="w-12 h-12 rounded-full flex items-center justify-center mb-5" style={{ background: 'linear-gradient(135deg, #e8a55d 0%, #d4943f 100%)' }}>
                  <SparkleIcon size={26} />
                </div>
                <h1 className="text-[22px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  What can I help you with?
                </h1>
              </div>
              <InputArea
                input={input}
                setInput={setInput}
                isLoading={isLoading}
                onSubmit={handleSubmit}
                onKeyDown={handleKeyDown}
                inputRef={inputRef}
              />
              <p className="mt-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                DevDocs can make mistakes. Please verify important information.
              </p>
            </div>
          </div>
        ) : (
          /* Chat state */
          <>
            <div className="flex-1 flex overflow-hidden">
              {/* Messages */}
              <div className="flex-1 overflow-y-auto">
                <div className="max-w-[720px] mx-auto px-4 py-6">
                  <div className="space-y-6">
                    {messages.map((message) => (
                      <MessageRow
                        key={message.id}
                        message={message}
                        onViewSources={(sources) => {
                          setActiveSources(sources);
                          setShowSources(true);
                        }}
                      />
                    ))}
                    <div ref={messagesEndRef} />
                  </div>
                </div>
              </div>

              {/* Sources panel */}
              {showSources && activeSources.length > 0 && (
                <SourcesPanel
                  sources={activeSources}
                  onClose={() => setShowSources(false)}
                />
              )}
            </div>

            {/* Bottom input */}
            <div className="flex-none px-4 pb-4 pt-2">
              <div className="max-w-[720px] mx-auto">
                <InputArea
                  input={input}
                  setInput={setInput}
                  isLoading={isLoading}
                  onSubmit={handleSubmit}
                  onKeyDown={handleKeyDown}
                  inputRef={inputRef}
                />
                <p className="mt-2 text-center text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  DevDocs can make mistakes. Please verify important information.
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/* ─── Sidebar ─── */

function Sidebar({ isConnected }: { isConnected: boolean | null }) {
  return (
    <aside
      className="w-[260px] flex-none flex flex-col border-r"
      style={{
        background: 'var(--color-bg-sidebar)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* New chat */}
      <div className="p-3">
        <button
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg transition-colors text-left"
          style={{ color: 'var(--color-text-primary)' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
          <span className="text-sm font-medium">New chat</span>
        </button>
      </div>

      {/* Chat list */}
      <div className="flex-1 overflow-y-auto px-3">
        <div className="mb-1 px-2 py-1.5">
          <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            Today
          </span>
        </div>
        <button
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors text-left"
          style={{ background: 'var(--color-bg-hover)', color: 'var(--color-text-primary)' }}
        >
          <span className="text-sm truncate">Chat 1</span>
        </button>
      </div>

      {/* User profile */}
      <div className="p-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center gap-3 px-2 py-1.5">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium"
            style={{ background: 'linear-gradient(135deg, #e8a55d 0%, #d4943f 100%)' }}
          >
            J
          </div>
          <span className="text-sm" style={{ color: 'var(--color-text-primary)' }}>Jasper</span>
          {/* Connection indicator */}
          <div className="ml-auto flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full"
              style={{
                background:
                  isConnected === null
                    ? 'var(--color-accent)'
                    : isConnected
                    ? '#4ade80'
                    : '#ef4444',
              }}
            />
          </div>
        </div>
      </div>
    </aside>
  );
}

/* ─── Input Area ─── */

function InputArea({
  input,
  setInput,
  isLoading,
  onSubmit,
  onKeyDown,
  inputRef,
}: {
  input: string;
  setInput: (val: string) => void;
  isLoading: boolean;
  onSubmit: (e: React.FormEvent) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}) {
  return (
    <form onSubmit={onSubmit} className="w-full">
      <div
        className="relative flex items-end rounded-2xl border transition-colors"
        style={{
          background: 'var(--color-bg-input)',
          borderColor: 'var(--color-border)',
        }}
      >
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about developer documentation..."
          disabled={isLoading}
          rows={1}
          className="w-full bg-transparent px-4 py-3.5 pr-12 resize-none min-h-[52px] max-h-[200px] focus:outline-none text-[15px] placeholder:text-[var(--color-text-muted)]"
          style={{ color: 'var(--color-text-primary)' }}
        />
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className="absolute right-2.5 bottom-2.5 p-1.5 rounded-lg transition-all disabled:opacity-30"
          style={{
            background: input.trim() && !isLoading ? 'var(--color-text-primary)' : 'transparent',
            color: input.trim() && !isLoading ? 'var(--color-bg-primary)' : 'var(--color-text-muted)',
          }}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="19" x2="12" y2="5" />
            <polyline points="5 12 12 5 19 12" />
          </svg>
        </button>
      </div>
    </form>
  );
}

/* ─── Message Row ─── */

function MessageRow({
  message,
  onViewSources,
}: {
  message: Message;
  onViewSources: (sources: SourceChunk[]) => void;
}) {
  if (message.isLoading) {
    return (
      <div className="flex gap-3.5">
        <div
          className="flex-none w-8 h-8 rounded-full flex items-center justify-center thinking-orb"
          style={{ background: 'linear-gradient(135deg, #e8a55d 0%, #d4943f 100%)' }}
        >
          <SparkleIcon size={18} />
        </div>
        <div className="flex-1 pt-1">
          <ThinkingIndicator />
        </div>
      </div>
    );
  }

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[85%] px-4 py-3 rounded-2xl text-[15px] leading-relaxed"
          style={{
            background: 'var(--color-bg-user-msg)',
            color: 'var(--color-text-primary)',
          }}
        >
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message
  const cleanContent = message.content.replace(/\[Source:[^\]]+\]/g, '').trim();
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div className="flex gap-3.5">
      <div
        className="flex-none w-8 h-8 rounded-full flex items-center justify-center mt-0.5"
        style={{ background: 'linear-gradient(135deg, #e8a55d 0%, #d4943f 100%)' }}
      >
        <SparkleIcon size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="markdown-content text-[15px]" style={{ color: 'var(--color-text-primary)' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{cleanContent}</ReactMarkdown>
        </div>
        {hasSources && (
          <button
            onClick={() => onViewSources(message.sources!)}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            style={{
              background: 'var(--color-bg-input)',
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-bg-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-bg-input)')}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <path d="M14 2v6h6" />
            </svg>
            {message.sources!.length} sources
          </button>
        )}
      </div>
    </div>
  );
}

/* ─── Thinking Indicator ─── */

function ThinkingIndicator() {
  const [phraseIndex, setPhraseIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPhraseIndex((prev) => (prev + 1) % THINKING_PHRASES.length);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-2.5">
      <div className="flex gap-1">
        <span className="thinking-dot w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-accent)' }} />
        <span className="thinking-dot w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-accent)' }} />
        <span className="thinking-dot w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-accent)' }} />
      </div>
      <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
        {THINKING_PHRASES[phraseIndex]}
      </span>
    </div>
  );
}

/* ─── Sources Panel ─── */

function SourcesPanel({
  sources,
  onClose,
}: {
  sources: SourceChunk[];
  onClose: () => void;
}) {
  return (
    <aside
      className="w-[340px] flex-none border-l overflow-y-auto sources-panel-enter"
      style={{
        background: 'var(--color-bg-source-panel)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Header */}
      <div
        className="sticky top-0 flex items-center justify-between px-4 py-3 border-b"
        style={{
          background: 'var(--color-bg-source-panel)',
          borderColor: 'var(--color-border)',
        }}
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4" style={{ color: 'var(--color-text-secondary)' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <path d="M14 2v6h6" />
          </svg>
          <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
            Sources
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded-full"
            style={{ background: 'var(--color-bg-input)', color: 'var(--color-text-secondary)' }}
          >
            {sources.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-primary)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-muted)')}
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* Source cards */}
      <div className="p-3 space-y-2">
        {sources.map((source, i) => (
          <SourceCard key={i} source={source} index={i} />
        ))}
      </div>
    </aside>
  );
}

/* ─── Source Card ─── */

function SourceCard({ source, index }: { source: SourceChunk; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const sourceName = source.source.split('/').pop() || source.source;
  const sourcePath = source.source;

  return (
    <div
      className="rounded-lg border overflow-hidden transition-colors"
      style={{
        background: expanded ? 'var(--color-bg-hover)' : 'var(--color-bg-primary)',
        borderColor: 'var(--color-border)',
      }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-colors"
        onMouseEnter={(e) => {
          if (!expanded) e.currentTarget.parentElement!.style.background = 'var(--color-bg-hover)';
        }}
        onMouseLeave={(e) => {
          if (!expanded) e.currentTarget.parentElement!.style.background = 'var(--color-bg-primary)';
        }}
      >
        <span
          className="flex-none w-5 h-5 rounded flex items-center justify-center text-[10px] font-medium"
          style={{ background: 'var(--color-bg-input)', color: 'var(--color-text-secondary)' }}
        >
          {index + 1}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate" style={{ color: 'var(--color-accent)' }}>
            {sourceName}
          </p>
          <p className="text-[11px] truncate" style={{ color: 'var(--color-text-muted)' }}>
            {sourcePath}
          </p>
        </div>
        <svg
          className={`flex-none w-4 h-4 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
          style={{ color: 'var(--color-text-muted)' }}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {expanded && (
        <div className="px-3 pb-3">
          <div
            className="rounded-md p-3 text-xs leading-relaxed font-mono whitespace-pre-wrap"
            style={{
              background: 'var(--color-bg-sidebar)',
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
            }}
          >
            {source.content.slice(0, 600)}
            {source.content.length > 600 ? '...' : ''}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Sparkle Icon (Claude-style) ─── */

function SparkleIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path
        d="M12 2L13.8 8.6L20 6L15.4 11L22 12L15.4 13L20 18L13.8 15.4L12 22L10.2 15.4L4 18L8.6 13L2 12L8.6 11L4 6L10.2 8.6L12 2Z"
        fill="white"
        opacity="0.95"
      />
    </svg>
  );
}

export default App;
