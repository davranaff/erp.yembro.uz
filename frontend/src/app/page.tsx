import type { Metadata } from 'next';
import Script from 'next/script';

import Icon from '@/components/ui/Icon';

import DemoForm from './_landing/DemoForm';
import NavClient from './_landing/NavClient';

export const metadata: Metadata = {
  title: 'YemBro ERP — Система управления птицефермой',
  description:
    'YemBro ERP — полный цикл управления птицеводческим предприятием. Маточник, инкубация, откорм, убойня, финансы, склад и Telegram-уведомления в одной системе.',
  keywords: [
    'ERP птицефабрика',
    'система управления птицеводством',
    'учёт птицефабрики',
    'программа для птицефермы',
    'маточник инкубация откорм ERP',
    'YemBro',
  ],
  authors: [{ name: 'YemBro' }],
  robots: { index: true, follow: true },
  openGraph: {
    title: 'YemBro ERP — Управляйте птицефермой. Всё в одном месте.',
    description:
      'От родительского стада до прилавка — маточник, инкубация, откорм, убойня, финансы и Telegram-уведомления в единой системе.',
    type: 'website',
    locale: 'ru_RU',
    siteName: 'YemBro ERP',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'YemBro ERP — Система управления птицефермой',
    description: 'Полный цикл птицефабрики в одной ERP-системе.',
  },
};

const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'YemBro ERP',
  applicationCategory: 'BusinessApplication',
  operatingSystem: 'Web',
  description:
    'ERP-система для управления птицеводческим предприятием: маточник, инкубация, откорм, убойня, финансы, Telegram-уведомления.',
  offers: { '@type': 'Offer', availability: 'https://schema.org/InStock' },
};

function Logo({ light = false }: { light?: boolean }) {
  const textColor = light ? '#FFFDF7' : '#2A1F0E';
  return (
    <svg height="30" viewBox="0 0 148 30" fill="none" aria-label="YemBro ERP">
      <circle cx="15" cy="15" r="13" fill="#E8751A" />
      <text x="9.5" y="21" fill="white" fontSize="14" fontWeight="700" fontFamily="sans-serif">Y</text>
      <text x="36" y="21" fill={textColor} fontSize="16" fontWeight="700" fontFamily="sans-serif">YemBro ERP</text>
    </svg>
  );
}

const FEATURES = [
  { icon: 'egg',       title: 'Маточник',          desc: 'Управление родительским стадом, яйцекладка, кормление и ветеринарные обработки.' },
  { icon: 'incubator', title: 'Инкубация',          desc: 'Режимы инкубации, мираж, вывод суточного цыплёнка и учёт отходов.' },
  { icon: 'factory',   title: 'Фабрика откорма',    desc: 'Партии бройлеров, взвешивания, конверсия корма и среднесуточный прирост.' },
  { icon: 'building',  title: 'Убойня',             desc: 'Смены убоя, выходы тушки по категориям, лабораторные тесты.' },
  { icon: 'bag',       title: 'Корма',              desc: 'Рецептура и замесы, расход по корпусам, себестоимость рациона.' },
  { icon: 'chart',     title: 'Отчёты',             desc: 'P&L, кэш-флоу, оборотная ведомость и полная трассировка партий.' },
  { icon: 'box',       title: 'Telegram-бот',       desc: 'Push-уведомления о закупках и платежах с учётом ролей каждого сотрудника.' },
  { icon: 'users',     title: 'Роли и права',       desc: 'Гибкое RBAC: от смотрителя до администратора, журнал аудита, холдинг.' },
] as const;

const STEPS = [
  {
    num: '01',
    title: 'Регистрируете организацию',
    desc: 'Создаёте организацию, добавляете сотрудников и назначаете роли. Настройка занимает несколько минут.',
  },
  {
    num: '02',
    title: 'Подключаете модули',
    desc: 'Включаете нужные участки: маточник, инкубация, откорм, убойня, корма, финансы. Всё готово к работе.',
  },
  {
    num: '03',
    title: 'Работаете и получаете отчёты',
    desc: 'Вводите данные на каждом участке — система считает показатели, строит отчёты и шлёт уведомления в Telegram.',
  },
] as const;

