/* Tasks Screen */
const taskCategories = [
  { id: 'today', label: 'Сегодня', count: 5 },
  { id: 'tomorrow', label: 'Завтра', count: 3 },
  { id: 'week', label: 'На неделе', count: 8 },
  { id: 'overdue', label: 'Просрочено', count: 2 },
];

const allTasks = [
  { id: 1, text: 'Позвонить ООО «ТехСтарт» — обсудить условия', time: '10:00', cat: 'today', done: true, priority: 'high', assignee: 'АИ', deal: 'Автоматизация склада' },
  { id: 2, text: 'Подготовить КП для АО «ПромГрупп»', time: '12:00', cat: 'today', done: true, priority: 'medium', assignee: 'АИ', deal: 'Модернизация IT' },
  { id: 3, text: 'Встреча с командой продаж', time: '14:00', cat: 'today', done: false, priority: 'medium', assignee: 'АИ', deal: null },
  { id: 4, text: 'Обновить CRM-карточки клиентов', time: '16:00', cat: 'today', done: false, priority: 'low', assignee: 'АИ', deal: null },
  { id: 5, text: 'Отправить отчёт руководству', time: '17:30', cat: 'today', done: false, priority: 'high', assignee: 'АИ', deal: null },
  { id: 6, text: 'Презентация для СберТех', time: '10:00', cat: 'tomorrow', done: false, priority: 'high', assignee: 'АИ', deal: 'ERP-интеграция' },
  { id: 7, text: 'Согласовать договор с юристом', time: '14:00', cat: 'tomorrow', done: false, priority: 'medium', assignee: 'ОК', deal: 'Поддержка 1С' },
  { id: 8, text: 'Демо CRM для нового клиента', time: '16:00', cat: 'tomorrow', done: false, priority: 'low', assignee: 'АИ', deal: null },
  { id: 9, text: 'Финальное КП ООО «Ресурс»', time: '—', cat: 'week', done: false, priority: 'medium', assignee: 'АИ', deal: null },
  { id: 10, text: 'Провести обучение менеджеров', time: '—', cat: 'week', done: false, priority: 'low', assignee: 'ОК', deal: null },
  { id: 11, text: 'Ответить на запрос ИП Козлов', time: 'просрочено 2д', cat: 'overdue', done: false, priority: 'high', assignee: 'АИ', deal: 'Облачная миграция' },
  { id: 12, text: 'Обновить прайс-лист', time: 'просрочено 1д', cat: 'overdue', done: false, priority: 'medium', assignee: 'АИ', deal: null },
];

const taskStyles = {
  layout: { display: 'grid', gridTemplateColumns: '220px 1fr', gap: 24 },
  sidebar: {
    background: '#fff', borderRadius: 'var(--radius-md)',
    border: '1px solid var(--surface-border)', padding: 8,
    alignSelf: 'start',
  },
  catItem: (active) => ({
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '10px 12px', borderRadius: 8, cursor: 'pointer',
    background: active ? 'var(--primary-lighter)' : 'transparent',
    color: active ? 'var(--primary)' : 'var(--text-color-secondary)',
    fontWeight: active ? 600 : 500, fontSize: 13,
    transition: 'all 0.15s',
  }),
  catCount: (active) => ({
    background: active ? 'var(--primary)' : 'var(--surface-hover)',
    color: active ? '#fff' : 'var(--text-color-muted)',
    borderRadius: 10, padding: '1px 8px', fontSize: 11, fontWeight: 700,
  }),
  main: {},
  taskCard: {
    background: '#fff', borderRadius: 'var(--radius-md)',
    border: '1px solid var(--surface-border)', overflow: 'hidden',
  },
  taskRow: (hovered, done) => ({
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '12px 20px',
    borderBottom: '1px solid var(--surface-border)',
    background: hovered ? 'var(--surface-hover)' : 'transparent',
    cursor: 'pointer', transition: 'background 0.1s',
    opacity: done ? 0.5 : 1,
  }),
  checkbox: (done) => ({
    width: 22, height: 22, borderRadius: 6, flexShrink: 0,
    border: done ? 'none' : '2px solid var(--surface-border)',
    background: done ? 'var(--green-500)' : '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer',
    transition: 'all 0.15s',
  }),
  taskText: (done) => ({
    flex: 1, fontSize: 13, fontWeight: 500,
    textDecoration: done ? 'line-through' : 'none',
  }),
  taskMeta: { display: 'flex', gap: 10, alignItems: 'center', fontSize: 12 },
  priorityTag: (p) => ({
    padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700,
    background: p === 'high' ? 'var(--red-50)' : p === 'medium' ? 'var(--orange-50)' : 'var(--surface-hover)',
    color: p === 'high' ? 'var(--red-500)' : p === 'medium' ? 'var(--orange-500)' : 'var(--text-color-muted)',
  }),
  dealTag: {
    padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
    background: 'var(--primary-lighter)', color: 'var(--primary)',
  },
  timeTag: (overdue) => ({
    fontSize: 12, color: overdue ? 'var(--red-500)' : 'var(--text-color-muted)', fontWeight: 500,
    minWidth: 60, textAlign: 'right',
  }),
  miniAvatar: {
    width: 22, height: 22, borderRadius: '50%',
    background: 'var(--primary)', color: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 9, fontWeight: 700,
  },
};

