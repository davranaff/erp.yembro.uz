'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import Icon from '@/components/ui/Icon';
import { useSubaccounts } from '@/hooks/useAccounts';
import { useModules } from '@/hooks/useModules';
import { paymentsCrud } from '@/hooks/usePayments';
import { useHasLevel, usePermissions } from '@/hooks/usePermissions';
import { LEVEL_ORDER } from '@/types/auth';
import type { GLSubaccount } from '@/types/auth';

import CashAccountModal from './CashAccountModal';

function fmtUzs(v: number): string {
  return v.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

export default function CashboxListPage() {
  const [cashAccountOpen, setCashAccountOpen] = useState(false);
  const [moduleId, setModuleId] = useState('');

  const hasLevel = useHasLevel();
  // Org-admin: только владелец/CFO. Управление кассами/счетами — это
  // структурное изменение плана счетов, не делегируется heads.
  const isOrgAdmin = hasLevel('admin', 'admin') || hasLevel('ledger', 'admin') || hasLevel('cash', 'admin');

  const { data: subs } = useSubaccounts();
  const { data: modules } = useModules();
  const permissions = usePermissions();

  // Скоупим список касс по RBAC: head вет не видит feed-кассу и наоборот.
  const accessibleModuleIds = useMemo<Set<string> | null>(() => {
    if (isOrgAdmin) return null;
    if (!modules) return new Set();
    const allowedCodes = new Set(
      Object.entries(permissions)
        .filter(([, lvl]) => LEVEL_ORDER[lvl] >= LEVEL_ORDER.rw)
        .map(([code]) => code),
    );
    return new Set(
      modules.filter((m) => allowedCodes.has(m.code)).map((m) => m.id),
    );
  }, [isOrgAdmin, modules, permissions]);

  // Все posted-платежи для расчёта баланса по каждой кассе.
  const { data: postedPayments } = paymentsCrud.useList({ status: 'posted' });

  const balanceByAccount = useMemo(() => {
    const map = new Map<string, number>();
    if (!postedPayments) return map;
    for (const p of postedPayments) {
      if (!p.cash_subaccount) continue;
      const amt = parseFloat(p.amount_uzs || '0');
      if (Number.isNaN(amt)) continue;
      const delta = p.direction === 'in' ? amt : -amt;
      map.set(p.cash_subaccount, (map.get(p.cash_subaccount) ?? 0) + delta);
    }
    return map;
  }, [postedPayments]);

  const cashAccounts: GLSubaccount[] = useMemo(() => {
    if (!subs) return [];
    return subs
      .filter((s) => s.code.startsWith('50.') || s.code.startsWith('51.'))
      .filter((s) => {
        if (accessibleModuleIds === null) return true; // org-admin
        if (!s.module) return false;                   // null-module → только admin
        return accessibleModuleIds.has(s.module);
      })
      .filter((s) => !moduleId || s.module === moduleId)
      .sort((a, b) => a.code.localeCompare(b.code));
  }, [subs, moduleId, accessibleModuleIds]);

  // Список модулей в дропдауне-фильтре: head'ам показываем только их,
  // org-admin'у — все.
  const filterableModules = useMemo(() => {
    if (!modules) return [];
    if (accessibleModuleIds === null) return modules;
    return modules.filter((m) => accessibleModuleIds.has(m.id));
  }, [modules, accessibleModuleIds]);

  return (
    <>
      <div className="page-hdr">
        <div>
          <h1>Касса и банк</h1>
          <div className="sub">
            Выберите кассу или счёт, чтобы посмотреть движения и провести операции.
          </div>
        </div>
        <div className="actions">
          {isOrgAdmin && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setCashAccountOpen(true)}
              title="Создать новую кассу или расчётный счёт под выбранный модуль"
            >
              <Icon name="plus" size={14} /> Касса/Банк
            </button>
          )}
        </div>
      </div>

      {/* Фильтр по модулю — оставляем только если их больше одного. */}
      {filterableModules.length > 1 && (
        <div className="filter-bar" style={{ marginBottom: 16 }}>
          <div className="filter-cell" style={{ minWidth: 240 }}>
            <label>Модуль</label>
            <select
              className="input"
              value={moduleId}
              onChange={(e) => setModuleId(e.target.value)}
            >
              <option value="">{accessibleModuleIds === null ? 'Все' : 'Все мои'}</option>
              {filterableModules.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {cashAccounts.length === 0 ? (
        <div style={{
          padding: 32, textAlign: 'center',
          background: 'var(--bg-soft)', borderRadius: 8,
          color: 'var(--fg-3)',
        }}>
          <Icon name="bag" size={28} />
          <div style={{ marginTop: 8, fontSize: 14, fontWeight: 500 }}>
            Нет касс/счетов
          </div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            {moduleId
              ? 'Для выбранного модуля нет касс.'
              : isOrgAdmin
                ? 'Создайте первую кассу через «+ Касса/Банк».'
                : 'Попросите администратора создать кассу для вашего модуля.'}
          </div>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: 12,
          }}
        >
          {cashAccounts.map((acc) => {
            const balance = balanceByAccount.get(acc.id) ?? 0;
            const isBank = acc.code.startsWith('51.');
            const moduleLabel = acc.module
              ? modules?.find((m) => m.id === acc.module)?.name ?? '—'
              : 'Общая';
            const balanceColor = balance >= 0 ? 'var(--success)' : 'var(--danger)';

            return (
              <Link
                key={acc.id}
                href={`/finance/cashbox/${acc.id}`}
                style={{
                  display: 'block',
                  padding: 16,
                  background: 'var(--bg-raised)',
                  border: '1px solid var(--border)',
                  borderRadius: 10,
                  textDecoration: 'none',
                  color: 'inherit',
                  transition: 'border-color .12s, transform .12s, box-shadow .12s',
                }}
                className="cashbox-card"
              >
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
                }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 8,
                    background: 'var(--bg-soft)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 18,
                  }}>
                    {isBank ? '🏦' : '💵'}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 14, fontWeight: 600,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {acc.name}
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                      {acc.code} · {isBank ? 'Банк' : 'Касса'}
                    </div>
                  </div>
                  <Icon name="chevron-right" size={16} />
                </div>

                <div style={{
                  fontSize: 11, color: 'var(--fg-3)',
                  textTransform: 'uppercase', letterSpacing: '.04em',
                  marginBottom: 4,
                }}>
                  Текущий баланс
                </div>
                <div className="mono" style={{
                  fontSize: 20, fontWeight: 700, color: balanceColor,
                  marginBottom: 8,
                }}>
                  {postedPayments ? `${fmtUzs(balance)} сум` : '—'}
                </div>

                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  fontSize: 12, color: 'var(--fg-2)',
                  paddingTop: 8, borderTop: '1px solid var(--border)',
                }}>
                  <Icon name="building" size={12} />
                  <span>Модуль: {moduleLabel}</span>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {cashAccountOpen && (
        <CashAccountModal
          initial={null}
          defaultModuleId={moduleId || undefined}
          onClose={() => setCashAccountOpen(false)}
        />
      )}

      <style jsx>{`
        :global(.cashbox-card:hover) {
          border-color: var(--brand-orange) !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
        }
      `}</style>
    </>
  );
}
