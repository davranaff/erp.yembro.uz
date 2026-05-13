'use client';

import { useEffect, useMemo, useState } from 'react';

import AmountInput from '@/components/ui/AmountInput';
import Icon from '@/components/ui/Icon';
import Modal from '@/components/ui/Modal';
import SmartSelect from '@/components/ui/SmartSelect';
import { useCounterparties } from '@/hooks/useCounterparties';
import { expenseArticlesCrud } from '@/hooks/useExpenseArticles';
import { useModules } from '@/hooks/useModules';
import { paymentsCrud, usePostPayment } from '@/hooks/usePayments';
import { useHasLevel, usePermissions } from '@/hooks/usePermissions';
import { useSubaccounts } from '@/hooks/useAccounts';
import { ApiError } from '@/lib/api';
import { LEVEL_ORDER, type ExpenseArticle, type ModuleLevel } from '@/types/auth';

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
  /**
   * Жёстко привязать форму к конкретной кассе (UUID GLSubaccount). Когда
   * передан — поле «Касса/счёт» становится readonly, и операция гарантированно
   * пойдёт по этой кассе. Используется при открытии модалки из карточки
   * /finance/cashbox/[id] — там нет смысла давать менять кассу.
   */
  cashSubaccountId?: string;
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

/**
 * Channel вычисляется по коду выбранного субсчёта, не указывается отдельно.
 * 50.NN — наличные, 51.NN — банк/перечисление. Остальные коды (если кому-то
 * понадобится платёж не из 50/51) — 'other'.
 */
function deriveChannel(code: string | undefined): 'cash' | 'transfer' | 'other' {
  if (!code) return 'other';
  if (code.startsWith('50.')) return 'cash';
  if (code.startsWith('51.')) return 'transfer';
  return 'other';
}

