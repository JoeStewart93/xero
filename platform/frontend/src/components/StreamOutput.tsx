import { useEffect, useMemo, useRef, useState } from 'react';
import { Lock, Trash2, Unlock } from 'lucide-react';

export interface StreamOutputChunk {
  chunk: string;
}

interface StreamOutputProps {
  chunks: StreamOutputChunk[];
  isComplete: boolean;
  onClear: () => void;
  stream: string;
}

function streamText(chunks: StreamOutputChunk[]): string {
  return chunks.map((chunk) => chunk.chunk).join('');
}

function isNearBottom(element: HTMLElement): boolean {
  return element.scrollHeight - element.scrollTop - element.clientHeight < 24;
}

export function StreamOutput({ chunks, isComplete, onClear, stream }: StreamOutputProps) {
  const outputRef = useRef<HTMLPreElement | null>(null);
  const [followOutput, setFollowOutput] = useState(true);
  const output = useMemo(() => streamText(chunks), [chunks]);

  useEffect(() => {
    if (!followOutput || !outputRef.current) {
      return;
    }
    outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [followOutput, output]);

  function handleScroll(): void {
    const element = outputRef.current;
    if (!element) {
      return;
    }
    setFollowOutput(isNearBottom(element));
  }

  return (
    <div className="stream-output-panel" data-testid="stream-output-panel">
      <div className="stream-output-toolbar">
        <div>
          <strong>Live {stream}</strong>
          <span>{isComplete ? 'complete' : 'streaming'} / {chunks.length} chunks</span>
        </div>
        <div>
          <button
            aria-label={followOutput ? 'Pause stream auto-scroll' : 'Resume stream auto-scroll'}
            className="secondary-button stream-output-icon-button"
            onClick={() => setFollowOutput((current) => !current)}
            title={followOutput ? 'Pause auto-scroll' : 'Resume auto-scroll'}
            type="button"
          >
            {followOutput ? <Lock aria-hidden="true" size={14} strokeWidth={2.1} /> : <Unlock aria-hidden="true" size={14} strokeWidth={2.1} />}
          </button>
          <button
            aria-label="Clear stream buffer"
            className="secondary-button stream-output-icon-button"
            disabled={chunks.length === 0}
            onClick={onClear}
            title="Clear stream buffer"
            type="button"
          >
            <Trash2 aria-hidden="true" size={14} strokeWidth={2.1} />
          </button>
        </div>
      </div>
      <pre
        className="stream-output-buffer"
        data-testid="stream-output-buffer"
        onScroll={handleScroll}
        ref={outputRef}
      >
        {output || '(waiting for streamed output)'}
      </pre>
    </div>
  );
}
