/* Contacts Screen */
const contactsData = [
  { id: 1, name: 'Мария Петрова', company: 'ООО «Дигитал»', role: 'Директор', email: 'petrova@digital.ru', phone: '+7 (495) 123-45-67', deals: 3, revenue: '₽ 1.2M', status: 'Активный', avatar: 'МП' },
  { id: 2, name: 'Дмитрий Козлов', company: 'ИП Козлов А.В.', role: 'Владелец', email: 'kozlov@mail.ru', phone: '+7 (903) 234-56-78', deals: 1, revenue: '₽ 240K', status: 'Активный', avatar: 'ДК' },
  { id: 3, name: 'Анна Сидорова', company: 'АО «ПромГрупп»', role: 'Закупки', email: 'sidorova@prom.ru', phone: '+7 (495) 345-67-89', deals: 5, revenue: '₽ 3.8M', status: 'Активный', avatar: 'АС' },
  { id: 4, name: 'Игорь Волков', company: 'ООО «ТехСтарт»', role: 'CTO', email: 'volkov@techstart.ru', phone: '+7 (916) 456-78-90', deals: 2, revenue: '₽ 850K', status: 'Новый', avatar: 'ИВ' },
  { id: 5, name: 'Елена Новикова', company: 'СберТех', role: 'Менеджер', email: 'novikova@sber.ru', phone: '+7 (495) 567-89-01', deals: 4, revenue: '₽ 2.1M', status: 'Активный', avatar: 'ЕН' },
  { id: 6, name: 'Сергей Морозов', company: 'ООО «Ресурс»', role: 'Директор', email: 'morozov@resurs.ru', phone: '+7 (926) 678-90-12', deals: 0, revenue: '₽ 0', status: 'Неактивный', avatar: 'СМ' },
  { id: 7, name: 'Ольга Кузнецова', company: 'ООО «АйТиПро»', role: 'HR', email: 'kuznetsova@itpro.ru', phone: '+7 (495) 789-01-23', deals: 2, revenue: '₽ 560K', status: 'Активный', avatar: 'ОК' },
  { id: 8, name: 'Павел Лебедев', company: 'ГК «Инновация»', role: 'Финансы', email: 'lebedev@innov.ru', phone: '+7 (903) 890-12-34', deals: 1, revenue: '₽ 420K', status: 'Новый', avatar: 'ПЛ' },
];

const avatarColors = ['#4F46E5', '#0891B2', '#7C3AED', '#DB2777', '#059669', '#D97706', '#DC2626', '#2563EB'];

const contactStyles = {
  toolbar: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 20, flexWrap: 'wrap', gap: 12,
  },
  filterGroup: { display: 'flex', gap: 8 },
  filterBtn: (active) => ({
    padding: '7px 14px', borderRadius: 7, border: '1px solid ' + (active ? 'var(--primary)' : 'var(--surface-border)'),
    background: active ? 'var(--primary-lighter)' : '#fff', color: active ? 'var(--primary)' : 'var(--text-color-secondary)',
    fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
    transition: 'all 0.15s',
  }),
  table: {
    background: '#fff', borderRadius: 'var(--radius-md)',
    border: '1px solid var(--surface-border)', overflow: 'hidden',
  },
  thead: {
    display: 'grid', gridTemplateColumns: '44px 2fr 1.5fr 1fr 1fr 0.8fr 80px',
    padding: '12px 20px', borderBottom: '1px solid var(--surface-border)',
    fontSize: 12, fontWeight: 600, color: 'var(--text-color-muted)',
    textTransform: 'uppercase', letterSpacing: '0.05em',
  },
  trow: (hovered) => ({
    display: 'grid', gridTemplateColumns: '44px 2fr 1.5fr 1fr 1fr 0.8fr 80px',
    padding: '12px 20px', borderBottom: '1px solid var(--surface-border)',
    fontSize: 13, alignItems: 'center', cursor: 'pointer',
    background: hovered ? 'var(--surface-hover)' : 'transparent',
    transition: 'background 0.1s',
  }),
  avatar: (i) => ({
    width: 34, height: 34, borderRadius: '50%',
    background: avatarColors[i % avatarColors.length],
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontSize: 12, fontWeight: 700,
  }),
  statusDot: (status) => ({
    width: 7, height: 7, borderRadius: '50%',
    background: status === 'Активный' ? 'var(--green-500)' : status === 'Новый' ? 'var(--blue-500)' : 'var(--text-color-muted)',
    display: 'inline-block', marginRight: 6,
  }),
  actionBtn: {
    width: 30, height: 30, borderRadius: 6, border: 'none',
    background: 'transparent', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: 'var(--text-color-muted)',
  },
};