const WHY = [
  {
    icon: 'chart' as const,
    tone: 'orange' as const,
    tag: 'Прозрачность',
    title: 'Полный контроль над каждым участком',
    desc: 'Все данные связаны: вес партии из откорма автоматически попадает в отчёт убойни. Никаких ручных сводок в Excel.',
  },
  {
    icon: 'box' as const,
    tone: 'yellow' as const,
    tag: 'Telegram-уведомления',
    title: 'Нужная информация — нужным людям',
    desc: 'Настраивайте кто и какие уведомления получает. Бухгалтер видит платежи, зоотехник — взвешивания, директор — сводку.',
  },
  {
    icon: 'settings' as const,
    tone: 'green' as const,
    tag: 'Гибкость',
    title: 'Настраивается под ваше хозяйство',
    desc: 'Маленькая ферма или холдинг из нескольких площадок — RBAC и многоорганизационная структура подойдут для любого масштаба.',
  },
] as const;

const STATS = [
  { value: '13',   label: 'Модулей в системе' },
  { value: '100%', label: 'Цикл птицефабрики' },
  { value: '24/7', label: 'Telegram-уведомления' },
  { value: 'RBAC', label: 'Управление правами' },
];

const ANIM_DELAYS = ['lp-anim-d1', 'lp-anim-d2', 'lp-anim-d3', 'lp-anim-d4', 'lp-anim-d5'] as const;

