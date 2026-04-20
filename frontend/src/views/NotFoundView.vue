<template>
  <div style="min-height: 100vh; display: grid; place-items: center; padding: 16px">
    <div class="surface-card" style="padding: 24px; text-align: center; max-width: 460px">
      <h1 class="brand-heading">404</h1>
      <p>Страница не найдена.</p>
      <RouterLink to="/">
        <PButton label="На главную" icon="pi pi-home" />
      </RouterLink>
    </div>
  </div>
</template>
