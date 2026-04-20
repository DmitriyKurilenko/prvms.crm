/* Dashboard Screen */
const dashStyles = {
  grid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20, marginBottom: 24 },
  statCard: {
    background: '#fff', borderRadius: 'var(--radius-md)', padding: '20px 22px',
    border: '1px solid var(--surface-border)',
    display: 'flex', flexDirection: 'column', gap: 8,
    animation: 'fadeIn 0.4s ease both',
  },
  statTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  statLabel: { fontSize: 13, color: 'var(--text-color-secondary)', fontWeight: 500 },
  statValue: { fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-color)' },
  statChange: (positive) => ({
    fontSize: 12, fontWeight: 600,
    color: positive ? 'var(--green-500)' : 'var(--red-500)',
    display: 'flex', alignItems: 'center', gap: 3,
  }),
  statIcon: (bg) => ({
    width: 42, height: 42, borderRadius: 10, background: bg,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  }),
  row: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 },
  card: {
    background: '#fff', borderRadius: 'var(--radius-md)',
    border: '1px solid var(--surface-border)',
    animation: 'fadeIn 0.5s ease both',
  },
  cardHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px 20px', borderBottom: '1px solid var(--surface-border)',
  },
  cardTitle: { fontSize: 15, fontWeight: 700 },
  cardBody: { padding: '16px 20px' },
  chip: (color) => ({
    fontSize: 11, fontWeight: 600, padding: '3px 10px',
    borderRadius: 20, background: color + '18', color: color,
  }),
  tableRow: (hovered) => ({
    display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr',
    padding: '10px 0', borderBottom: '1px solid var(--surface-border)',
    fontSize: 13, alignItems: 'center',
    background: hovered ? 'var(--surface-hover)' : 'transparent',
    cursor: 'pointer', transition: 'background 0.1s',
  }),
  progressBar: (pct, color) => ({
    height: 6, borderRadius: 3, background: '#F3F4F6',
    position: 'relative', overflow: 'hidden',
  }),
  progressFill: (pct, color) => ({
    position: 'absolute', left: 0, top: 0, bottom: 0,
    width: pct + '%', borderRadius: 3,
    background: color, transition: 'width 0.6s ease',
  }),
  activityItem: {
    display: 'flex', gap: 12, padding: '10px 0',
    borderBottom: '1px solid var(--surface-border)',
    fontSize: 13,
  },
  activityDot: (color) => ({
    width: 8, height: 8, borderRadius: '50%', background: color,
    marginTop: 5, flexShrink: 0,
  }),
};

