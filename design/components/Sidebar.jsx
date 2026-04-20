/* Sidebar Component */
const menuItems = [
  { id: 'dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4', label: 'Дашборд' },
  { id: 'contacts', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z', label: 'Контакты' },
  { id: 'deals', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z', label: 'Сделки' },
  { id: 'tasks', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4', label: 'Задачи' },
  { type: 'divider' },
  { id: 'chat', icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z', label: 'Чат', badge: 3 },
  { id: 'email', icon: 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z', label: 'Рассылки' },
  { id: 'finance', icon: 'M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z', label: 'Финансы' },
  { id: 'reports', icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', label: 'Отчёты' },
  { type: 'divider' },
  { id: 'phone', icon: 'M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z', label: 'Телефония' },
  { id: 'settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z', label: 'Настройки' },
];

const SvgIcon = ({ d, size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const sidebarStyles = {
  sidebar: {
    position: 'fixed', top: 0, left: 0, bottom: 0,
    width: 'var(--sidebar-width)',
    background: '#FFFFFF',
    borderRight: '1px solid var(--surface-border)',
    display: 'flex', flexDirection: 'column',
    zIndex: 100,
    transition: 'transform 0.3s ease',
  },
  logo: {
    height: 'var(--topbar-height)',
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '0 20px',
    borderBottom: '1px solid var(--surface-border)',
    fontWeight: 700, fontSize: 20, color: 'var(--primary)',
    letterSpacing: '-0.02em',
    flexShrink: 0,
  },
  logoIcon: {
    width: 34, height: 34, borderRadius: 8,
    background: 'var(--primary)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontSize: 16, fontWeight: 800,
  },
  nav: {
    flex: 1, overflowY: 'auto', padding: '12px 12px',
    display: 'flex', flexDirection: 'column', gap: 2,
  },
  item: (active) => ({
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '10px 12px', borderRadius: 8,
    cursor: 'pointer', fontSize: 14, fontWeight: active ? 600 : 500,
    color: active ? 'var(--primary)' : 'var(--text-color-secondary)',
    background: active ? 'var(--primary-lighter)' : 'transparent',
    transition: 'all 0.15s ease',
    position: 'relative',
    userSelect: 'none',
  }),
  divider: {
    height: 1, background: 'var(--surface-border)',
    margin: '8px 12px',
  },
  badge: {
    marginLeft: 'auto',
    background: 'var(--red-500)', color: '#fff',
    borderRadius: 10, fontSize: 11, fontWeight: 700,
    padding: '1px 7px', minWidth: 20, textAlign: 'center',
  },
  userArea: {
    padding: '14px 16px',
    borderTop: '1px solid var(--surface-border)',
    display: 'flex', alignItems: 'center', gap: 10,
    cursor: 'pointer', flexShrink: 0,
  },
  avatar: {
    width: 36, height: 36, borderRadius: '50%',
    background: 'linear-gradient(135deg, var(--primary), var(--primary-light))',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontWeight: 700, fontSize: 14,
  },
};

function Sidebar({ currentPage, onNavigate }) {
  const [hoveredItem, setHoveredItem] = React.useState(null);

  return (
    <aside style={sidebarStyles.sidebar}>
      <div style={sidebarStyles.logo}>
        <div style={sidebarStyles.logoIcon}>CR</div>
        <span>CRM Pro</span>
      </div>
      <nav style={sidebarStyles.nav}>
        {menuItems.map((item, i) => {
          if (item.type === 'divider') return <div key={i} style={sidebarStyles.divider} />;
          const active = currentPage === item.id;
          const hovered = hoveredItem === item.id && !active;
          return (
            <div
              key={item.id}
              style={{
                ...sidebarStyles.item(active),
                ...(hovered ? { background: 'var(--surface-hover)', color: 'var(--text-color)' } : {}),
              }}
              onClick={() => onNavigate(item.id)}
              onMouseEnter={() => setHoveredItem(item.id)}
              onMouseLeave={() => setHoveredItem(null)}
            >
              <SvgIcon d={item.icon} />
              <span>{item.label}</span>
              {item.badge && <span style={sidebarStyles.badge}>{item.badge}</span>}
            </div>
          );
        })}
      </nav>
      <div style={sidebarStyles.userArea}>
        <div style={sidebarStyles.avatar}>АИ</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Алексей Иванов</div>
          <div style={{ fontSize: 11, color: 'var(--text-color-muted)' }}>Менеджер</div>
        </div>
      </div>
    </aside>
  );
}

window.Sidebar = Sidebar;
window.SvgIcon = SvgIcon;
