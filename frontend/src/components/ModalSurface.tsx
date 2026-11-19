import React, { useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '../utils/cn';

/** Native modal primitive supplies focus containment, Escape and focus restoration. */
export function ModalSurface({ open, onClose, label, children, className }: {
  open: boolean; onClose: () => void; label: string; children: React.ReactNode; className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
    return () => { if (dialog.open) dialog.close(); };
  }, [open]);
  return createPortal(<dialog ref={ref} aria-label={label} onCancel={e => { e.preventDefault(); close.current(); }}
    onClick={e => { if (e.target === e.currentTarget) close.current(); }}
    className={cn('ui-dialog m-auto max-w-xl max-h-[90dvh] overflow-y-auto border border-line-strong bg-surface p-0 text-ink shadow-xl', className)}>
    <div className="min-w-0 w-full">{children}</div>
  </dialog>, document.body);
}
