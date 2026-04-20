<template>
  <div class="invite-page">
    <div class="surface-card invite-card fade-in-up">
      <h1 class="brand-heading">CRM Platform</h1>

      <div v-if="loading" class="loading-state">
        <PProgressSpinner style="width: 40px; height: 40px" />
        <p>Проверяем приглашение…</p>
      </div>

      <div v-else-if="errorMsg" class="error-state">
        <p class="error">{{ errorMsg }}</p>
        <RouterLink to="/login">Войти в систему</RouterLink>
      </div>

      <template v-else-if="invite">
        <p>
          Вас пригласили в организацию <strong>{{ invite.org_name }}</strong>
          с ролью <strong>{{ roleLabel }}</strong>.
        </p>

        <form class="form" @submit.prevent="submit">
          <PInputText :model-value="invite.email" disabled />

          <template v-if="!invite.has_account">
            <PInputText v-model="username" placeholder="Имя пользователя" />
          </template>
          <PPassword
            v-model="password"
            :placeholder="invite.has_account ? 'Пароль текущего аккаунта' : 'Пароль'"
            :feedback="!invite.has_account"
            toggle-mask
          />

          <small v-if="submitError" class="error">{{ submitError }}</small>

          <PButton
            :loading="submitting"
            type="submit"
            :disabled="!password.trim()"
            :label="invite.has_account ? 'Подтвердить и принять' : 'Создать аккаунт и принять'"
          />
        </form>

        <small v-if="invite.has_account" class="hint">
          У вас уже есть аккаунт. Подтвердите пароль, чтобы присоединиться к организации.
        </small>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { checkInvite, acceptInvite, type InviteInfo } from '@/api/auth'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const errorMsg = ref('')
const invite = ref<InviteInfo | null>(null)
const username = ref('')
const password = ref('')
const submitting = ref(false)
const submitError = ref('')

const roleLabels: Record<string, string> = {
  owner: 'Владелец',
  admin: 'Администратор',
  manager: 'Менеджер',
  viewer: 'Наблюдатель',
}

const roleLabel = computed(() => {
  if (!invite.value) return ''
  return roleLabels[invite.value.role] || invite.value.role
})

const token = computed(() => {
  const t = route.query.token
  return typeof t === 'string' ? t : ''
})

onMounted(async () => {
  if (!token.value) {
    errorMsg.value = 'Токен приглашения отсутствует'
    loading.value = false
    return
  }
  try {
    invite.value = await checkInvite(token.value)
  } catch (err: any) {
    errorMsg.value = err?.data?.detail || 'Не удалось проверить приглашение'
  } finally {
    loading.value = false
  }
})

const submit = async () => {
  submitError.value = ''
  submitting.value = true
  try {
    await acceptInvite({
      token: token.value,
      password: password.value,
      ...(invite.value?.has_account ? {} : { username: username.value }),
    })
    await router.push('/app')
  } catch (err: any) {
    submitError.value = err?.data?.detail || 'Не удалось принять приглашение'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.invite-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 16px;
}

.invite-card {
  width: min(440px, 100%);
  padding: 24px;
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
  display: block;
}

.error-state {
  text-align: center;
  margin-top: 16px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.hint {
  display: block;
  margin-top: 8px;
  color: var(--text-muted);
}
</style>