export default function OpexModal({ preselect, onClose }: Props) {
  const create = paymentsCrud.useCreate();
  const post = usePostPayment();

  const { data: modules } = useModules();
  const { data: subaccounts } = useSubaccounts();
  const { data: counterparties } = useCounterparties();
  const { data: articles } = expenseArticlesCrud.useList({ is_active: 'true' });
  const hasLevel = useHasLevel();
  const permissions = usePermissions();
  const isOrgAdmin = hasLevel('admin', 'admin') || hasLevel('ledger', 'admin');

  const [direction, setDirection] = useState<'out' | 'in'>(preselect?.direction ?? 'out');
  const [kind, setKind] = useState<'opex' | 'income' | 'salary'>(
    KIND_FOR_DIRECTION[preselect?.direction ?? 'out'],
  );
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [amount, setAmount] = useState('');
  const [cashSubId, setCashSubId] = useState(preselect?.cashSubaccountId ?? '');
  // Если кассу прислали через preselect — поле кассы readonly, чтобы юзер
  // открывший форму со страницы конкретной кассы случайно не зачислил/списал
  // с другой.
  const cashLocked = Boolean(preselect?.cashSubaccountId);
  const [contraSubId, setContraSubId] = useState('');
  const [articleId, setArticleId] = useState('');
  const [moduleId, setModuleId] = useState('');
  // Касса у нас уже привязана к модулю (s.module). По умолчанию подставляем
  // модуль из выбранной кассы, чтобы оператор не выбирал одно и то же дважды.
  // Если юзер вручную поменял модуль — больше не перезаписываем при смене
  // кассы (он явно знает, что делает: например, тратит из feed-кассы, но
  // расход относит на vet).
  const [moduleManuallySet, setModuleManuallySet] = useState(false);
  const [counterpartyId, setCounterpartyId] = useState('');
  const [notes, setNotes] = useState('');
  // Раскрыть «бухгалтерскую» секцию (выбор субсчёта вручную). Обычный
  // пользователь её не видит — статья сама подставляет правильный субсчёт.
  // Раскрытие нужно только если статьи нет, или для корректировки.
  const [showAdvanced, setShowAdvanced] = useState(false);
  // Inline-создание новой статьи прямо из дропдауна — кейс «у нас нет
  // статьи "Обед", надо добавить» без ухода в /settings.
  const [creatingArticle, setCreatingArticle] = useState(false);
  const [newArticleName, setNewArticleName] = useState('');
  const [newArticleSubId, setNewArticleSubId] = useState('');
  const createArticle = expenseArticlesCrud.useCreate();

  // ── Доступные модули юзера ────────────────────────────────────────
  // Бухгалтер (ledger:admin) и org-admin видят все кассы; head feed —
  // только свои. Без этого head feed мог зачислить расход на vet-кассу
  // что нарушает изоляцию финансов между модулями.
  const accessibleModuleIds = useMemo<Set<string> | null>(() => {
    if (isOrgAdmin) return null;
    if (!modules) return new Set();
    const allowedCodes = new Set(
      Object.entries(permissions)
        .filter(([, lvl]) => LEVEL_ORDER[lvl as ModuleLevel] >= LEVEL_ORDER.rw)
        .map(([code]) => code),
    );
    return new Set(
      modules.filter((m) => allowedCodes.has(m.code)).map((m) => m.id),
    );
  }, [isOrgAdmin, modules, permissions]);

  // Кассы доступные текущему юзеру: 50.NN и 51.NN, + RBAC фильтр.
  // Если юзер видит ровно одну кассу — авто-выбираем её, чтобы не
  // заставлять кликать.
  const cashOptions = useMemo(() => {
    if (!subaccounts) return [];
    return subaccounts
      .filter((s) => s.code.startsWith('50.') || s.code.startsWith('51.'))
      .filter((s) => {
        if (accessibleModuleIds === null) return true;
        if (!s.module) return false; // null-module («общая» 50.01) — только админ
        return accessibleModuleIds.has(s.module);
      })
      .sort((a, b) => a.code.localeCompare(b.code));
  }, [subaccounts, accessibleModuleIds]);

  // Авто-выбор если ровно одна доступная касса.
  useEffect(() => {
    if (cashLocked) return; // preselect.cashSubaccountId — не переопределяем
    if (!cashSubId && cashOptions.length === 1) {
      setCashSubId(cashOptions[0].id);
    }
    // Если выбранная касса больше не в списке (юзер сменил модуль или
    // у неё пропал доступ) — сбрасываем.
    if (cashSubId && !cashOptions.some((s) => s.id === cashSubId)) {
      setCashSubId('');
    }
  }, [cashOptions, cashSubId, cashLocked]);

  // Preselect модуль по коду
  useEffect(() => {
    if (preselect?.moduleCode && modules && !moduleId) {
      const m = modules.find((x) => x.code === preselect.moduleCode);
      if (m) setModuleId(m.id);
    }
  }, [preselect, modules, moduleId]);

  // Авто-подстановка модуля из выбранной кассы. Не трогаем, если юзер
  // уже вручную выбрал модуль (см. moduleManuallySet).
  useEffect(() => {
    if (moduleManuallySet) return;
    if (!cashSubId || !subaccounts) return;
    const cashbox = subaccounts.find((s) => s.id === cashSubId);
    if (cashbox?.module) {
      setModuleId(cashbox.module);
    }
  }, [cashSubId, subaccounts, moduleManuallySet]);

  // (старая логика «method → 50.01/51.01» удалена — теперь юзер
  // выбирает кассу явно из своего отфильтрованного списка)

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

  // Дефолтный субсчёт для новой статьи: если direction=out → берём первый
  // частый расходный (НЗП модуля если есть, иначе 91.02 «Прочие расходы»).
  // Для income → 91.01.
  const defaultNewArticleSub = useMemo(() => {
    if (!subaccounts) return '';
    if (direction === 'out') {
      // Сначала НЗП модуля, потом «прочие расходы»
      if (nzpCodeForModule) {
        const s = subaccounts.find((x) => x.code === nzpCodeForModule);
        if (s) return s.id;
      }
      const other = subaccounts.find((x) => x.code === '91.02');
      return other?.id ?? '';
    }
    const inc = subaccounts.find((x) => x.code === '91.01');
    return inc?.id ?? '';
  }, [subaccounts, direction, nzpCodeForModule]);

  const openCreateArticle = () => {
    setCreatingArticle(true);
    setNewArticleName('');
    setNewArticleSubId(defaultNewArticleSub);
  };

  const submitNewArticle = async () => {
    const name = newArticleName.trim();
    if (!name) {
      alert('Введите название категории (например «Обед»).');
      return;
    }
    // Если оператор не выбрал субсчёт (или это не админ — у него вообще
    // нет дропдауна) — auto-fallback на «Прочие». Так оператор не страдает
    // бухгалтерией: создал «Обед» → попало в 91.02. Админ потом может
    // переразнести на правильный субсчёт через /settings → Категории.
    let subId = newArticleSubId;
    if (!subId && subaccounts) {
      const fallbackCode = direction === 'out' ? '91.02' : '91.01';
      const fallback = subaccounts.find((s) => s.code === fallbackCode);
      if (fallback) {
        subId = fallback.id;
      }
    }
    if (!subId) {
      alert('Не удалось определить субсчёт по умолчанию. Попросите админа.');
      return;
    }
    // code: автогенерим из name (cyrillic→translit базовый, обрезаем до 16).
    // Бекенд требует unique, добавим суффикс через timestamp если коллизия.
    const codeBase = name
      .toUpperCase()
      .replace(/[^A-ZА-ЯЁ0-9]+/gu, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 16) || 'KATEGORIYA';
    const code = `${codeBase}_${Date.now().toString().slice(-4)}`;
    try {
      const created = await createArticle.mutateAsync({
        code,
        name,
        kind: direction === 'out' ? 'expense' : 'income',
        default_subaccount: subId,
        default_module: moduleId || null,
      });
      if (created?.id) {
        setArticleId(created.id);
        setContraSubId(subId);
      }
      setCreatingArticle(false);
    } catch (e) {
      const msg = e instanceof ApiError ? (e.message || 'Ошибка') : 'Ошибка';
      alert(`Не удалось создать категорию: ${msg}`);
    }
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
    const selectedCash = cashOptions.find((s) => s.id === cashSubId);
    try {
      const created = await create.mutateAsync({
        date,
        module: moduleId || null,
        direction,
        channel: deriveChannel(selectedCash?.code),
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
          <AmountInput
            className={'input mono' + (getFieldErr('amount_uzs') ? ' err' : '')}
            value={amount}
            onChange={setAmount}
            placeholder="0"
          />
          {getFieldErr('amount_uzs')
            ? <span className="hint" style={{ color: 'var(--danger)' }}>{getFieldErr('amount_uzs')}</span>
            : <span className="hint">Например: 1 000 000</span>}
        </div>
      </div>

      {/* ───── Касса/счёт ───── */}
      <div className="field">
        <label>Касса / счёт *</label>
        {cashLocked ? (
          // Жёстко зафиксирована (открыто со страницы конкретной кассы).
          // Показываем только бейдж — без возможности смены, иначе юзер
          // случайно перенесёт операцию на чужую кассу.
          (() => {
            const s = subaccounts?.find((x) => x.id === cashSubId);
            if (!s) {
              return (
                <div style={{
                  padding: 8, fontSize: 12,
                  background: 'var(--bg-soft)', borderRadius: 6,
                }}>
                  Загрузка кассы…
                </div>
              );
            }
            const isCash = s.code.startsWith('50.');
            return (
              <div style={{
                padding: '8px 10px', fontSize: 13,
                background: 'var(--bg-soft)',
                border: '1px solid var(--border)', borderRadius: 6,
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span>{isCash ? '💵' : '🏦'}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500 }}>{s.name}</div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--fg-3)' }}>
                    {s.code}{s.module_code ? ` · ${s.module_code}` : ''}
                  </div>
                </div>
              </div>
            );
          })()
        ) : cashOptions.length === 0 ? (
          <div style={{
            padding: 8, fontSize: 12, color: 'var(--danger)',
            background: 'var(--danger-soft, #FEF2F2)',
            border: '1px solid var(--danger)', borderRadius: 6,
          }}>
            У вас нет доступных касс/счетов. Попросите администратора
            создать кассу для вашего модуля в /finance/cashbox.
          </div>
        ) : (
          <SmartSelect
            value={cashSubId}
            onChange={setCashSubId}
            options={cashOptions.map((s) => {
              const isCash = s.code.startsWith('50.');
              return {
                value: s.id,
                label: `${isCash ? '💵 ' : '🏦 '}${s.name}`,
                sublabel: s.module_code ?? s.code,
              };
            })}
            placeholder="— выберите кассу —"
            searchPlaceholder="Поиск кассы/банка…"
            emptyText="Касс/счетов нет"
          />
        )}
        <span className="hint">
          {cashLocked
            ? 'Операция жёстко привязана к этой кассе.'
            : direction === 'out'
              ? 'Откуда списываются деньги. Видите только свои кассы (по модулям где у вас rw).'
              : 'Куда зачисляются деньги. Видите только свои кассы.'}
        </span>
      </div>

      {/* ───── На что ───── */}
      <SectionLabel>На что {direction === 'out' ? 'потрачено' : 'получено'}</SectionLabel>

      <div className="field">
        <label>Модуль</label>
        <select
          className="input"
          value={moduleId}
          onChange={(e) => {
            setModuleId(e.target.value);
            setModuleManuallySet(true);
          }}
        >
          <option value="">— не привязан —</option>
          {modules?.map((m) => (
            <option key={m.id} value={m.id}>{m.name}</option>
          ))}
        </select>
        <span className="hint">
          Подставляется из кассы автоматически. Меняйте только если расход/приход
          реально относится к другому производству.
        </span>
      </div>

      <div className="field">
        <label>Категория *</label>
        {!creatingArticle ? (
          <>
            <select
              className="input"
              value={articleId}
              onChange={(e) => {
                if (e.target.value === '__create__') {
                  openCreateArticle();
                } else {
                  handleArticleChange(e.target.value);
                }
              }}
            >
              <option value="">— выберите —</option>
              <option value="__create__" style={{ fontWeight: 600, color: 'var(--brand-orange)' }}>
                ＋ Создать новую категорию…
              </option>
              {articleOptions.length > 0 && (
                <option disabled>──────────</option>
              )}
              {articleOptions.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
            <span className="hint">
              Например «Обед», «Канцтовары», «Премия», «Бензин».
              Полный CRUD категорий — в /settings → «Категории расходов».
            </span>
          </>
        ) : (
          // ─── Inline-форма создания категории ──────────────────────
          // Оператор видит только название. GL-субсчёт назначается
          // автоматически («Прочие расходы» 91.02 для расходов,
          // «Прочие доходы» 91.01 для доходов). Бухгалтер позже может
          // переразнести в /settings → Категории если нужна точность.
          <div style={{
            padding: 12, marginTop: 4,
            background: 'var(--bg-soft)',
            border: '1px solid var(--brand-orange)',
            borderRadius: 6,
          }}>
            <div style={{
              fontSize: 11, fontWeight: 700, color: 'var(--brand-orange)',
              textTransform: 'uppercase', letterSpacing: '.04em',
              marginBottom: 8,
            }}>
              Новая категория {direction === 'out' ? 'расхода' : 'дохода'}
            </div>
            <div className="field" style={{ marginBottom: 8 }}>
              <label style={{ fontSize: 12 }}>Название *</label>
              <input
                className="input"
                autoFocus
                value={newArticleName}
                onChange={(e) => setNewArticleName(e.target.value)}
                placeholder="Обед / Канцтовары / Премия"
              />
            </div>
            {isOrgAdmin && (
              <div className="field" style={{ marginBottom: 8 }}>
                <label style={{ fontSize: 12 }}>
                  Бухгалтерский субсчёт{' '}
                  <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
                    (для админа · можно пропустить)
                  </span>
                </label>
                <select
                  className="input"
                  value={newArticleSubId}
                  onChange={(e) => setNewArticleSubId(e.target.value)}
                >
                  <option value="">— по умолчанию (Прочие) —</option>
                  {contraOptions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                      {s.module_code ? ` · ${s.module_code}` : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 8 }}>
              {isOrgAdmin
                ? 'Если не выберете субсчёт — будет привязка к «Прочие расходы/доходы».'
                : 'Категория попадёт в «Прочие расходы» в отчётности. Если нужна '
                  + 'точная бухгалтерская группировка — попросите админа настроить '
                  + 'в /settings → Категории.'}
            </div>
            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setCreatingArticle(false)}
                disabled={createArticle.isPending}
              >
                Отмена
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={submitNewArticle}
                disabled={createArticle.isPending || !newArticleName.trim()}
              >
                {createArticle.isPending ? 'Создание…' : 'Создать и выбрать'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Подтверждение что субсчёт подставился из статьи. Не дропдаун
          с кодами — просто строка для прозрачности. */}
      {/* Подтверждение subaccount — теперь видно ТОЛЬКО админу. Оператору
          бухгалтерская подкладка не нужна и только запутывает. */}
      {isOrgAdmin && articleId && selectedContra && !showAdvanced && (
        <div
          className="field"
          style={{
            background: 'var(--bg-soft)', borderRadius: 6, padding: '8px 10px',
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
            fontSize: 12,
          }}
        >
          <Icon name="check" size={14} />
          <div style={{ flex: 1 }}>
            Субсчёт: <b>{selectedContra.name}</b>
            <span style={{ color: 'var(--fg-3)', marginLeft: 6, fontSize: 11 }}>
              {selectedContra.code}
            </span>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => setShowAdvanced(true)}
          >
            Изменить
          </button>
        </div>
      )}

      {/* Ручной выбор субсчёта — только для админа и ТОЛЬКО при явном
          раскрытии. Раньше показывалась когда нет articleId — это
          путало даже админа при первом открытии формы (форма пустая,
          ничего не выбрано → выскакивала бухгалтерская секция).
          Теперь: открывается только если admin кликнул «⚙ Указать
          вручную» (showAdvanced=true). Базовый флоу — через «Категория». */}
      {isOrgAdmin && showAdvanced && (
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
                  {q.label.replace(/^\d+\.\d+\s·\s/, '')}
                </button>
              ))}
            </div>
          )}
          <SmartSelect
            value={contraSubId}
            onChange={setContraSubId}
            options={contraOptions.map((s) => ({
              value: s.id,
              label: s.name,
              sublabel: s.module_code ?? s.code,
            }))}
            placeholder="— выберите субсчёт —"
            searchPlaceholder="Поиск по плану счетов…"
            emptyText="Субсчетов нет"
          />
          <span className="hint">
            Бухгалтерский план счетов. Если не уверены — выберите «Категория» выше.
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => { setShowAdvanced(false); setContraSubId(''); }}
            style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}
          >
            ← Свернуть и пользоваться категориями
          </button>
        </div>
      )}

      {/* Ссылка «указать субсчёт вручную» — только админу и только когда
          секция не раскрыта. Оператор её не видит, ему достаточно
          «Категория». */}
      {isOrgAdmin && !showAdvanced && (
        <div style={{ marginBottom: 8 }}>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowAdvanced(true)}
            style={{ fontSize: 11, color: 'var(--fg-3)' }}
          >
            ⚙ Указать субсчёт вручную (для бухгалтерии)
          </button>
        </div>
      )}

      {/* ───── Дополнительно ───── */}
      <SectionLabel>Дополнительно</SectionLabel>

      <div className="field">
        <label>Контрагент</label>
        <SmartSelect
          value={counterpartyId}
          onChange={setCounterpartyId}
          options={counterparties?.map((c) => ({
            value: c.id,
            label: c.name,
            sublabel: c.code,
          })) ?? []}
          placeholder="— не указан —"
          searchPlaceholder="Поиск по названию или коду…"
          emptyText="Контрагенты не найдены"
        />
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

