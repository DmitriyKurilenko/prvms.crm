<template>
  <main class="landing">
    <section class="hero surface-card fade-in-up">
      <p class="eyebrow">PRVMS CRM</p>
      <h1 class="brand-heading">CRM-платформа для продаж, договоров и коммуникаций</h1>
      <p class="lead">
        Запускайте организацию за несколько минут: зарегистрируйте компанию, пригласите команду и переходите в личный кабинет.
      </p>

      <div class="actions">
        <RouterLink to="/register">
          <PButton label="Создать организацию" />
        </RouterLink>
        <RouterLink to="/login">
          <PButton outlined label="Войти в ЛК" />
        </RouterLink>
      </div>
    </section>

    <section class="features">
      <article class="feature surface-card">
        <h3>Встроенный CRM</h3>
        <p>Сделки, этапы, задачи и контроль менеджеров в одном интерфейсе.</p>
      </article>
      <article class="feature surface-card">
        <h3>Договоры и подписание</h3>
        <p>Генерация PDF, отправка на подпись и подтверждение через OTP.</p>
      </article>
      <article class="feature surface-card">
        <h3>Каналы и телефония</h3>
        <p>Мессенджеры, звонки и аналитика в едином процессе обработки заявок.</p>
      </article>
    </section>
  </main>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  display: grid;
  gap: 20px;
  padding: 28px 16px;
  max-width: 1080px;
  margin: 0 auto;
}

.hero {
  padding: 28px;
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.lead {
  color: var(--text-muted);
  max-width: 740px;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: 18px;
  flex-wrap: wrap;
}

.features {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.feature {
  padding: 18px;
}

.feature h3 {
  margin-top: 0;
}

.feature p {
  color: var(--text-muted);
  margin-bottom: 0;
}
</style>
