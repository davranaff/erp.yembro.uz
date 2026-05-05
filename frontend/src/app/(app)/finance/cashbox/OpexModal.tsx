'use client';

import { useEffect, useMemo, useState } from 'react';

import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import { useCounterparties } from '@/hooks/useCounterparties';
import { expenseArticlesCrud } from '@/hooks/useExpenseArticles';
import { useModules } from '@/hooks/useModules';
import { paymentsCrud, usePostPayment } from '@/hooks/usePayments';
import { useSubaccounts } from '@/hooks/useAccounts';
import { ApiError } from '@/lib/api';
import type { ExpenseArticle } from '@/types/auth';

export interface OpexPreselect {
  /** Preselect модуль (когда открыто из feed/slaughter/...). */
  moduleCode?: string;
  /** Стартовое направление: in / out. */
  direction?: 'out' | 'in';
  /**
   * Подсказка для быстрого выбора контр-субсчёта: код счета 20.XX,
   * соответствующий модулю. Если задан — будет автоматически отмечен.
   */
  suggestedContraCode?: string;
}

interface Props {
  preselect?: OpexPreselect;
  onClose: () => void;
}

const KIND_FOR_DIRECTION: Record<'out' | 'in', 'opex' | 'income'> = {
  out: 'opex',
  in: 'income',
};

/** Маппинг модуль → субсчёт НЗП по умолчанию. */
const MODULE_NZP: Record<string, string> = {
  matochnik: '20.01',
  feedlot: '20.02',
  incubation: '20.03',
  slaughter: '20.04',
  feed: '20.05',
  vet: '20.06',
};

type PayMethod = 'cash' | 'bank' | 'other';

const METHOD_TO_CHANNEL: Record<PayMethod, 'cash' | 'transfer' | 'other'> = {
  cash: 'cash',
  bank: 'transfer',
  other: 'other',
};

