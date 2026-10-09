<script setup>
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
const { t, locale } = useI18n();

definePageMeta({
  layout: 'auth',
  title: 'Login',
});

const config = useRuntimeConfig();
const apiHost = config.public.apiHost;

const username = ref('');
const password = ref('');
const error_message = ref('');
const error_type = ref('error'); // 'error' | 'warning' | 'connection'
const router = useRouter();
const route = useRoute();
const loading = ref(false);

/**
 * Determina el missatge d'error a partir del codi HTTP i el cos de la resposta.
 * Codis possibles del backend:
 *   200 → Login correcte (retorna username + token)
 *   400 → Credencials incorrectes, camps buits, usuari inactiu
 *   405 → Mètode HTTP incorrecte (no és POST)
 *   415 → Content-Type no suportat
 */
const resolveLoginError = (err) => {
  const status = err?.status ?? err?.response?.status ?? null;

  if (status === 400) {
    const data = err?.data ?? {};

    // Usuari inactiu
    if (
      (data?.non_field_errors && String(data.non_field_errors).toLowerCase().includes('inactive')) ||
      (data?.detail && String(data.detail).toLowerCase().includes('inactive'))
    ) {
      error_type.value = 'warning';
      return t('dashboard.login_inactive_user');
    }

    // Camps buits (el backend retorna errors de validació per camp)
    const hasEmptyFieldError =
      data?.username?.length > 0 ||
      data?.password?.length > 0;
    if (hasEmptyFieldError) {
      error_type.value = 'warning';
      return t('dashboard.login_empty_fields');
    }

    // Credencials incorrectes (cas genèric 400)
    error_type.value = 'warning';
    return t('dashboard.login_wrong');
  }

  if (status === 405) {
    error_type.value = 'error';
    return t('dashboard.login_method_not_allowed');
  }

  if (status === 415) {
    error_type.value = 'error';
    return t('dashboard.login_unsupported_media');
  }

  // Sense connexió / servidor no assolible
  if (!status || String(err).indexOf('<no response>') > -1) {
    error_type.value = 'connection';
    return t('dashboard.login_fail');
  }

  // Qualsevol altre error de servidor no previst
  error_type.value = 'error';
  return t('dashboard.login_server_error');
};

const login = async () => {
  try {
    loading.value = true;
    error_message.value = '';
    error_type.value = 'error';

    const response = await $fetch(apiHost + '/auth/login/', {
      method: 'POST',
      body: {
        username: username.value,
        password: password.value,
      },
    }).catch((err) => {
      console.error('Error during login:', err);
      error_message.value = resolveLoginError(err);
      loading.value = false;
    });

    loading.value = false;

    if (typeof response === 'undefined') {
      return;
    }

    const token = response.token;

    localStorage.setItem('auth_token', token);
    localStorage.setItem('user_username', username.value);
    document.cookie = `auth_token=${token}; path=/`;

    // Torna a la ruta que s'intentava obrir abans del login (la desa `auth.global.ts` a
    // `?redirect=`), i si no n'hi ha, a la pàgina principal. Només s'accepten rutes internes:
    // ha de començar per una sola barra, per no convertir el login en un redirector obert.
    const redirect = route.query.redirect;
    const isInternal = typeof redirect === 'string' && /^\/(?!\/)/.test(redirect);
    router.push(isInternal ? redirect : '/');

  } catch (error) {
    console.error('Error during login:', error);
    error_message.value = resolveLoginError(error);
    loading.value = false;
  }
};

onMounted(() => {
  getLanguage();
});

const getLanguage = () => {
  locale.value = config.public.defaultLocale;
  localStorage.setItem('preferred_language', locale.value);
};
</script>

<template>
  <div class="flex min-h-full flex-col justify-center px-6 py-12 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-sm">
      <h2 class="mt-10 text-center text-2xl font-bold leading-9 tracking-tight text-gray-900">
        {{ $t('dashboard.intro_login') }}
      </h2>
    </div>

    <div class="mt-10 sm:mx-auto sm:w-full sm:max-w-sm">

      <!-- Bloc d'error: estil canvia segons el tipus d'error -->
      <div
        v-if="error_message"
        role="alert"
        class="flex items-start gap-3 px-4 py-3 rounded-lg border mb-4 text-sm"
        :class="{
          'bg-red-50 border-red-300 text-red-800':   error_type === 'error',
          'bg-amber-50 border-amber-300 text-amber-800': error_type === 'warning',
          'bg-slate-50 border-slate-300 text-slate-700': error_type === 'connection',
        }"
      >
        <!-- Icona segons el tipus -->
        <span class="mt-0.5 text-lg leading-none select-none" aria-hidden="true">
          <template v-if="error_type === 'warning'"><Icon name="fa6-solid:triangle-exclamation" class="w-3.5 h-3.5" /></template>
          <template v-else-if="error_type === 'connection'"><Icon name="fa6-solid:plug" class="w-3.5 h-3.5" /></template>
          <template v-else><Icon name="fa6-solid:xmark" class="w-3.5 h-3.5" /></template>
        </span>
        <span>{{ error_message }}</span>
      </div>

      <form class="space-y-6" @submit.prevent="login">
        <div>
          <label for="username" class="block text-sm font-medium leading-6 text-gray-900">
            {{ $t('user') }}
          </label>
          <div class="mt-2">
            <input
              id="username"
              type="text"
              v-model="username"
              :placeholder="$t('user')"
              required="required"
              autocomplete="username"
              class="block w-full rounded-md border-0 p-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
            />
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between">
            <label for="password" class="block text-sm font-medium leading-6 text-gray-900">
              {{ $t('common.password') }}
            </label>
          </div>
          <div class="mt-2">
            <input
              id="password"
              type="password"
              v-model="password"
              :placeholder="$t('common.password')"
              required="required"
              autocomplete="current-password"
              class="block w-full rounded-md border-0 p-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
            />
          </div>
        </div>

        <div>
          <button
            type="submit"
            :disabled="loading"
            class="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <span v-if="loading" class="spinner-border spinner-border-sm mr-2" role="status" aria-hidden="true"></span>
            {{ loading ? $t('common.loading') : $t('dashboard.enter') }}
          </button>
        </div>
      </form>

    </div>
  </div>
</template>
