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

/**
 * Маппинг модуль → субсчёт НЗП по умолчанию (для быстрой кнопки
 * «На НЗП модуля» в форме OPEX).
 */
const MODULE_NZP: Record<string, string> = {
  matochnik: '20.01',
  feedlot: '20.02',
  incubation: '20.03',
  slaughter: '20.04',
  feed: '20.05',
  vet: '20.06',
};

export default function OpexModal({ preselect, onClose }: Props) {
  const create = paymentsCrud.useCreate();
  const post = usePostPayment();

  const { data: modules } = useModules();
  const { data: subaccounts } = useSubaccounts();
  const { data: counterparties } = useCounterparties();
  const { data: articles } = expenseArticlesCrud.useList({ is_active: 'true' });

  // Направление
  const [direction, setDirection] = useState<'out' | 'in'>(
    preselect?.direction ?? 'out',
  );
  // Вид операции
  const [kind, setKind] = useState<'opex' | 'income' | 'salary'>(
    KIND_FOR_DIRECTION[preselect?.direction ?? 'out'],
  );
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [channel, setChannel] = useState<'cash' | 'transfer' | 'click' | 'other'>('cash');
  const [amount, setAmount] = useState('');
  const [cashSubId, setCashSubId] = useState('');
  const [contraSubId, setContraSubId] = useState('');
  const [articleId, setArticleId] = useState('');
  const [moduleId, setModuleId] = useState('');
  const [counterpartyId, setCounterpartyId] = useState('');
  const [notes, setNotes] = useState('');

  // Preselect модуль по коду
  useEffect(() => {
    if (preselect?.moduleCode && modules && !moduleId) {
      const m = modules.find((x) => x.code === preselect.moduleCode);
      if (m) setModuleId(m.id);
    }
  }, [preselect, modules, moduleId]);

  // Авто-выбор кассы (50.01) при первой загрузке субсчётов
  useEffect(() => {
    if (!cashSubId && subaccounts && subaccounts.length > 0) {
      const def = subaccounts.find((s) => s.code === '50.01');
      if (def) setCashSubId(def.id);
    }
  }, [subaccounts, cashSubId]);

  // Каналы → касса/банк
  useEffect(() => {
    if (!subaccounts || subaccounts.length === 0) return;
    const want = channel === 'cash' ? '50.01' : '51.01';
    const target = subaccounts.find((s) => s.code === want);
    if (target && target.id !== cashSubId) setCashSubId(target.id);
  }, [channel, subaccounts]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Preselect contra (если передан suggestedContraCode)
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

  // Когда меняется direction — пересчитываем kind
  useEffect(() => {
    setKind(KIND_FOR_DIRECTION[direction]);
  }, [direction]);

  // Активный модуль (для быстрых кнопок)
  const activeModuleCode = useMemo(
    () => modules?.find((m) => m.id === moduleId)?.code,
    [modules, moduleId],
  );
  const nzpCodeForModule = activeModuleCode ? MODULE_NZP[activeModuleCode] : undefined;

  // Статьи, подходящие к текущему направлению.
  // out → expense + salary; in → income + transfer.
  const articleOptions = useMemo<ExpenseArticle[]>(() => {
    if (!articles) return [];
    const allowed = direction === 'out'
      ? new Set(['expense', 'salary'])
      : new Set(['income', 'transfer']);
    return articles
      .filter((a) => a.is_active && allowed.has(a.kind))
      .sort((a, b) => a.code.localeCompare(b.code));
  }, [articles, direction]);

  // Автоподстановка subaccount + kind при выборе статьи
  const handleArticleChange = (id: string) => {
    setArticleId(id);
    if (!id) return;
    const a = articles?.find((x) => x.id === id);
    if (!a) return;
    if (a.default_subaccount && a.default_subaccount !== contraSubId) {
      setContraSubId(a.default_subaccount);
    }
    if (a.default_module && !moduleId) {
      setModuleId(a.default_module);
    }
    // подсказка по kind: salary → kind=salary
    if (a.kind === 'salary') setKind('salary');
    else if (direction === 'out') setKind('opex');
    else setKind('income');
  };

  // Сгруппированные субсчёта для dropdown'a «Статья»
  const contraOptions = useMemo(() => {
    if (!subaccounts) return [];
    // Исключаем кассу/банк/AP/AR — они не контр-счёт для OPEX
    const excluded = new Set(['50.01', '51.01', '60.01', '60.02', '62.01', '62.02']);
    return subaccounts.filter((s) => !excluded.has(s.code));
  }, [subaccounts]);

  // Быстрые кнопки: НЗП модуля, 26.01 общехоз, 70 ЗП, 91.01/91.02
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
        channel,
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

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {create.isPending || post.isPending ? 'Сохранение…' : 'Сохранить и провести'}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: 'var(--fg-3)', marginBottom: 12 }}>
        Операция проводится сразу. Создаётся <b>проводка в ГК</b>:
        {' '}{direction === 'out' ? 'Дт статья / Кт касса-банк' : 'Дт касса-банк / Кт статья'}.
      </div>

      {/* Направление (сегменты) */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        <button
          type="button"
          onClick={() => setDirection('out')}
          className={'btn btn-sm ' + (direction === 'out' ? 'btn-primary' : 'btn-ghost')}
          style={{ flex: 1 }}
        >
          <Icon name="arrow-right" size={12} /> Расход
        </button>
        <button
          type="button"
          onClick={() => setDirection('in')}
          className={'btn btn-sm ' + (direction === 'in' ? 'btn-primary' : 'btn-ghost')}
          style={{ flex: 1 }}
        >
          <Icon name="download" size={12} /> Приход
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Дата *</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        <div className="field">
          <label>Сумма, UZS *</label>
          <input
            className="input mono"
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
          />
          {getFieldErr('amount_uzs') && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>{getFieldErr('amount_uzs')}</div>
          )}
        </div>

        <div className="field">
          <label>Канал *</label>
          <select className="input" value={channel} onChange={(e) => setChannel(e.target.value as typeof channel)}>
            <option value="cash">Наличные (касса 50.01)</option>
            <option value="transfer">Перечисление (банк 51.01)</option>
            <option value="click">Click (банк 51.01)</option>
            <option value="other">Прочее</option>
          </select>
        </div>

        <div className="field">
          <label>Счёт (касса/банк) *</label>
          <select className="input" value={cashSubId} onChange={(e) => setCashSubId(e.target.value)}>
            <option value="">—</option>
            {subaccounts
              ?.filter((s) => s.code.startsWith('50.') || s.code.startsWith('51.'))
              .map((s) => (
                <option key={s.id} value={s.id}>{s.code} · {s.name}</option>
              ))}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label>Модуль (опционально)</label>
          <select className="input" value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
            <option value="">— не привязан —</option>
            {modules?.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>Статья (аналитика)</span>
            <span style={{ fontSize: 10, color: 'var(--fg-3)', fontWeight: 400 }}>
              напр. «Газ», «Электричество», «Зарплата технолога»
            </span>
          </label>
          <select
            className="input"
            value={articleId}
            onChange={(e) => handleArticleChange(e.target.value)}
          >
            <option value="">— без статьи (только субсчёт) —</option>
            {articleOptions.map((a) => (
              <option key={a.id} value={a.id}>
                {a.code} · {a.name}
                {a.default_subaccount_code ? ` → ${a.default_subaccount_code}` : ''}
              </option>
            ))}
          </select>
          {articleId && (
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
              Субсчёт ниже подставлен автоматически из статьи. Можно переопределить.
            </div>
          )}
        </div>

        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label>
            Субсчёт ГК (счёт расхода/дохода) *
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
          <select className="input" value={contraSubId} onChange={(e) => setContraSubId(e.target.value)}>
            <option value="">— выберите статью —</option>
            {contraOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} · {s.name}
                {s.module_code ? ` · [${s.module_code}]` : ''}
              </option>
            ))}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label>Контрагент (опционально)</label>
          <select className="input" value={counterpartyId} onChange={(e) => setCounterpartyId(e.target.value)}>
            <option value="">— не указан —</option>
            {counterparties?.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div className="field" style={{ gridColumn: '1 / 3' }}>
          <label>Описание</label>
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)}
                 placeholder="Например: Электричество апрель" />
        </div>
      </div>

      {error instanceof ApiError && error.status !== 400 && (
        <div style={{ marginTop: 10, padding: 8, background: '#fef2f2', color: 'var(--danger)', borderRadius: 6, fontSize: 12 }}>
          {error.message}
        </div>
      )}
    </Modal>
  );
}
