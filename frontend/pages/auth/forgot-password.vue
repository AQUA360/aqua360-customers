<script setup>
// Recuperació de la contrasenya (sense sessió): l'usuari escriu el seu nom d'usuari i, si es
// pot, rep un correu amb un enllaç per triar-ne una de nova. Si no es pot (no té correu,
// l'empresa no té el correu configurat...), se li demana que s'adreci a l'administrador.
import { ref } from 'vue';

definePageMeta({
  layout: 'auth',
  title: 'Forgot password',
});

const { t, locale } = useI18n();
const config = useRuntimeConfig();
const route = useRoute();

const username = ref(typeof route.query.username === 'string' ? route.query.username : '');
const loading = ref(false);
// null | 'sent' | 'unavailable' | 'error'
const result = ref(null);

const submit = async () => {
  if (!username.value.trim()) return;
  loading.value = true;
  result.value = null;
  try {
    const response = await $fetch(config.public.apiHost + '/auth/password-reset/', {
      method: 'POST',
      body: { username: username.value.trim() },
      headers: { 'Accept-Language': locale.value },
    });
    result.value = response?.status === 'sent' ? 'sent' : 'unavailable';
  } catch (error) {
    console.error('Error requesting password reset:', error);
    result.value = 'error';
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="flex min-h-full flex-col justify-center px-6 py-12 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-sm">
      <h2 class="mt-10 text-center text-2xl font-bold leading-9 tracking-tight text-gray-900">
        {{ $t('password_reset.title') }}
      </h2>
      <p class="mt-2 text-center text-sm text-gray-500">{{ $t('password_reset.request_help') }}</p>
    </div>

    <div class="mt-10 sm:mx-auto sm:w-full sm:max-w-sm">
      <!-- Correu enviat -->
      <div v-if="result === 'sent'" role="status"
        class="flex items-start gap-3 px-4 py-3 rounded-lg border mb-4 text-sm bg-green-50 border-green-300 text-green-800">
        <Icon name="fa6-solid:envelope-circle-check" class="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
        <span>{{ $t('password_reset.sent') }}</span>
      </div>

      <!-- No es pot enviar: cal l'administrador -->
      <div v-else-if="result === 'unavailable'" role="alert"
        class="flex items-start gap-3 px-4 py-3 rounded-lg border mb-4 text-sm bg-amber-50 border-amber-300 text-amber-800">
        <Icon name="fa6-solid:triangle-exclamation" class="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
        <span>{{ $t('password_reset.unavailable') }}</span>
      </div>

      <!-- Error de connexió o massa intents -->
      <div v-else-if="result === 'error'" role="alert"
        class="flex items-start gap-3 px-4 py-3 rounded-lg border mb-4 text-sm bg-red-50 border-red-300 text-red-800">
        <Icon name="fa6-solid:xmark" class="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
        <span>{{ $t('password_reset.request_error') }}</span>
      </div>

      <form v-if="result !== 'sent'" class="space-y-6" @submit.prevent="submit">
        <div>
          <label for="username" class="block text-sm font-medium leading-6 text-gray-900">{{ $t('user') }}</label>
          <div class="mt-2">
            <input id="username" v-model="username" type="text" :placeholder="$t('user')" required
              autocomplete="username"
              class="block w-full rounded-md border-0 p-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6" />
          </div>
        </div>

        <button type="submit" :disabled="loading || !username.trim()"
          class="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-60 disabled:cursor-not-allowed">
          <Icon v-if="loading" name="fa6-solid:spinner" class="animate-spin mr-2 self-center" />
          {{ $t('password_reset.send_link') }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm">
        <NuxtLink to="/auth/login" class="font-semibold text-indigo-600 hover:text-indigo-500">
          {{ $t('password_reset.back_to_login') }}
        </NuxtLink>
      </p>
    </div>
  </div>
</template>
