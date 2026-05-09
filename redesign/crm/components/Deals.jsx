/* Deals Kanban Screen */
const dealStages = [
  { id: 'new', name: 'Новые', color: '#8B5CF6', deals: [
    { id: 1, name: 'Внедрение CRM', company: 'ООО «Дигитал»', amount: '₽ 380K', contact: 'М. Петрова', days: 3, priority: 'medium' },
    { id: 2, name: 'Разработка сайта', company: 'ГК «Инновация»', amount: '₽ 420K', contact: 'П. Лебедев', days: 1, priority: 'low' },
  ]},
  { id: 'qualify', name: 'Квалификация', color: '#3B82F6', deals: [
    { id: 3, name: 'Модернизация IT', company: 'АО «ПромГрупп»', amount: '₽ 1.2M', contact: 'А. Сидорова', days: 5, priority: 'high' },
    { id: 4, name: 'Поддержка 1С', company: 'ООО «АйТиПро»', amount: '₽ 560K', contact: 'О. Кузнецова', days: 7, priority: 'medium' },
    { id: 5, name: 'Аудит безопасности', company: 'СберТех', amount: '₽ 890K', contact: 'Е. Новикова', days: 2, priority: 'high' },
  ]},
  { id: 'proposal', name: 'КП отправлено', color: '#06B6D4', deals: [
    { id: 6, name: 'Облачная миграция', company: 'ИП Козлов А.В.', amount: '₽ 240K', contact: 'Д. Козлов', days: 10, priority: 'low' },
    { id: 7, name: 'ERP-интеграция', company: 'СберТех', amount: '₽ 2.1M', contact: 'Е. Новикова', days: 4, priority: 'high' },
  ]},
  { id: 'negotiation', name: 'Переговоры', color: '#F97316', deals: [
    { id: 8, name: 'Автоматизация склада', company: 'ООО «ТехСтарт»', amount: '₽ 850K', contact: 'И. Волков', days: 12, priority: 'high' },
  ]},
  { id: 'won', name: 'Закрыто ✓', color: '#22C55E', deals: [
    { id: 9, name: 'Обновление ПО', company: 'АО «ПромГрупп»', amount: '₽ 650K', contact: 'А. Сидорова', days: 0, priority: 'medium' },
  ]},
];

const kanbanStyles = {
  board: {
    display: 'flex', gap: 16, overflowX: 'auto', paddingBottom: 20,
    minHeight: 'calc(100vh - 180px)',
  },
  column: {
    minWidth: 280, maxWidth: 300, flex: '0 0 280px',
    display: 'flex', flexDirection: 'column',
  },
  colHeader: (color) => ({
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 12, padding: '0 4px',
  }),
  colTitle: (color) => ({
    display: 'flex', alignItems: 'center', gap: 8,
    fontSize: 13, fontWeight: 700, color: 'var(--text-color)',
  }),
  colDot: (color) => ({
    width: 10, height: 10, borderRadius: '50%', background: color,
  }),
  colCount: {
    background: 'var(--surface-hover)', borderRadius: 12,
    padding: '2px 8px', fontSize: 11, fontWeight: 700,
    color: 'var(--text-color-secondary)',
  },
  colTotal: (color) => ({
    fontSize: 12, fontWeight: 700, color: color,
  }),
  card: (hovered, dragging) => ({
    background: '#fff', borderRadius: 'var(--radius-md)',
    border: '1px solid ' + (hovered ? 'var(--primary-light)' : 'var(--surface-border)'),
    padding: 16, marginBottom: 10, cursor: 'grab',
    boxShadow: hovered ? 'var(--shadow-md)' : 'var(--shadow-sm)',
    transition: 'all 0.15s ease',
    transform: hovered ? 'translateY(-2px)' : 'none',
  }),
  cardName: { fontSize: 14, fontWeight: 600, marginBottom: 4 },
  cardCompany: { fontSize: 12, color: 'var(--text-color-secondary)', marginBottom: 10 },
  cardBottom: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  cardAmount: { fontSize: 15, fontWeight: 700, color: 'var(--primary)' },
  cardMeta: { display: 'flex', gap: 8, alignItems: 'center', fontSize: 11, color: 'var(--text-color-muted)' },
  priorityDot: (p) => ({
    width: 6, height: 6, borderRadius: '50%',
    background: p === 'high' ? 'var(--red-500)' : p === 'medium' ? 'var(--orange-500)' : 'var(--green-500)',
  }),
  addBtn: {
    padding: '8px 0', borderRadius: 8, border: '2px dashed var(--surface-border)',
    background: 'transparent', color: 'var(--text-color-muted)',
    fontSize: 13, fontWeight: 500, cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
    fontFamily: 'inherit', marginTop: 4,
    transition: 'all 0.15s',
  },
};