export default function OpexModal({ preselect, onClose }: Props) {
  const create = paymentsCrud.useCreate();
  const post = usePostPayment();

  const { data: modules } = useModules();
  const { data: subaccounts } = useSubaccounts();
  const { data: counterparties } = useCounterparties();
  const { data: articles } = expenseArticlesCrud.useList({ is_active: 'true' });

  const [direction, setDirection] = useState<'out' | 'in'>(preselect?.direction ?? 'out');
  const [kind, setKind] = useState<'opex' | 'income' | 'salary'>(
    KIND_FOR_DIRECTION[preselect?.direction ?? 'out'],
  );
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [method, setMethod] = useState<PayMethod>('cash');
  const [amount, setAmount] = useState('');
  const [cashSubId, setCashSubId] = useState('');
  const [contraSubId, setContraSubId] = useState('');
  const [articleId, setArticleId] = useState('');
  const [moduleId, setModuleId] = useState('');
  const [counterpartyId, setCounterpartyId] = useState('');
  const [notes, setNotes] = useState('');
  const [editContra, setEditContra] = useState(false);

  // Preselect модуль по коду
  useEffect(() => {
    if (preselect?.moduleCode && modules && !moduleId) {
      const m = modules.find((x) => x.code === preselect.moduleCode);
      if (m) setModuleId(m.id);
    }
  }, [preselect, modules, moduleId]);

  // Способ оплаты → касса/банк
  useEffect(() => {
    if (!subaccounts || subaccounts.length === 0) return;
    if (method === 'cash') {
      const s = subaccounts.find((x) => x.code === '50.01');
      if (s) setCashSubId(s.id);
    } else if (method === 'bank') {
      const s = subaccounts.find((x) => x.code === '51.01');
      if (s) setCashSubId(s.id);
    }
    // method === 'other' → пользователь выбирает сам
  }, [method, subaccounts]);

  // Preselect contra (suggestedContraCode)
  useEffect(() => {
    if (
      !contraSubId
      && preselect?.suggestedContraCode
      && subaccounts && subaccounts.length > 0
    ) {
      const s = subaccounts.find((x) => x.code === preselect.suggestedContraCode);
      if (s) setContraSubId(s.id);
    }
  }, [preselect, subaccounts, contraSubId]);

  useEffect(() => {
    setKind(KIND_FOR_DIRECTION[direction]);
  }, [direction]);

  const activeModuleCode = useMemo(
    () => modules?.find((m) => m.id === moduleId)?.code,
    [modules, moduleId],
  );
  const nzpCodeForModule = activeModuleCode ? MODULE_NZP[activeModuleCode] : undefined;

  const articleOptions = useMemo<ExpenseArticle[]>(() => {
    if (!articles) return [];
    const allowed = direction === 'out'
      ? new Set(['expense', 'salary'])
      : new Set(['income', 'transfer']);
    return articles
      .filter((a) => a.is_active && allowed.has(a.kind))
      .sort((a, b) => a.code.localeCompare(b.code));
  }, [articles, direction]);

  const handleArticleChange = (id: string) => {
    setArticleId(id);
    setEditContra(false);
    if (!id) return;
    const a = articles?.find((x) => x.id === id);
    if (!a) return;
    if (a.default_subaccount && a.default_subaccount !== contraSubId) {
      setContraSubId(a.default_subaccount);
    }
    if (a.default_module && !moduleId) {
      setModuleId(a.default_module);
    }
    if (a.kind === 'salary') setKind('salary');
    else if (direction === 'out') setKind('opex');
    else setKind('income');
  };

  const contraOptions = useMemo(() => {
    if (!subaccounts) return [];
    const excluded = new Set(['50.01', '51.01', '60.01', '60.02', '62.01', '62.02']);
    return subaccounts.filter((s) => !excluded.has(s.code));
  }, [subaccounts]);

  const quickContras = useMemo(() => {
    if (!subaccounts) return [];
    const quick: { code: string; id: string; label: string }[] = [];
    const add = (code: string, label: string) => {
      const s = subaccounts.find((x) => x.code === code);
      if (s) quick.push({ code, id: s.id, label });
    };
    if (nzpCodeForModule) {
      const s = subaccounts.find((x) => x.code === nzpCodeForModule);
      if (s) quick.push({ code: nzpCodeForModule, id: s.id, label: `${nzpCodeForModule} · НЗП модуля` });
    }
    if (direction === 'out') {
      add('26.01', '26.01 · Аренда/коммуналка');
      add('26.02', '26.02 · Связь');
      add('44.02', '44.02 · Доставка');
      add('91.02', '91.02 · Прочие расходы');
    } else {
      add('91.01', '91.01 · Прочие доходы');
    }
    return quick;
  }, [subaccounts, direction, nzpCodeForModule]);

  const error = create.error ?? post.error;
  const fieldErrors = error instanceof ApiError && error.status === 400
    ? ((error.data as Record<string, unknown>) ?? {})
    : {};

  const canSubmit =
    Boolean(amount)
    && parseFloat(amount) > 0
    && Boolean(cashSubId)
    && Boolean(contraSubId)
    && !create.isPending
    && !post.isPending;

  const getFieldErr = (k: string): string | null => {
    const v = (fieldErrors as Record<string, unknown>)[k];
    if (Array.isArray(v)) return v.join(' · ');
    if (typeof v === 'string') return v;
    return null;
  };

  const handleSubmit = async () => {
    try {
      const created = await create.mutateAsync({
        date,
        module: moduleId || null,
        direction,
        channel: METHOD_TO_CHANNEL[method],
        kind,
        counterparty: counterpartyId || null,
        amount_uzs: amount,
        cash_subaccount: cashSubId,
        contra_subaccount: contraSubId,
        expense_article: articleId || null,
        notes,
      });
      if (created?.id) {
        await post.mutateAsync({ id: created.id });
      }
      onClose();
    } catch {
      /* ошибка отображается из mutation-ов */
    }
  };

  const title = direction === 'out' ? 'Новый расход' : 'Новый приход';
  const selectedContra = subaccounts?.find((s) => s.id === contraSubId);
  const contraIsAutoFromArticle = Boolean(articleId) && !editContra;

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
          <span className="hint" style={{ flex: 1 }}>
            Операция сразу создаст проводку в ГК
          </span>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {create.isPending || post.isPending ? 'Сохранение…' : 'Сохранить'}
          </button>
        </div>
      }
    >
      {/* ───── Направление ───── */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        <button
          type="button"
          onClick={() => setDirection('out')}
          className={'btn btn-sm ' + (direction === 'out' ? 'btn-primary' : 'btn-ghost')}
          style={{ flex: 1 }}
        >
          <Icon name="arrow-right" size={12} /> Расход — деньги ушли
        </button>
        <button
          type="button"
          onClick={() => setDirection('in')}
          className={'btn btn-sm ' + (direction === 'in' ? 'btn-primary' : 'btn-ghost')}
          style={{ flex: 1 }}
        >
          <Icon name="download" size={12} /> Приход — деньги пришли
        </button>
      </div>

      {/* ───── Главное ───── */}
      <SectionLabel>Когда и сколько</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата *</label>
          <input
            className="input"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <span className="hint">Когда {direction === 'out' ? 'списали' : 'получили'} деньги</span>
        </div>

        <div className="field">
          <label>Сумма, UZS *</label>
          <input
            className={'input mono' + (getFieldErr('amount_uzs') ? ' err' : '')}
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
          />
          {getFieldErr('amount_uzs')
            ? <span className="hint" style={{ color: 'var(--danger)' }}>{getFieldErr('amount_uzs')}</span>
            : <span className="hint">Только число, без пробелов</span>}
        </div>
      </div>

      {/* ───── Способ оплаты ───── */}
      <div className="field">
        <label>Способ оплаты *</label>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <MethodChip active={method === 'cash'} onClick={() => setMethod('cash')}>
            Наличные
          </MethodChip>
          <MethodChip active={method === 'bank'} onClick={() => setMethod('bank')}>
            Банк / Карта
          </MethodChip>
          <MethodChip active={method === 'other'} onClick={() => setMethod('other')}>
            Прочее
          </MethodChip>
        </div>
        <span className="hint">
          {method === 'cash' && 'Касса 50.01 проставится автоматически'}
          {method === 'bank' && 'Банковский счёт 51.01 проставится автоматически'}
          {method === 'other' && 'Выберите счёт ниже вручную'}
        </span>

        {method === 'other' && (
          <select
            className="input"
            style={{ marginTop: 6 }}
            value={cashSubId}
            onChange={(e) => setCashSubId(e.target.value)}
          >
            <option value="">— выберите счёт —</option>
            {subaccounts
              ?.filter((s) => s.code.startsWith('50.') || s.code.startsWith('51.'))
              .map((s) => (
                <option key={s.id} value={s.id}>{s.code} · {s.name}</option>
              ))}
          </select>
        )}
      </div>

      {/* ───── На что ───── */}
      <SectionLabel>На что {direction === 'out' ? 'потрачено' : 'получено'}</SectionLabel>

      <div className="field">
        <label>Модуль</label>
        <select className="input" value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
          <option value="">— не привязан —</option>
          {modules?.map((m) => (
            <option key={m.id} value={m.id}>{m.name}</option>
          ))}
        </select>
        <span className="hint">К какому производству относится. Можно пропустить</span>
      </div>

      <div className="field">
        <label>Статья</label>
        <select
          className="input"
          value={articleId}
          onChange={(e) => handleArticleChange(e.target.value)}
        >
          <option value="">— выбрать субсчёт вручную —</option>
          {articleOptions.map((a) => (
            <option key={a.id} value={a.id}>
              {a.code} · {a.name}
              {a.default_subaccount_code ? ` → ${a.default_subaccount_code}` : ''}
            </option>
          ))}
        </select>
        <span className="hint">
          Что именно — напр. «Газ», «Электричество», «Зарплата технолога». Субсчёт подставится сам
        </span>
      </div>

      {/* Субсчёт ГК — скрываем когда выбрана статья (показываем строкой). */}
      {contraIsAutoFromArticle && selectedContra ? (
        <div
          className="field"
          style={{
            background: 'var(--bg-subtle)', borderRadius: 6, padding: '8px 10px',
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
          }}
        >
          <Icon name="check" size={14} />
          <div style={{ flex: 1, fontSize: 12 }}>
            Субсчёт: <b>{selectedContra.code} · {selectedContra.name}</b>
            <div className="hint">Подставлен из статьи</div>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => setEditContra(true)}
          >
            Изменить
          </button>
        </div>
      ) : (
        <div className="field">
          <label>
            Субсчёт ГК *
            {getFieldErr('contra_subaccount') && (
              <span style={{ fontSize: 11, color: 'var(--danger)', marginLeft: 6 }}>
                {getFieldErr('contra_subaccount')}
              </span>
            )}
          </label>
          {quickContras.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
              {quickContras.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => setContraSubId(q.id)}
                  className={'btn btn-sm ' + (contraSubId === q.id ? 'btn-primary' : 'btn-ghost')}
                >
                  {q.label}
                </button>
              ))}
            </div>
          )}
          <select
            className="input"
            value={contraSubId}
            onChange={(e) => setContraSubId(e.target.value)}
          >
            <option value="">— выберите субсчёт —</option>
            {contraOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} · {s.name}
                {s.module_code ? ` · [${s.module_code}]` : ''}
              </option>
            ))}
          </select>
          <span className="hint">
            Куда списываем по плану счетов. Используйте кнопки выше для частых вариантов
          </span>
        </div>
      )}

      {/* ───── Дополнительно ───── */}
      <SectionLabel>Дополнительно</SectionLabel>

      <div className="field">
        <label>Контрагент</label>
        <select className="input" value={counterpartyId} onChange={(e) => setCounterpartyId(e.target.value)}>
          <option value="">— не указан —</option>
          {counterparties?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <span className="hint">
          {direction === 'out' ? 'Кому платим' : 'От кого получили'}. Можно пропустить
        </span>
      </div>

      <div className="field">
        <label>Описание</label>
        <input
          className="input"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Например: Электричество апрель"
        />
        <span className="hint">Заметка для себя — увидите в истории операций</span>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{
          marginTop: 10, padding: 8, background: '#fef2f2',
          color: 'var(--danger)', borderRadius: 6, fontSize: 12,
        }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 700, letterSpacing: '.08em',
      textTransform: 'uppercase', color: 'var(--fg-3)',
      marginTop: 4, marginBottom: 8,
    }}>
      {children}
    </div>
  );
}

function MethodChip({
  active, onClick, children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={'btn btn-sm ' + (active ? 'btn-primary' : 'btn-ghost')}
      style={{ flex: 1, minWidth: 110 }}
    >
      {children}
    </button>
  );
}
