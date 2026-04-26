'use client';

import { useState } from 'react';

import Badge from '@/components/ui/Badge';
import DataTable from '@/components/ui/DataTable';
import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import Panel from '@/components/ui/Panel';
import RowActions from '@/components/ui/RowActions';
import { useHasLevel } from '@/hooks/usePermissions';
import {
  sellerTokensCrud,
  useCreateSellerToken,
  useRevokeSellerToken,
} from '@/hooks/useSellerTokens';
import { usePeople } from '@/hooks/usePeople';
import { ApiError } from '@/lib/api';
import type { SellerDeviceToken } from '@/types/auth';


export default function SellerTokensPage() {
  const { data: tokens, isLoading } = sellerTokensCrud.useList();
  const create = useCreateSellerToken();
  const revoke = useRevokeSellerToken();
  const { data: people } = usePeople({ is_active: 'true' });

  const hasLevel = useHasLevel();
  const canEdit = hasLevel('vet', 'rw');

  const [createOpen, setCreateOpen] = useState(false);
  const [user, setUser] = useState('');
  const [label, setLabel] = useState('');
  const [createdToken, setCreatedToken] = useState<SellerDeviceToken | null>(null);

  const handleCreate = async () => {
    try {
      const result = await create.mutateAsync({ user, label });
      setCreatedToken(result);
      setCreateOpen(false);
      setUser('');
      setLabel('');
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Ошибка';
      alert(msg);
    }
  };

  const handleRevoke = (t: SellerDeviceToken) => {
    if (!confirm(`Отозвать токен «${t.label || t.masked_token}»? Это действие необратимо.`)) {
      return;
    }
    revoke.mutate(t.id, {
      onError: (err) => alert(`Не удалось: ${err.message}`),
    });
  };

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Токены продавцов</h1>
          <div className="sub">
            Долговременные Bearer-токены для public-сканера{' '}
            <code style={{ fontSize: 12 }}>/scan/&lt;barcode&gt;</code>
          </div>
        </div>
        <div className="actions">
          {canEdit && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setCreateOpen(true)}
            >
              <Icon name="plus" size={14} /> Создать токен
            </button>
          )}
        </div>
      </div>

      <Panel flush>
        <DataTable<SellerDeviceToken>
          isLoading={isLoading}
          rows={tokens}
          rowKey={(t) => t.id}
          emptyMessage="Нет токенов. Создайте первый, чтобы продавец мог сканировать штрих-коды и продавать."
          columns={[
            { key: 'user', label: 'Продавец',
              render: (t) => (
                <>
                  <div style={{ fontWeight: 500 }}>{t.user_full_name}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>{t.user_email ?? ''}</div>
                </>
              ) },
            { key: 'label', label: 'Метка', cellStyle: { fontSize: 12 },
              render: (t) => t.label || '—' },
            { key: 'masked', label: 'Токен', mono: true, cellStyle: { fontSize: 12 },
              render: (t) => t.masked_token },
            { key: 'last', label: 'Последнее использование', mono: true,
              cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
              render: (t) => t.last_used_at
                ? new Date(t.last_used_at).toLocaleString('ru-RU')
                : 'не использовался' },
            { key: 'created', label: 'Создан', mono: true,
              cellStyle: { fontSize: 11, color: 'var(--fg-3)' },
              render: (t) => new Date(t.created_at).toLocaleDateString('ru-RU') },
            { key: 'status', label: 'Статус',
              render: (t) => t.revoked_at
                ? <Badge tone="danger" dot>Отозван</Badge>
                : t.is_active
                ? <Badge tone="success" dot>Активен</Badge>
                : <Badge tone="neutral" dot>Неактивен</Badge> },
            { key: 'actions', label: '', width: 60, align: 'right',
              render: (t) => canEdit ? (
                <RowActions
                  actions={[
                    {
                      label: 'Отозвать',
                      danger: true,
                      hidden: Boolean(t.revoked_at) || !t.is_active,
                      disabled: revoke.isPending,
                      onClick: () => handleRevoke(t),
                    },
                  ]}
                />
              ) : null },
          ]}
        />
      </Panel>

      {createOpen && (
        <Modal
          title="Создать токен продавца"
          onClose={() => setCreateOpen(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setCreateOpen(false)}>Отмена</button>
              <button
                className="btn btn-primary"
                disabled={!user || create.isPending}
                onClick={handleCreate}
              >
                {create.isPending ? 'Создание…' : 'Создать'}
              </button>
            </>
          }
        >
          <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
            Токен показывается <strong>только один раз</strong> при создании. Скопируйте и
            передайте продавцу. Если потеряли — отзовите и создайте новый.
          </div>
          <div className="field">
            <label>Сотрудник *</label>
            <select className="input" value={user} onChange={(e) => setUser(e.target.value)}>
              <option value="">—</option>
              {people?.map((p) => (
                <option key={p.user} value={p.user}>
                  {p.user_full_name} · {p.position_title || p.user_email}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Метка <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>(точка продаж)</span></label>
            <input
              className="input"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Магазин Юнусабад / Палатка №3 / ..."
            />
          </div>
        </Modal>
      )}

      {createdToken && (
        <Modal
          title="Токен создан"
          onClose={() => setCreatedToken(null)}
          footer={
            <button className="btn btn-primary" onClick={() => setCreatedToken(null)}>
              Я скопировал токен
            </button>
          }
        >
          <div style={{ fontSize: 13, marginBottom: 12 }}>
            Токен для <strong>{createdToken.user_full_name}</strong>
            {createdToken.label && <> · {createdToken.label}</>}.
          </div>
          <div style={{
            padding: 12, background: 'var(--bg-soft)', borderRadius: 6,
            border: '1px solid var(--brand-orange)',
            marginBottom: 12,
          }}>
            <div style={{
              fontSize: 11, fontWeight: 700, color: 'var(--fg-3)',
              textTransform: 'uppercase', letterSpacing: '.04em',
              marginBottom: 6,
            }}>
              Скопируйте — этот токен больше не будет показан
            </div>
            <code style={{
              display: 'block', wordBreak: 'break-all',
              fontFamily: 'var(--font-mono)', fontSize: 13,
              padding: 8, background: 'var(--bg-card, #fff)',
              border: '1px solid var(--border)', borderRadius: 4,
            }}>
              {createdToken.token}
            </code>
            <button
              className="btn btn-secondary btn-sm"
              style={{ marginTop: 8 }}
              onClick={() => {
                navigator.clipboard?.writeText(createdToken.token!);
                alert('Скопировано');
              }}
            >
              Копировать
            </button>
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            Передайте продавцу: пусть откроет <code>/scan/login</code> и введёт токен.
            После этого сканирование штрих-кода ведёт на <code>/scan/&lt;barcode&gt;</code>
            и кнопка «Продать» работает.
          </div>
        </Modal>
      )}
    </>
  );
}