function DealsScreen() {
  const [hoveredCard, setHoveredCard] = React.useState(null);
  const [stages, setStages] = React.useState(dealStages);

  const totalAmount = stages.reduce((sum, s) => {
    return sum + s.deals.reduce((ds, d) => {
      const num = parseFloat(d.amount.replace(/[^\d.]/g, ''));
      const mult = d.amount.includes('M') ? 1000 : 1;
      return ds + num * mult;
    }, 0);
  }, 0);

  return (
    <div className="animate-fade">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Сделки</h1>
          <p style={{ fontSize: 14, color: 'var(--text-color-secondary)' }}>
            {stages.reduce((s, st) => s + st.deals.length, 0)} сделок в воронке
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{
            padding: '8px 16px', borderRadius: 8, background: 'var(--primary-lighter)',
            fontSize: 13, fontWeight: 700, color: 'var(--primary)',
          }}>
            Итого: ₽ {(totalAmount / 1000).toFixed(1)}M
          </div>
          <button style={{
            padding: '9px 18px', borderRadius: 8, border: 'none',
            background: 'var(--primary)', color: '#fff', fontSize: 13, fontWeight: 600,
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'inherit',
          }}>
            <SvgIcon d="M12 4v16m8-8H4" size={15} />
            Новая сделка
          </button>
        </div>
      </div>

      <div style={kanbanStyles.board}>
        {stages.map(stage => {
          const stageSum = stage.deals.reduce((s, d) => {
            const num = parseFloat(d.amount.replace(/[^\d.]/g, ''));
            const mult = d.amount.includes('M') ? 1000 : 1;
            return s + num * mult;
          }, 0);
          return (
            <div key={stage.id} style={kanbanStyles.column}>
              <div style={kanbanStyles.colHeader(stage.color)}>
                <div style={kanbanStyles.colTitle(stage.color)}>
                  <div style={kanbanStyles.colDot(stage.color)} />
                  {stage.name}
                  <span style={kanbanStyles.colCount}>{stage.deals.length}</span>
                </div>
                <span style={kanbanStyles.colTotal(stage.color)}>₽ {stageSum >= 1000 ? (stageSum/1000).toFixed(1) + 'M' : stageSum + 'K'}</span>
              </div>
              <div style={{ flex: 1 }}>
                {stage.deals.map(deal => (
                  <div key={deal.id}
                    style={kanbanStyles.card(hoveredCard === deal.id)}
                    onMouseEnter={() => setHoveredCard(deal.id)}
                    onMouseLeave={() => setHoveredCard(null)}
                  >
                    <div style={kanbanStyles.cardName}>{deal.name}</div>
                    <div style={kanbanStyles.cardCompany}>{deal.company} · {deal.contact}</div>
                    <div style={kanbanStyles.cardBottom}>
                      <span style={kanbanStyles.cardAmount}>{deal.amount}</span>
                      <div style={kanbanStyles.cardMeta}>
                        <div style={kanbanStyles.priorityDot(deal.priority)} />
                        <span>{deal.days}д</span>
                      </div>
                    </div>
                  </div>
                ))}
                <button
                  style={kanbanStyles.addBtn}
                  onMouseEnter={e => { e.target.style.borderColor = 'var(--primary-light)'; e.target.style.color = 'var(--primary)'; }}
                  onMouseLeave={e => { e.target.style.borderColor = 'var(--surface-border)'; e.target.style.color = 'var(--text-color-muted)'; }}
                >
                  <SvgIcon d="M12 4v16m8-8H4" size={14} /> Добавить
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

window.DealsScreen = DealsScreen;
