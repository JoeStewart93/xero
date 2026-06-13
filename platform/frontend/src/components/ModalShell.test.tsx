import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ModalShell } from './ModalShell';

describe('ModalShell', () => {
  it('closes from the button, Escape key, and backdrop without closing on inner clicks', () => {
    const onClose = vi.fn();

    render(
      <ModalShell ariaLabel="Example modal" onClose={onClose} title="Example">
        <button type="button">Inner action</button>
      </ModalShell>,
    );

    const dialog = screen.getByRole('dialog', { name: 'Example modal' });
    expect(dialog.getAttribute('aria-modal')).toBe('true');

    fireEvent.mouseDown(dialog);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.mouseDown(document.querySelector('.modal-backdrop') as Element);
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByRole('button', { name: 'Close Example' }));
    expect(onClose).toHaveBeenCalledTimes(3);
  });
});
