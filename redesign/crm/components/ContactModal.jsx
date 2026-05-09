/* Contact Detail Modal */
const modalStyles = {
  overlay: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.35)', zIndex: 1000,
    display: 'flex', justifyContent: 'flex-end',
    animation: 'fadeIn 0.2s ease',
  },
  panel: {
    width: 520, height: '100%', background: '#fff',
    boxShadow: '-8px 0 30px rgba(0,0,0,0.12)',
    overflowY: 'auto', animation: 'slideInRight 0.25s ease',
    display: 'flex', flexDirection: 'column',
  },
  header: {
    padding: '24px 28px 20px', borderBottom: '1px solid var(--surface-border)',
    display: 'flex', alignItems: 'flex-start', gap: 16,
  },
  bigAvatar: (color) => ({
    width: 56, height: 56, borderRadius: 16,
    background: color,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontSize: 20, fontWeight: 700, flexShrink: 0,
  }),
  closeBtn: {
    position: 'absolute', top: 16, right: 16,
    width: 32, height: 32, borderRadius: 8, border: 'none',
    background: 'var(--surface-hover)', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: 'var(--text-color-muted)',
  },
  tabs: {
    display: 'flex', gap: 0, borderBottom: '1px solid var(--surface-border)',
    padding: '0 28px',
  },
  tab: (active) => ({
    padding: '12px 16px', fontSize: 13, fontWeight: active ? 600 : 500,
    color: active ? 'var(--primary)' : 'var(--text-color-secondary)',
    borderBottom: active ? '2px solid var(--primary)' : '2px solid transparent',
    cursor: 'pointer', background: 'none', border: 'none',
    fontFamily: 'inherit', marginBottom: -1,
  }),
  body: { padding: '20px 28px', flex: 1 },
  field: { marginBottom: 16 },
  fieldLabel: { fontSize: 11, fontWeight: 600, color: 'var(--text-color-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' },
  fieldValue: { fontSize: 14, fontWeight: 500, color: 'var(--text-color)' },
  dealRow: (hovered) => ({
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '10px 12px', borderRadius: 8, marginBottom: 4,
    background: hovered ? 'var(--surface-hover)' : 'transparent',
    cursor: 'pointer', transition: 'background 0.1s',
  }),
  noteInput: {
    width: '100%', padding: '10px 12px', borderRadius: 8,
    border: '1px solid var(--surface-border)', fontSize: 13,
    fontFamily: 'inherit', resize: 'vertical', minHeight: 80,
    outline: 'none',
  },
};

function ContactModal({ contact, onClose }) {
  const [tab, setTab] = React.useState('info');
  const [hoveredDeal, setHoveredDeal] = React.useState(null);
  const [note, setNote] = React.useState('');

  if (!contact) return null;

  const colorIdx = contactsData.findIndex(c => c.id === contact.id);
  const color = avatarColors[colorIdx % avatarColors.length];

  const contactDeals = [
    { name: 'Модернизация IT', amount: '₽ 1.2M', stage: 'Квалификация', stageColor: '#3B82F6' },
    { name: 'Поддержка серверов', amount: '₽ 380K', stage: 'КП отправлено', stageColor: '#06B6D4' },
  ];

  const activities = [
    { type: 'call', text: 'Входящий звонок — 4 мин', time: '2 ч назад' },
    { type: 'email', text: 'Отправлено КП #1045', time: 'вчера' },
    { type: 'note', text: 'Заинтересован в расширении', time: '3 дня назад' },
    { type: 'deal', text: 'Создана сделка «Модернизация IT»', time: '5 дней назад' },
  ];

  return (
    <div style={modalStyles.overlay} onClick={onClose}>
      <div style={modalStyles.panel} onClick={e => e.stopPropagation()}>
        <div style={{ position: 'relative' }}>
          <div style={modalStyles.header}>
            <div style={modalStyles.bigAvatar(color)}>{contact.avatar}</div>
            <div>
              <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 2 }}>{contact.name}</div>
              <div style={{ fontSize: 13, color: 'var(--text-color-secondary)' }}>{contact.role} · {contact.company}</div>
              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                {['Позвонить', 'Написать', 'Задача'].map(action => (
                  <button key={action} style={{
                    padding: '5px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                    border: '1px solid var(--surface-border)', background: '#fff',
                    cursor: 'pointer', fontFamily: 'inherit', color: 'var(--text-color-secondary)',
                  }}>{action}</button>
                ))}
              </div>
            </div>
          </div>
          <button style={modalStyles.closeBtn} onClick={onClose}>
            <SvgIcon d="M6 18L18 6M6 6l12 12" size={16} />
          </button>
        </div>

        <div style={modalStyles.tabs}>
          {[['info', 'Инфо'], ['deals', 'Сделки'], ['activity', 'Активность'], ['notes', 'Заметки']].map(([id, label]) => (
            <button key={id} style={modalStyles.tab(tab === id)} onClick={() => setTab(id)}>{label}</button>
          ))}
        </div>

        <div style={modalStyles.body}>
          {tab === 'info' && (
            <div className="animate-fade">
              {[
                ['Email', contact.email],
                ['Телефон', contact.phone],
                ['Компания', contact.company],
                ['Должность', contact.role],
                ['Сделок', String(contact.deals)],
                ['Выручка', contact.revenue],
                ['Статус', contact.status],
              ].map(([label, value]) => (
                <div key={label} style={modalStyles.field}>
                  <div style={modalStyles.fieldLabel}>{label}</div>
                  <div style={modalStyles.fieldValue}>{value}</div>
                </div>
              ))}
            </div>
          )}
          {tab === 'deals' && (
            <div className="animate-fade">
              {contactDeals.map((d, i) => (
                <div key={i} style={modalStyles.dealRow(hoveredDeal === i)}
                  onMouseEnter={() => setHoveredDeal(i)} onMouseLeave={() => setHoveredDeal(null)}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{d.name}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-color-muted)', marginTop: 2 }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                        background: d.stageColor + '18', color: d.stageColor,
                      }}>{d.stage}</span>
                    </div>
                  </div>
                  <span style={{ fontWeight: 700, color: 'var(--primary)', fontSize: 14 }}>{d.amount}</span>
                </div>
              ))}
            </div>
          )}
          {tab === 'activity' && (
            <div className="animate-fade">
              {activities.map((a, i) => (
                <div key={i} style={{ display: 'flex', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--surface-border)', fontSize: 13 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                    background: a.type === 'call' ? 'var(--green-50)' : a.type === 'email' ? 'var(--blue-50)' : a.type === 'deal' ? 'var(--primary-lighter)' : 'var(--orange-50)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: a.type === 'call' ? 'var(--green-500)' : a.type === 'email' ? 'var(--blue-500)' : a.type === 'deal' ? 'var(--primary)' : 'var(--orange-500)',
                  }}>
                    <SvgIcon d={
                      a.type === 'call' ? 'M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z' :
                      a.type === 'email' ? 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' :
                      a.type === 'deal' ? 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' :
                      'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z'
                    } size={14} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500 }}>{a.text}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-color-muted)', marginTop: 2 }}>{a.time}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {tab === 'notes' && (
            <div className="animate-fade">
              <textarea
                style={modalStyles.noteInput}
                placeholder="Добавить заметку..."
                value={note}
                onChange={e => setNote(e.target.value)}
              />
              <button style={{
                marginTop: 10, padding: '8px 16px', borderRadius: 7, border: 'none',
                background: 'var(--primary)', color: '#fff', fontSize: 12, fontWeight: 600,
                cursor: 'pointer', fontFamily: 'inherit',
              }}>Сохранить</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

window.ContactModal = ContactModal;
