'use client';

import { useState } from 'react';

import Icon from '@/components/ui/Icon';
import { apiFetch } from '@/lib/api';

export default function DemoForm() {
  const [name, setName] = useState('');
  const [contact, setContact] = useState('');
  const [company, setCompany] = useState('');
  // Honeypot — невидимое поле, реальный пользователь его не заполнит.
  // Боты-автозаполнители часто хватают любой текстовый input → попадают.
  const [website, setWebsite] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (submitted) {
    return (
      <div className="lp-success-card">
        <div className="lp-success-icon">
          <Icon name="check" size={28} />
        </div>
        <div className="lp-success-title">Заявка принята!</div>
        <p className="lp-success-sub">
          Спасибо, {name}. Мы свяжемся с вами в&nbsp;ближайшее время.
        </p>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !contact.trim()) {
      setError('Пожалуйста, заполните имя и контакт.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await apiFetch('/api/landing/demo/', {
        method: 'POST',
        body: {
          name: name.trim(),
          contact: contact.trim(),
          company: company.trim(),
          website,  // honeypot — обычно пусто, бот заполнит → backend отбросит
        },
        skipAuth: true,
        skipOrg: true,
      });
      setSubmitted(true);
    } catch {
      setError('Не удалось отправить заявку. Попробуйте позже или напишите нам напрямую.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="lp-form-card">
      <div className="lp-form-title">Запросить демо</div>
      <p className="lp-form-sub">
        Оставьте контакты — покажем систему и ответим на все вопросы.
      </p>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label className="label">Имя *</label>
          <input
            className="input"
            type="text"
            placeholder="Иван Иванов"
            value={name}
            onChange={e => setName(e.target.value)}
            required
          />
        </div>
        <div className="field" style={{ marginTop: 14 }}>
          <label className="label">Телефон или Email *</label>
          <input
            className="input"
            type="text"
            placeholder="+998 99 000-00-00 или ivan@farm.uz"
            value={contact}
            onChange={e => setContact(e.target.value)}
            required
          />
        </div>
        <div className="field" style={{ marginTop: 14 }}>
          <label className="label">Название хозяйства / компании</label>
          <input
            className="input"
            type="text"
            placeholder="ООО «Птицефабрика Восток»"
            value={company}
            onChange={e => setCompany(e.target.value)}
          />
        </div>

        {/* Honeypot: невидимо для людей, заполняется только ботами.
            Если поле пришло непустым — backend тихо отбрасывает заявку. */}
        <div
          aria-hidden="true"
          style={{
            position: 'absolute',
            left: -9999,
            width: 1,
            height: 1,
            overflow: 'hidden',
          }}
        >
          <label>
            Не заполняйте это поле:
            <input
              type="text"
              name="website"
              tabIndex={-1}
              autoComplete="off"
              value={website}
              onChange={e => setWebsite(e.target.value)}
            />
          </label>
        </div>

        {error && <div className="lp-form-error">{error}</div>}
        <button
          type="submit"
          className="btn btn-primary lp-form-submit"
          disabled={submitting}
          style={{ marginTop: 20 }}
        >
          {submitting ? 'Отправка…' : 'Отправить заявку →'}
        </button>
      </form>
    </div>
  );
}
