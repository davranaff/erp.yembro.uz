'use client';

import { useState } from 'react';

import Panel from '@/components/ui/Panel';
import { ApiError } from '@/lib/api';
import { useChangePassword } from '@/hooks/useChangePassword';

export default function SecurityTab() {
  const change = useChangePassword();
  const [oldPwd, setOldPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirmPwd, setConfirmPwd] = useState('');
  const [success, setSuccess] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const fieldErrors = (change.error instanceof ApiError && change.error.status === 400)
    ? (change.error.data as Record<string, string[]>) ?? {}
    : {};

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccess(false);
    setConfirmError(null);
    if (newPwd !== confirmPwd) {
      setConfirmError('Подтверждение не совпадает с новым паролем.');
      return;
    }
    try {
      await change.mutateAsync({ old_password: oldPwd, new_password: newPwd });
      setSuccess(true);
      setOldPwd('');
      setNewPwd('');
      setConfirmPwd('');
    } catch {
      // отображается через fieldErrors
    }
  };

  return (
    <Panel title="Безопасность">
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 480 }}>
        <div className="field">
          <label>Текущий пароль</label>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={oldPwd}
            onChange={(e) => setOldPwd(e.target.value)}
            required
          />
          {fieldErrors.old_password && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.old_password.join(' · ')}
            </div>
          )}
        </div>

        <div className="field">
          <label>Новый пароль</label>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            value={newPwd}
            onChange={(e) => setNewPwd(e.target.value)}
            required
            minLength={8}
          />
          {fieldErrors.new_password && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {fieldErrors.new_password.join(' · ')}
            </div>
          )}
          <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            Минимум 8 символов, не должен совпадать с текущим.
          </div>
        </div>

        <div className="field">
          <label>Подтверждение нового пароля</label>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            value={confirmPwd}
            onChange={(e) => setConfirmPwd(e.target.value)}
            required
            minLength={8}
          />
          {confirmError && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{confirmError}</div>
          )}
        </div>

        {change.error instanceof ApiError && change.error.status !== 400 && (
          <div style={{ fontSize: 12, color: 'var(--danger)' }}>
            Ошибка сервера: {change.error.status}
          </div>
        )}

        {success && (
          <div style={{ fontSize: 12, color: 'var(--success)' }}>
            Пароль успешно изменён.
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={change.isPending || !oldPwd || !newPwd || !confirmPwd}
          >
            {change.isPending ? 'Изменение…' : 'Сменить пароль'}
          </button>
        </div>
      </form>
    </Panel>
  );
}