function ContactsScreen({ onOpenContact }) {
  const [filter, setFilter] = React.useState('Все');
  const [hoveredRow, setHoveredRow] = React.useState(null);
  const [selected, setSelected] = React.useState(new Set());

  const filtered = filter === 'Все' ? contactsData : contactsData.filter(c => c.status === filter);

  return (
    <div className="animate-fade">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Контакты</h1>
          <p style={{ fontSize: 14, color: 'var(--text-color-secondary)' }}>{contactsData.length} контактов в базе</p>
        </div>
        <button style={{
          padding: '9px 18px', borderRadius: 8, border: 'none',
          background: 'var(--primary)', color: '#fff', fontSize: 13, fontWeight: 600,
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'inherit',
        }}>
          <SvgIcon d="M12 4v16m8-8H4" size={15} />
          Новый контакт
        </button>
      </div>

      <div style={contactStyles.toolbar}>
        <div style={contactStyles.filterGroup}>
          {['Все', 'Активный', 'Новый', 'Неактивный'].map(f => (
            <button key={f} style={contactStyles.filterBtn(filter === f)} onClick={() => setFilter(f)}>{f}</button>
          ))}
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-color-muted)' }}>
          Показано: {filtered.length} из {contactsData.length}
        </div>
      </div>

      <div style={contactStyles.table}>
        <div style={contactStyles.thead}>
          <span></span>
          <span>Контакт</span>
          <span>Компания</span>
          <span>Телефон</span>
          <span>Сделки / Выручка</span>
          <span>Статус</span>
          <span></span>
        </div>
        {filtered.map((c, i) => (
          <div key={c.id} style={contactStyles.trow(hoveredRow === c.id)}
            onMouseEnter={() => setHoveredRow(c.id)}
            onMouseLeave={() => setHoveredRow(null)}
            onClick={() => onOpenContact && onOpenContact(c)}
          >
            <div style={contactStyles.avatar(i)}>{c.avatar}</div>
            <div>
              <div style={{ fontWeight: 600 }}>{c.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-color-muted)' }}>{c.email}</div>
            </div>
            <div>
              <div style={{ fontWeight: 500 }}>{c.company}</div>
              <div style={{ fontSize: 11, color: 'var(--text-color-muted)' }}>{c.role}</div>
            </div>
            <div style={{ color: 'var(--text-color-secondary)' }}>{c.phone}</div>
            <div>
              <span style={{ fontWeight: 600 }}>{c.deals}</span>
              <span style={{ color: 'var(--text-color-muted)' }}> / {c.revenue}</span>
            </div>
            <div>
              <span style={contactStyles.statusDot(c.status)} />
              <span style={{ fontSize: 12, fontWeight: 500 }}>{c.status}</span>
            </div>
            <button style={contactStyles.actionBtn} onClick={e => e.stopPropagation()}>
              <SvgIcon d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" size={16} />
            </button>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, fontSize: 13, color: 'var(--text-color-muted)' }}>
        <span>Страница 1 из 1</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {[1].map(p => (
            <button key={p} style={{
              width: 32, height: 32, borderRadius: 6,
              border: 'none', background: p === 1 ? 'var(--primary)' : 'var(--surface-hover)',
              color: p === 1 ? '#fff' : 'var(--text-color-secondary)',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}>{p}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

window.ContactsScreen = ContactsScreen;
window.contactsData = contactsData;
window.avatarColors = avatarColors;