function TasksScreen() {
  const [activeCat, setActiveCat] = React.useState('today');
  const [tasks, setTasks] = React.useState(allTasks);
  const [hoveredRow, setHoveredRow] = React.useState(null);

  const filtered = tasks.filter(t => t.cat === activeCat);
  const toggleDone = (id) => setTasks(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t));

  return (
    <div className="animate-fade">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Задачи</h1>
          <p style={{ fontSize: 14, color: 'var(--text-color-secondary)' }}>
            {tasks.filter(t => !t.done).length} активных задач
          </p>
        </div>
        <button style={{
          padding: '9px 18px', borderRadius: 8, border: 'none',
          background: 'var(--primary)', color: '#fff', fontSize: 13, fontWeight: 600,
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'inherit',
        }}>
          <SvgIcon d="M12 4v16m8-8H4" size={15} />
          Новая задача
        </button>
      </div>

      <div style={taskStyles.layout}>
        <div style={taskStyles.sidebar}>
          {taskCategories.map(cat => {
            const count = tasks.filter(t => t.cat === cat.id && !t.done).length;
            return (
              <div key={cat.id} style={taskStyles.catItem(activeCat === cat.id)} onClick={() => setActiveCat(cat.id)}>
                <span>{cat.label}</span>
                <span style={taskStyles.catCount(activeCat === cat.id)}>{count}</span>
              </div>
            );
          })}
        </div>

        <div style={taskStyles.main}>
          <div style={taskStyles.taskCard}>
            {filtered.length === 0 && (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-color-muted)', fontSize: 14 }}>
                Нет задач в этой категории
              </div>
            )}
            {filtered.map(t => (
              <div key={t.id} style={taskStyles.taskRow(hoveredRow === t.id, t.done)}
                onMouseEnter={() => setHoveredRow(t.id)}
                onMouseLeave={() => setHoveredRow(null)}
              >
                <div style={taskStyles.checkbox(t.done)} onClick={() => toggleDone(t.id)}>
                  {t.done && '✓'}
                </div>
                <div style={taskStyles.taskText(t.done)}>{t.text}</div>
                <div style={taskStyles.taskMeta}>
                  {t.deal && <span style={taskStyles.dealTag}>{t.deal}</span>}
                  <span style={taskStyles.priorityTag(t.priority)}>
                    {t.priority === 'high' ? 'Высокий' : t.priority === 'medium' ? 'Средний' : 'Низкий'}
                  </span>
                  <div style={taskStyles.miniAvatar}>{t.assignee}</div>
                </div>
                <span style={taskStyles.timeTag(t.cat === 'overdue')}>{t.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.TasksScreen = TasksScreen;