const stats = [
  { label: 'Выручка', value: '₽ 4.2M', change: '+12.5%', positive: true, bg: 'var(--blue-50)', color: 'var(--blue-500)', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { label: 'Новые сделки', value: '48', change: '+8.2%', positive: true, bg: 'var(--green-50)', color: 'var(--green-500)', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
  { label: 'Клиенты', value: '1,284', change: '+3.1%', positive: true, bg: 'var(--primary-lighter)', color: 'var(--primary)', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z' },
  { label: 'Задачи', value: '23', change: '-2 просрочено', positive: false, bg: 'var(--orange-50)', color: 'var(--orange-500)', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4' },
];

const recentDeals = [
  { name: 'ООО «ТехСтарт»', amount: '₽ 850K', stage: 'Переговоры', stageColor: '#F97316', date: '20 апр' },
  { name: 'ИП Козлов А.В.', amount: '₽ 240K', stage: 'КП отправлено', stageColor: '#3B82F6', date: '19 апр' },
  { name: 'АО «ПромГрупп»', amount: '₽ 1.2M', stage: 'Закрыта', stageColor: '#22C55E', date: '18 апр' },
  { name: 'ООО «Дигитал»', amount: '₽ 380K', stage: 'Новая', stageColor: '#8B5CF6', date: '18 апр' },
  { name: 'СберТех', amount: '₽ 2.1M', stage: 'Переговоры', stageColor: '#F97316', date: '17 апр' },
];

const funnelStages = [
  { name: 'Новые лиды', count: 34, pct: 100, color: '#818CF8' },
  { name: 'Квалификация', count: 22, pct: 65, color: '#60A5FA' },
  { name: 'КП отправлено', count: 15, pct: 44, color: '#34D399' },
  { name: 'Переговоры', count: 8, pct: 24, color: '#FBBF24' },
  { name: 'Закрыто', count: 5, pct: 15, color: '#22C55E' },
];

const activities = [
  { text: 'Новая сделка с ООО «ТехСтарт» на ₽850K', time: '10 мин назад', color: 'var(--green-500)' },
  { text: 'Звонок клиенту ИП Козлов — перезвонить в 15:00', time: '32 мин назад', color: 'var(--blue-500)' },
  { text: 'КП #1042 отклонено — АО «Ресурс»', time: '1 ч назад', color: 'var(--red-500)' },
  { text: 'Задача «Подготовить презентацию» выполнена', time: '2 ч назад', color: 'var(--primary)' },
  { text: 'Новый контакт: Мария Петрова, ООО «Дигитал»', time: '3 ч назад', color: 'var(--orange-500)' },
];

function DashboardScreen() {
  const [hoveredRow, setHoveredRow] = React.useState(null);
  const [animatedPcts, setAnimatedPcts] = React.useState(funnelStages.map(() => 0));

  React.useEffect(() => {
    const t = setTimeout(() => setAnimatedPcts(funnelStages.map(s => s.pct)), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Добро пожаловать, Алексей</h1>
          <p style={{ fontSize: 14, color: 'var(--text-color-secondary)' }}>Вот что происходит сегодня</p>
        </div>
        <button style={{
          padding: '9px 18px', borderRadius: 8, border: 'none',
          background: 'var(--primary)', color: '#fff', fontSize: 13, fontWeight: 600,
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          fontFamily: 'inherit',
        }}>
          <SvgIcon d="M12 4v16m8-8H4" size={15} />
          Новая сделка
        </button>
      </div>

      <div style={dashStyles.grid}>
        {stats.map((s, i) => (
          <div key={i} style={{ ...dashStyles.statCard, animationDelay: i * 0.08 + 's' }}>
            <div style={dashStyles.statTop}>
              <span style={dashStyles.statLabel}>{s.label}</span>
              <div style={dashStyles.statIcon(s.bg)}>
                <div style={{ color: s.color }}><SvgIcon d={s.icon} size={20} /></div>
              </div>
            </div>
            <div style={dashStyles.statValue}>{s.value}</div>
            <div style={dashStyles.statChange(s.positive)}>
              {s.positive ? '↑' : '↓'} {s.change}
            </div>
          </div>
        ))}
      </div>

      <div style={dashStyles.row}>
        <div style={dashStyles.card}>
          <div style={dashStyles.cardHeader}>
            <span style={dashStyles.cardTitle}>Последние сделки</span>
            <span style={{ fontSize: 12, color: 'var(--primary)', cursor: 'pointer', fontWeight: 600 }}>Все сделки →</span>
          </div>
          <div style={dashStyles.cardBody}>
            {recentDeals.map((d, i) => (
              <div key={i} style={dashStyles.tableRow(hoveredRow === i)}
                onMouseEnter={() => setHoveredRow(i)} onMouseLeave={() => setHoveredRow(null)}>
                <span style={{ fontWeight: 600 }}>{d.name}</span>
                <span style={{ fontWeight: 600 }}>{d.amount}</span>
                <span><span style={dashStyles.chip(d.stageColor)}>{d.stage}</span></span>
                <span style={{ color: 'var(--text-color-muted)', textAlign: 'right' }}>{d.date}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={dashStyles.card}>
          <div style={dashStyles.cardHeader}>
            <span style={dashStyles.cardTitle}>Воронка продаж</span>
            <span style={{ fontSize: 12, color: 'var(--text-color-muted)' }}>Апрель 2026</span>
          </div>
          <div style={{ ...dashStyles.cardBody, display: 'flex', flexDirection: 'column', gap: 14 }}>
            {funnelStages.map((s, i) => (
              <div key={i}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13 }}>
                  <span style={{ fontWeight: 500 }}>{s.name}</span>
                  <span style={{ fontWeight: 700, color: s.color }}>{s.count}</span>
                </div>
                <div style={dashStyles.progressBar(s.pct, s.color)}>
                  <div style={dashStyles.progressFill(animatedPcts[i], s.color)} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={dashStyles.row}>
        <div style={dashStyles.card}>
          <div style={dashStyles.cardHeader}>
            <span style={dashStyles.cardTitle}>Активность</span>
          </div>
          <div style={dashStyles.cardBody}>
            {activities.map((a, i) => (
              <div key={i} style={dashStyles.activityItem}>
                <div style={dashStyles.activityDot(a.color)} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500 }}>{a.text}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-color-muted)', marginTop: 2 }}>{a.time}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={dashStyles.card}>
          <div style={dashStyles.cardHeader}>
            <span style={dashStyles.cardTitle}>Задачи на сегодня</span>
            <span style={dashStyles.chip('var(--primary)')}>5 задач</span>
          </div>
          <div style={dashStyles.cardBody}>
            {[
              { text: 'Позвонить ООО «ТехСтарт»', time: '10:00', done: true },
              { text: 'Подготовить КП для АО «ПромГрупп»', time: '12:00', done: true },
              { text: 'Встреча с командой продаж', time: '14:00', done: false },
              { text: 'Обновить CRM-карточки', time: '16:00', done: false },
              { text: 'Отправить отчёт руководству', time: '17:30', done: false },
            ].map((t, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0',
                borderBottom: '1px solid var(--surface-border)', fontSize: 13,
                opacity: t.done ? 0.5 : 1,
              }}>
                <div style={{
                  width: 20, height: 20, borderRadius: 6,
                  border: t.done ? 'none' : '2px solid var(--surface-border)',
                  background: t.done ? 'var(--green-500)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontSize: 11, cursor: 'pointer', flexShrink: 0,
                }}>
                  {t.done && '✓'}
                </div>
                <span style={{ flex: 1, textDecoration: t.done ? 'line-through' : 'none', fontWeight: 500 }}>{t.text}</span>
                <span style={{ color: 'var(--text-color-muted)', fontSize: 12 }}>{t.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.DashboardScreen = DashboardScreen;