export default function LandingPage() {
  return (
    <>
      <Script
        id="ld-json"
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div>
        {/* ── Nav ── */}
        <NavClient logo={<Logo />} />

        {/* ── Hero ── */}
        <section className="lp-hero" aria-label="Главный экран">
          <div className="lp-hero-orb" aria-hidden="true" />
          <div className="lp-hero-inner">
            <div className={`lp-eyebrow lp-anim ${ANIM_DELAYS[0]}`}>
              <span className="lp-eyebrow-dot" aria-hidden="true" />
              ERP для птицеводческого предприятия
            </div>
            <h1 className={`lp-headline lp-anim ${ANIM_DELAYS[1]}`}>
              Управляйте птицефермой.<br />
              <em>Всё в одном месте.</em>
            </h1>
            <p className={`lp-subtext lp-anim ${ANIM_DELAYS[2]}`}>
              От родительского стада до прилавка — маточник, инкубация, откорм,
              убойня, финансы и отчёты в единой системе с&nbsp;Telegram-уведомлениями.
            </p>
            <div className={`lp-cta-row lp-anim ${ANIM_DELAYS[3]}`}>
              <a href="#demo" className="lp-btn-lg btn-primary">
                Запросить демо
                <Icon name="arrow-right" size={18} />
              </a>
              <a href="/login" className="lp-btn-lg btn-secondary">
                Войти в систему
              </a>
            </div>

            <div className={`lp-stats-row lp-anim ${ANIM_DELAYS[4]}`} role="list" aria-label="Ключевые показатели">
              {STATS.map(s => (
                <div key={s.label} className="lp-stat" role="listitem">
                  <div className="lp-stat-value">{s.value}</div>
                  <div className="lp-stat-label">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Features ── */}
        <section id="features" className="lp-section" aria-labelledby="features-title">
          <div className="lp-section-inner">
            <div className="lp-section-header">
              <div className="lp-section-eyebrow">Что входит в ERP</div>
              <h2 id="features-title" className="lp-section-title">Модули системы</h2>
              <p className="lp-section-sub">
                Каждый модуль закрывает отдельный участок и передаёт данные дальше
                по цепочке — автоматически.
              </p>
            </div>
            <div className="lp-features-grid">
              {FEATURES.map((f, i) => (
                <article
                  key={f.title}
                  className={`lp-feature-card lp-anim lp-anim-d${Math.min(i % 4 + 1, 5)}`}
                >
                  <div className="lp-feature-icon" aria-hidden="true">
                    <Icon name={f.icon} size={22} />
                  </div>
                  <h3>{f.title}</h3>
                  <p>{f.desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ── How it works ── */}
        <section id="how" className="lp-section lp-how-section" aria-labelledby="how-title">
          <div className="lp-section-inner">
            <div className="lp-section-header">
              <div className="lp-section-eyebrow">Как это работает</div>
              <h2 id="how-title" className="lp-section-title">Три шага до запуска</h2>
              <p className="lp-section-sub">
                Не нужна долгая настройка или интеграция. Подключаетесь и начинаете работать.
              </p>
            </div>
            <div className="lp-steps-grid">
              {STEPS.map((s, i) => (
                <div key={s.num} className={`lp-step lp-anim lp-anim-d${i + 1}`}>
                  <div className="lp-step-num" aria-hidden="true">{s.num}</div>
                  <h3>{s.title}</h3>
                  <p>{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Why YemBro ── */}
        <section id="why" className="lp-section" aria-labelledby="why-title">
          <div className="lp-section-inner">
            <div className="lp-section-header center">
              <div className="lp-section-eyebrow">Почему YemBro</div>
              <h2 id="why-title" className="lp-section-title">Создано для птицеводства</h2>
              <p className="lp-section-sub">
                Не универсальная ERP с птицеводческим шаблоном — а система,
                спроектированная с нуля под реальные задачи птицефабрики.
              </p>
            </div>
            <div className="lp-why-grid">
              {WHY.map((w, i) => (
                <article key={w.title} className={`lp-why-card lp-anim lp-anim-d${i + 1}`}>
                  <div className={`lp-why-icon ${w.tone}`} aria-hidden="true">
                    <Icon name={w.icon} size={24} />
                  </div>
                  <div>
                    <div className="lp-why-tag">{w.tag}</div>
                    <h3 style={{ marginTop: 10 }}>{w.title}</h3>
                  </div>
                  <p>{w.desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ── Demo / CTA ── */}
        <section id="demo" className="lp-section lp-demo-section" aria-labelledby="demo-title">
          <div className="lp-section-inner">
            <div className="lp-demo-layout">
              <div className="lp-demo-info lp-anim lp-anim-d1">
                <div className="lp-section-eyebrow">Связаться с нами</div>
                <h2 id="demo-title">Попробуйте YemBro ERP бесплатно</h2>
                <p>
                  Покажем систему в действии, ответим на вопросы и настроим
                  под ваше хозяйство — без обязательств.
                </p>
                <ul className="lp-demo-checklist" aria-label="Что вы получите">
                  {[
                    'Демонстрация всех модулей под вашу структуру',
                    'Настройка ролей и прав для сотрудников',
                    'Подключение Telegram-уведомлений',
                    'Ответы на все технические вопросы',
                  ].map(item => (
                    <li key={item}>
                      <span className="lp-demo-check" aria-hidden="true">
                        <Icon name="check" size={12} />
                      </span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="lp-anim lp-anim-d2">
                <DemoForm />
              </div>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="lp-footer" aria-label="Подвал сайта">
          <div className="lp-footer-top">
            <div className="lp-footer-brand">
              <Logo light />
              <p>ERP-система для управления птицеводческим предприятием полного цикла.</p>
            </div>
            <div className="lp-footer-col">
              <h4>Система</h4>
              <ul>
                <li><a href="#features">Модули</a></li>
                <li><a href="#how">Как работает</a></li>
                <li><a href="#why">Преимущества</a></li>
                <li><a href="#demo">Демо</a></li>
              </ul>
            </div>
            <div className="lp-footer-col">
              <h4>Аккаунт</h4>
              <ul>
                <li><a href="/login">Войти</a></li>
              </ul>
            </div>
          </div>
          <div className="lp-footer-bottom">
            <span className="lp-footer-copy">© {new Date().getFullYear()} YemBro ERP. Все права защищены.</span>
          </div>
        </footer>
      </div>
    </>
  );
}
