<script setup>
// Pàgina de l'enllaç del correu de recuperació (sense sessió): comprova l'enllaç i deixa triar
// la contrasenya nova, amb els mateixos requisits i barra de fortalesa que el perfil.
import { ref, computed, onMounted } from 'vue';
import { usePasswordRules } from '~/composables/usePasswordRules';
import PasswordRequirements from '~/components/molecules/PasswordRequirements.vue';

definePageMeta({
  layout: 'auth',
  title: 'Reset password',
});

const { t, locale } = useI18n();
const config = useRuntimeConfig();
const route = useRoute();

const uid = typeof route.query.uid === 'string' ? route.query.uid : '';
const token = typeof route.query.token === 'string' ? route.query.token : '';

// 'checking' | 'invalid' | 'form' | 'done' | 'check_error'
const state = ref('checking');
const strictRules = ref(false);
const newPassword = ref('');
const repeatPassword = ref('');
const saving = ref(false);
const attemptedSave = ref(false);
const errorMessage = ref('');

const { rules, rulesOk, strength } = usePasswordRules(newPassword, { strict: strictRules });
const passwordsMatch = computed(() => newPassword.value === repeatPassword.value);
const showMismatch = computed(() => !!repeatPassword.value && !passwordsMatch.value);

const inputCls = 'block w-full rounded-md border-0 p-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6';

const confirmRequest = (body) => $fetch(config.public.apiHost + '/auth/password-reset/confirm/', {
  method: 'POST',
  body: { uid, token, ...body },
  headers: { 'Accept-Language': locale.value },
});

const checkLink = async () => {
  if (!uid || !token) {
    state.value = 'invalid';
    return;
  }
  try {
    const response = await confirmRequest({});
    strictRules.value = !!response?.strict_rules;
    state.value = response?.valid ? 'form' : 'invalid';
  } catch (error) {
    console.error('Error checking password reset link:', error);
    state.value = 'check_error';
  }
};

// Missatges del backend (enllaç caducat, requisits...) en un sol text
const backendMessage = (error) => {
  const data = error?.data;
  if (data && typeof data === 'object') {
    const messages = Object.values(data).flat().filter(m => typeof m === 'string');
    if (messages.length) return messages.join(' ');
  }
  return '';
};

const save = async () => {
  attemptedSave.value = true;
  errorMessage.value = '';
  if (!rulesOk.value || !passwordsMatch.value) return;
  saving.value = true;
  try {
    await confirmRequest({ new_password: newPassword.value });
    state.value = 'done';
  } catch (error) {
    console.error('Error resetting password:', error);
    if (error?.data?.token) {
      state.value = 'invalid';
    } else {
      errorMessage.value = backendMessage(error) || t('password_reset.request_error');
    }
  } finally {
    saving.value = false;
  }
};

onMounted(checkLink);
</script>

<template>
  <div class="flex min-h-full flex-col justify-center px-6 py-12 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-sm">
      <h2 class="mt-10 text-center text-2xl font-bold leading-9 tracking-tight text-gray-900">
        {{ $t('password_reset.new_password_title') }}
      </h2>
    </div>

    <div class="mt-10 sm:mx-auto sm:w-full sm:max-w-sm">
      <p v-if="state === 'checking'" class="text-center text-sm text-gray-500">
        <Icon name="fa6-solid:spinner" class="animate-spin mr-2" aria-hidden="true" />{{ $t('common.loading') }}
      </p>

      <!-- Enllaç no vàlid, caducat o ja fet servir -->
      <template v-else-if="state === 'invalid' || state === 'check_error'">
        <div role="alert"
          class="flex items-start gap-3 px-4 py-3 rounded-lg border mb-4 text-sm bg-amber-50 border-amber-300 text-amber-800">
          <Icon name="fa6-solid:triangle-exclamation" class="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
          <span>{{ state === 'invalid' ? $t('password_reset.invalid_link') : $t('password_reset.request_error') }}</span>
        </div>
        <p class="text-center text-sm">
          <NuxtLink to="/auth/forgot-password" class="font-semibold text-indigo-600 hover:text-indigo-500">
            {{ $t('password_reset.request_new_link') }}
          </NuxtLink>
        </p>
      </template>

      <!-- Fet -->
      <template v-else-if="state === 'done'">
        <div role="status"
          class="flex items-start gap-3 px-4 py-3 rounded-lg border mb-6 text-sm bg-green-50 border-green-300 text-green-800">
          <Icon name="fa6-solid:circle-check" class="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
          <span>{{ $t('password_reset.done') }}</span>
        </div>
        <NuxtLink to="/auth/login"
          class="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500">
          {{ $t('password_reset.back_to_login') }}
        </NuxtLink>
      </template>

      <!-- Formulari -->
      <form v-else class="space-y-6" @submit.prevent="save">
        <div v-if="errorMessage" role="alert"
          class="flex items-start gap-3 px-4 py-3 rounded-lg border text-sm bg-red-50 border-red-300 text-red-800">
          <Icon name="fa6-solid:xmark" class="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
          <span>{{ errorMessage }}</span>
        </div>

        <div>
          <label for="new-password" class="block text-sm font-medium leading-6 text-gray-900">{{ $t('user_group.new_password') }}</label>
          <div class="mt-2">
            <input id="new-password" v-model="newPassword" type="password" autocomplete="new-password" required
              :class="[inputCls, { 'ring-red-400': attemptedSave && !rulesOk }]" />
          </div>
          <PasswordRequirements :rules="rules" :strength="strength" />
        </div>

        <div>
          <label for="repeat-password" class="block text-sm font-medium leading-6 text-gray-900">{{ $t('user_group.repeat_password') }}</label>
          <div class="mt-2">
            <input id="repeat-password" v-model="repeatPassword" type="password" autocomplete="new-password" required
              :class="[inputCls, { 'ring-red-400': (attemptedSave && !passwordsMatch) || showMismatch }]" />
          </div>
          <p v-if="showMismatch" class="mt-1 text-sm text-red-600">{{ $t('user_group.password_not_match') }}</p>
        </div>

        <button type="submit" :disabled="saving"
          class="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-60 disabled:cursor-not-allowed">
          <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin mr-2 self-center" />
          {{ $t('password_reset.save_password') }}
        </button>
      </form>
    </div>
  </div>
</template>
