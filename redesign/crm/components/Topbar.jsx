/* Topbar Component */
const topbarStyles = {
  bar: {
    position: 'fixed', top: 0, right: 0,
    left: 'var(--sidebar-width)',
    height: 'var(--topbar-height)',
    background: '#FFFFFF',
    borderBottom: '1px solid var(--surface-border)',
    display: 'flex', alignItems: 'center',
    padding: '0 24px', gap: 16,
    zIndex: 99,
  },
  breadcrumb: {
    fontSize: 14, color: 'var(--text-color-muted)', fontWeight: 500,
  },
  breadcrumbActive: {
    color: 'var(--text-color)', fontWeight: 600,
  },
  searchWrap: {
    flex: 1, maxWidth: 420, position: 'relative',
  },
  searchInput: {
    width: '100%', padding: '8px 12px 8px 36px',
    border: '1px solid var(--surface-border)',
    borderRadius: 8, fontSize: 13,
    background: 'var(--surface-ground)',
    outline: 'none', fontFamily: 'inherit',
    transition: 'border-color 0.15s',
  },
  searchIcon: {
    position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
    color: 'var(--text-color-muted)',
  },
  actions: {
    display: 'flex', alignItems: 'center', gap: 4, marginLeft: 'auto',
  },
  iconBtn: (hovered) => ({
    width: 36, height: 36, borderRadius: 8,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    cursor: 'pointer', position: 'relative',
    background: hovered ? 'var(--surface-hover)' : 'transparent',
    color: 'var(--text-color-secondary)',
    transition: 'all 0.15s',
    border: 'none',
  }),
  notifDot: {
    position: 'absolute', top: 6, right: 6,
    width: 8, height: 8, borderRadius: '50%',
    background: 'var(--red-500)', border: '2px solid #fff',
  },
};

const pageNames = {
  dashboard: 'Дашборд',
  contacts: 'Контакты',
  deals: 'Сделки',
  tasks: 'Задачи',
  chat: 'Чат',
  email: 'Рассылки',
  finance: 'Финансы',
  reports: 'Отчёты',
  phone: 'Телефония',
  settings: 'Настройки',
};

function Topbar({ currentPage, onSearch }) {
  const [searchValue, setSearchValue] = React.useState('');
  const [searchFocused, setSearchFocused] = React.useState(false);
  const [hoveredBtn, setHoveredBtn] = React.useState(null);

  return (
    <header style={topbarStyles.bar}>
      <div>
        <span style={topbarStyles.breadcrumb}>CRM Pro / </span>
        <span style={topbarStyles.breadcrumbActive}>{pageNames[currentPage] || 'Дашборд'}</span>
      </div>
      <div style={topbarStyles.searchWrap}>
        <div style={topbarStyles.searchIcon}>
          <SvgIcon d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" size={16} />
        </div>
        <input
          style={{
            ...topbarStyles.searchInput,
            borderColor: searchFocused ? 'var(--primary)' : 'var(--surface-border)',
          }}
          placeholder="Поиск контактов, сделок, задач..."
          value={searchValue}
          onChange={e => setSearchValue(e.target.value)}
          onFocus={() => setSearchFocused(true)}
          onBlur={() => setSearchFocused(false)}
        />
      </div>
      <div style={topbarStyles.actions}>
        {['bell', 'calendar', 'plus'].map(btn => (
          <button
            key={btn}
            style={topbarStyles.iconBtn(hoveredBtn === btn)}
            onMouseEnter={() => setHoveredBtn(btn)}
            onMouseLeave={() => setHoveredBtn(null)}
          >
            <SvgIcon d={
              btn === 'bell' ? 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' :
              btn === 'calendar' ? 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' :
              'M12 4v16m8-8H4'
            } size={18} />
            {btn === 'bell' && <div style={topbarStyles.notifDot} />}
          </button>
        ))}
      </div>
    </header>
  );
}

window.Topbar = Topbar;
window.pageNames = pageNames;
