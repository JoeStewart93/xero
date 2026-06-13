import { MouseEvent, ReactNode, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

interface ModalShellProps {
  ariaLabel: string;
  children: ReactNode;
  onClose: () => void;
  subtitle?: string;
  title: string;
  variant?: 'center' | 'side' | 'wide';
}

export function ModalShell({ ariaLabel, children, onClose, subtitle, title, variant = 'center' }: ModalShellProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  function handleBackdropMouseDown(event: MouseEvent<HTMLDivElement>): void {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  return createPortal(
    <div className={`modal-backdrop modal-backdrop--${variant}`} onMouseDown={handleBackdropMouseDown} role="presentation">
      <section aria-label={ariaLabel} aria-modal="true" className={`modal-shell modal-shell--${variant}`} role="dialog">
        <div className="modal-shell-header">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          <button aria-label={`Close ${title}`} className="modal-shell-close" onClick={onClose} type="button">
            <X aria-hidden="true" size={17} strokeWidth={2.2} />
          </button>
        </div>
        {children}
      </section>
    </div>,
    document.body,
  );
}
