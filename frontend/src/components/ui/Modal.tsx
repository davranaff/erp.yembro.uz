'use client';

import { useModalLifecycle } from '@/hooks/useModalLifecycle';
import { useUnsavedChangesGuard } from '@/hooks/useUnsavedChangesGuard';

import Icon from './Icon';

interface ModalProps {
  title: string;
  onClose: () => void;
  footer?: React.ReactNode;
  children: React.ReactNode;
}

export default function Modal({ title, onClose, footer, children }: ModalProps) {
  const { containerRef, handleClose, handleClickCapture } = useUnsavedChangesGuard(onClose);
  useModalLifecycle(handleClose);
  return (
    <div className="modal-backdrop" onClick={handleClose} onClickCapture={handleClickCapture}>
      <div className="modal" ref={containerRef} onClick={(e) => e.stopPropagation()}>
        <div className="modal-hdr">
          <h3>{title}</h3>
          <button
            className="close-btn"
            onClick={handleClose}
            aria-label="Закрыть"
            title="Закрыть (Esc)"
          >
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-ftr">{footer}</div>}
      </div>
    </div>
  );
}
