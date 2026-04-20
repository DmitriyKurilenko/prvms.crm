<template>
  <div class="login-page">
    <div class="surface-card login-card fade-in-up">
      <h1 class="brand-heading">CRM Platform</h1>
      <p>Вход в личный кабинет организации</p>

      <form class="form" @submit.prevent="submit">
        <PInputText v-model="email" placeholder="Email или username" />
        <PPassword v-model="password" placeholder="Пароль" :feedback="false" toggle-mask />
        <PButton :loading="auth.loading" type="submit" label="Войти" />
      </form>

      <small v-if="error" class="error">{{ error }}</small>
      <small class="hint">
        Нет аккаунта организации?
        <RouterLink to="/register">Зарегистрироваться</RouterLink>
      </small>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const email = ref('')
const password = ref('')
const error = ref('')

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const submit = async () => {
  error.value = ''
  try {
    await auth.login(email.value, password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/app'
    await router.push(redirect)
  } catch {
    error.value = 'Не удалось войти. Проверьте логин и пароль.'
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 16px;
  background: var(--bg);
}

.login-card {
  width: min(440px, 100%);
  padding: 32px;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

.login-card h1 {
  margin-bottom: 6px;
}

p {
  color: var(--text-muted);
}

.form {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.error {
  color: var(--danger);
  margin-top: 10px;
  display: block;
}

.hint {
  display: block;
  margin-top: 8px;
  color: var(--text-muted);
}
</style>
