'use client';

import { useState } from 'react';

import Modal from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useCurrenciesSorted } from '@/hooks/useCurrencyRates';
import { useCreatePerson, usePeople, useUpdatePerson } from '@/hooks/usePeople';
import { useCreateRate, useSaveCompensationPlan } from '@/hooks/usePayroll';
import { useHasLevel } from '@/hooks/usePermissions';
import type { MembershipRow } from '@/types/auth';
import type { CompensationType } from '@/types/payroll';

interface Props {
  initial?: MembershipRow | null;
  onClose: () => void;
  onSaved?: (m: MembershipRow) => void;
}

const WORK_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'active',      label: 'Активен' },
  { value: 'vacation',    label: 'Отпуск' },
  { value: 'sick_leave',  label: 'Больничный' },
  { value: 'terminated',  label: 'Уволен' },
];

export default function PersonModal({ initial, onClose, onSaved }: Props) {
  const create = useCreatePerson();
  const update = useUpdatePerson();
  const savePlan = useSaveCompensationPlan();
  const createRate = useCreateRate();
  const { data: currencies = [] } = useCurrenciesSorted();
  const hasLevel = useHasLevel();
  const canSetCompensation = hasLevel('hr', 'rw');

  const saving =
    create.isPending || update.isPending || savePlan.isPending || createRate.isPending;
  const error = (initial ? update.error : create.error) ?? null;
  const isEdit = !!initial;

  const [email, setEmail] = useState(initial?.user_email ?? '');
  const [fullName, setFullName] = useState(initial?.user_full_name ?? '');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [positionTitle, setPositionTitle] = useState(initial?.position_title ?? '');
  const [workPhone, setWorkPhone] = useState(initial?.work_phone ?? '');
  const [workStatus, setWorkStatus] = useState(initial?.work_status ?? 'active');
  const [managerId, setManagerId] = useState<string>(initial?.manager ?? '');

  // Кандидаты в руководители: активные сотрудники текущей org, кроме самого
  // редактируемого (нельзя быть себе руководителем).
  const { data: candidates = [] } = usePeople({ is_active: 'true' });

  // Compensation поля — показываются только при создании и при наличии hr:rw.
  const [compType, setCompType] = useState<CompensationType>('monthly_salary');
  const [initialRate, setInitialRate] = useState('');
  const [rateFrom, setRateFrom] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
  });

  const fieldErrors =
    error instanceof ApiError && error.status === 400
      ? ((error.data as Record<string, string[]>) ?? {})
      : {};

  const handleSave = async () => {
    try {
      if (isEdit && initial) {
        const res = await update.mutateAsync({
          id: initial.id,
          patch: {
            position_title: positionTitle,
            work_phone: workPhone,
            work_status: workStatus,
            manager: managerId || null,
          },
        });
        onSaved?.(res);
      } else {
        const res = await create.mutateAsync({
          email,
          full_name: fullName,
          phone,
          password: password || undefined,
          position_title: positionTitle,
          work_phone: workPhone,
          work_status: workStatus,
          manager: managerId || null,
        });
        // Если у юзера hr:rw — сразу настроим план и (опц.) первую ставку.
        if (canSetCompensation) {
          const uzs = currencies.find((c) => c.code === 'UZS') ?? currencies[0];
          if (uzs) {
            try {
              await savePlan.mutateAsync({
                employee: res.id,
                compensation_type: compType,
                currency: uzs.id,
              });
              const amount = initialRate.replace(/\s/g, '');
              if (amount && Number(amount) > 0) {
                await createRate.mutateAsync({
                  employee: res.id,
                  amount,
                  currency: uzs.id,
                  effective_from: rateFrom,
                  reason: 'hire',
                });
              }
            } catch {
              // Если payroll-операции упали — членство уже создано,
              // юзер донастроит на детальной странице. Не блокируем закрытие.
            }
          }
        }
        onSaved?.(res);
      }
      onClose();
    } catch {
      /* field errors */
    }
  };

  return (
    <Modal
      title={isEdit ? `Сотрудник · ${initial?.user_full_name}` : 'Новый сотрудник'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button
            className="btn btn-primary"
            disabled={saving || (!isEdit && (!email || !fullName))}
            onClick={handleSave}
          >
            {saving ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Добавить'}
          </button>
        </>
      }
    >
      {!isEdit && (
        <>
          <div className="field">
            <label>Email *</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ivanov@example.com"
            />
            {fieldErrors.email && (
              <div style={{ fontSize: 11, color: 'var(--danger)' }}>
                {fieldErrors.email.join(' · ')}
              </div>
            )}
          </div>
          <div className="field">
            <label>ФИО *</label>
            <input
              className="input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
            {fieldErrors.full_name && (
              <div style={{ fontSize: 11, color: 'var(--danger)' }}>
                {fieldErrors.full_name.join(' · ')}
              </div>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="field">
              <label>Телефон</label>
              <input
                className="input"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+998 …"
              />
            </div>
            <div className="field">
              <label>Начальный пароль</label>
              <input
                className="input"
                type="text"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="оставьте пустым — вход заблокирован"
              />
            </div>
          </div>
          <div
            style={{
              fontSize: 11,
              color: 'var(--fg-3)',
              marginBottom: 8,
              padding: 6,
              background: 'var(--bg-soft)',
              borderRadius: 4,
            }}
          >
            Если email уже зарегистрирован в системе — будет использован существующий
            аккаунт (только добавится membership в текущей компании).
          </div>
        </>
      )}

      {isEdit && (
        <div className="field">
          <label>Пользователь</label>
          <input
            className="input"
            value={`${initial?.user_full_name ?? ''} · ${initial?.user_email ?? ''}`}
            disabled
          />
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="field">
          <label>Должность</label>
          <input
            className="input"
            value={positionTitle}
            onChange={(e) => setPositionTitle(e.target.value)}
            placeholder="Технолог"
          />
        </div>
        <div className="field">
          <label>Рабочий телефон</label>
          <input
            className="input"
            value={workPhone}
            onChange={(e) => setWorkPhone(e.target.value)}
          />
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Статус</label>
          <select
            className="input"
            value={workStatus}
            onChange={(e) => setWorkStatus(e.target.value)}
          >
            {WORK_STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ gridColumn: '1/3' }}>
          <label>Руководитель</label>
          <select
            className="input"
            value={managerId}
            onChange={(e) => setManagerId(e.target.value)}
          >
            <option value="">— не назначен —</option>
            {candidates
              .filter((c) => !initial || c.id !== initial.id)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.user_full_name}{c.position_title ? ` · ${c.position_title}` : ''}
                </option>
              ))}
          </select>
          {fieldErrors.manager && (
            <div style={{ fontSize: 11, color: 'var(--danger)' }}>
              {Array.isArray(fieldErrors.manager)
                ? fieldErrors.manager.join(' · ')
                : String(fieldErrors.manager)}
            </div>
          )}
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>
            Руководитель видит этого сотрудника в табе «Мои» на /people и может
            быстро ставить +/− по его ЗП на /payroll/balances.
          </div>
        </div>
      </div>

      {!isEdit && canSetCompensation && (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            background: 'var(--bg-soft)',
            borderRadius: 6,
            display: 'grid',
            gap: 10,
          }}
        >
          <div style={{ fontWeight: 600, fontSize: 13 }}>Зарплата (опционально)</div>
          <div className="field">
            <label>Тип оплаты</label>
            <select
              className="input"
              value={compType}
              onChange={(e) => setCompType(e.target.value as CompensationType)}
            >
              <option value="monthly_salary">Оклад в месяц</option>
              <option value="per_shift">Ставка за смену</option>
              <option value="per_hour">Ставка за час</option>
            </select>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="field">
              <label>Стартовая ставка (UZS)</label>
              <input
                className="input"
                inputMode="decimal"
                value={initialRate}
                onChange={(e) => setInitialRate(e.target.value)}
                placeholder="оставьте пустым — задать позже"
              />
            </div>
            <div className="field">
              <label>С даты</label>
              <input
                className="input"
                type="date"
                value={rateFrom}
                onChange={(e) => setRateFrom(e.target.value)}
              />
            </div>
          </div>
        </div>
      )}

      {error && error.status !== 400 && (
        <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 12 }}>
          Ошибка: {error.message}
        </div>
      )}
    </Modal>
  );
}
