<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { onKeyStroke } from '@vueuse/core';
import H1 from '~/components/atoms/H1.vue';

const { t } = useI18n();
const toast = useToast();
const config = useRuntimeConfig();

// La Lecturapp crida `${URL}/lecturapp/...`, i el backend munta l'app `lecturapp` a l'arrel de l'API,
// així que la URL que cal posar a l'app és la mateixa apiHost d'aquesta instal·lació (sense barra final).
const apiUrl = computed(() => {
  const host = String(config.public.apiHost || '').trim();
  try {
    return new URL(host, window.location.origin).href.replace(/\/+$/, '');
  } catch {
    return host.replace(/\/+$/, '');
  }
});

const installation = computed(() => window.location.host);

const copyUrl = async () => {
  try {
    await navigator.clipboard.writeText(apiUrl.value);
    toast.success(t('lecturapp_help.url_copied'));
  } catch {
    toast.error(t('common.error'));
  }
};

// Comprovem que l'endpoint de la Lecturapp respon: sense token, validate-token retorna un JSON
// amb `success: false` (400). Qualsevol resposta d'aquest tipus vol dir que la URL és correcta.
const checkStatus = ref(null); // null | 'checking' | 'ok' | 'error'
const checkConnection = async () => {
  checkStatus.value = 'checking';
  try {
    const response = await fetch(`${apiUrl.value}/lecturapp/auth/validate-token/`);
    const data = await response.json().catch(() => null);
    checkStatus.value = data && 'success' in data ? 'ok' : 'error';
  } catch {
    checkStatus.value = 'error';
  }
};

onMounted(() => {
  checkConnection();
});

// Captures de l'app (public/images/lecturapp). Són les mateixes per a tots els clients.
const screenshots = {
  login: { src: '/images/lecturapp/01-login.jpg', caption: 'lecturapp_help.cap_login' },
  config: { src: '/images/lecturapp/02-config-url.jpg', caption: 'lecturapp_help.cap_config' },
  loginOk: { src: '/images/lecturapp/03-login-ok.jpg', caption: 'lecturapp_help.cap_login_ok' },
  lots: { src: '/images/lecturapp/04-lots.jpg', caption: 'lecturapp_help.cap_lots' },
  lot: { src: '/images/lecturapp/05-lot.jpg', caption: 'lecturapp_help.cap_lot' },
  finca: { src: '/images/lecturapp/06-finca.jpg', caption: 'lecturapp_help.cap_finca' },
  lectura: { src: '/images/lecturapp/07-lectura.jpg', caption: 'lecturapp_help.cap_lectura' },
  incidencia: { src: '/images/lecturapp/08-incidencia.jpg', caption: 'lecturapp_help.cap_incidencia' },
};
const appShots = [screenshots.login, screenshots.config, screenshots.loginOk];
const useShots = [screenshots.lots, screenshots.lot, screenshots.finca, screenshots.lectura, screenshots.incidencia];

const enlarged = ref(null);
onKeyStroke('Escape', () => { enlarged.value = null; });
</script>

<template>
  <div id="wrapper" class="text-base max-w-4xl">
    <div class="flex justify-between items-center mb-2">
      <H1 class="mb-2">{{ $t('lecturapp_help.title') }}</H1>
    </div>
    <p class="text-slate-600 mb-6">{{ $t('lecturapp_help.intro') }}</p>

    <!-- URL de configuració -->
    <section class="mb-8 p-4 rounded-lg border border-sky-200 bg-sky-50">
      <h2 class="font-semibold text-slate-700 mb-1">{{ $t('lecturapp_help.url_title') }}</h2>
      <p class="text-sm text-slate-600 mb-3">{{ $t('lecturapp_help.url_desc') }}</p>
      <div class="flex flex-wrap items-center gap-2">
        <code class="flex-1 min-w-0 break-all px-3 py-2 rounded-md bg-white border border-slate-300 text-lg font-mono text-slate-800 select-all">{{ apiUrl }}</code>
        <button type="button" class="button-primary flex items-center gap-2" @click="copyUrl">
          <Icon name="fa6-solid:copy" />
          {{ $t('lecturapp_help.copy') }}
        </button>
      </div>
      <div class="flex flex-wrap items-center gap-3 mt-3 text-sm">
        <span class="text-slate-500">{{ $t('lecturapp_help.installation') }}: <span class="font-medium text-slate-700">{{ installation }}</span></span>
        <span v-if="checkStatus === 'checking'" class="flex items-center gap-1 text-slate-500">
          <Icon name="fa6-solid:spinner" class="animate-spin" /> {{ $t('lecturapp_help.checking') }}
        </span>
        <span v-else-if="checkStatus === 'ok'" class="flex items-center gap-1 text-green-700">
          <Icon name="fa6-solid:circle-check" /> {{ $t('lecturapp_help.check_ok') }}
        </span>
        <span v-else-if="checkStatus === 'error'" class="flex items-center gap-1 text-red-600">
          <Icon name="fa6-solid:triangle-exclamation" /> {{ $t('lecturapp_help.check_error') }}
        </span>
        <button v-if="checkStatus !== 'checking'" type="button" class="px-2 py-1 hover:bg-sky-100 rounded text-sky-600"
          @click="checkConnection">
          <Icon name="fa6-solid:rotate-right" /> {{ $t('lecturapp_help.check_again') }}
        </button>
      </div>
      <ul class="mt-3 text-sm text-slate-600 list-disc pl-5 space-y-1">
        <li>{{ $t('lecturapp_help.url_note_exact') }}</li>
        <li>{{ $t('lecturapp_help.url_note_no_suffix') }}</li>
      </ul>
    </section>

    <!-- 1. Configurar l'app -->
    <section class="mb-8">
      <h2 class="font-semibold text-slate-700 mb-2">1. {{ $t('lecturapp_help.step_app_title') }}</h2>
      <ol class="list-decimal pl-6 space-y-1 text-slate-700">
        <li>{{ $t('lecturapp_help.step_app_1') }}</li>
        <li>{{ $t('lecturapp_help.step_app_2') }} <Icon name="fa6-solid:gear" class="text-slate-500" /></li>
        <li>{{ $t('lecturapp_help.step_app_3') }}</li>
        <li>{{ $t('lecturapp_help.step_app_4') }}</li>
      </ol>
      <div class="flex flex-wrap gap-4 mt-4">
        <figure v-for="shot in appShots" :key="shot.src" class="w-40">
          <button type="button" class="block w-full rounded-lg overflow-hidden border border-slate-200 shadow-sm hover:shadow-md hover:border-sky-300 transition"
            :title="$t('lecturapp_help.enlarge')" @click="enlarged = shot">
            <img :src="shot.src" :alt="$t(shot.caption)" loading="lazy" class="w-full" />
          </button>
          <figcaption class="text-xs text-slate-500 text-center mt-1">{{ $t(shot.caption) }}</figcaption>
        </figure>
      </div>
    </section>

    <!-- 2. Usuari Lecturapp -->
    <section class="mb-8">
      <h2 class="font-semibold text-slate-700 mb-2">2. {{ $t('lecturapp_help.step_user_title') }}</h2>
      <ol class="list-decimal pl-6 space-y-1 text-slate-700">
        <li>
          {{ $t('lecturapp_help.step_user_1') }}
          <NuxtLink to="/order/operators/" class="text-sky-500 underline hover:no-underline">{{ $t('common.operators') }}</NuxtLink>.
        </li>
        <li>{{ $t('lecturapp_help.step_user_2') }}</li>
        <li>{{ $t('lecturapp_help.step_user_3') }}</li>
      </ol>
    </section>

    <!-- 3. Lot de lectures -->
    <section class="mb-8">
      <h2 class="font-semibold text-slate-700 mb-2">3. {{ $t('lecturapp_help.step_batch_title') }}</h2>
      <ol class="list-decimal pl-6 space-y-1 text-slate-700">
        <li>
          {{ $t('lecturapp_help.step_batch_1') }}
          <NuxtLink to="/reading/reading-batches/add" class="text-sky-500 underline hover:no-underline">{{ $t('billing_block.new_reading_batch') }}</NuxtLink>.
        </li>
        <li>{{ $t('lecturapp_help.step_batch_2') }}</li>
        <li>{{ $t('lecturapp_help.step_batch_3') }}</li>
        <li>{{ $t('lecturapp_help.step_batch_4') }}</li>
      </ol>
    </section>

    <!-- 4. Ús de l'app -->
    <section class="mb-8">
      <h2 class="font-semibold text-slate-700 mb-2">4. {{ $t('lecturapp_help.step_use_title') }}</h2>
      <ol class="list-decimal pl-6 space-y-1 text-slate-700">
        <li>{{ $t('lecturapp_help.use_1') }}</li>
        <li>{{ $t('lecturapp_help.use_2') }}</li>
        <li>{{ $t('lecturapp_help.use_3') }}</li>
        <li>{{ $t('lecturapp_help.use_4') }}</li>
        <li>{{ $t('lecturapp_help.use_5') }}</li>
      </ol>
      <p class="mt-3 text-sm text-slate-600 flex items-start gap-2">
        <Icon name="fa6-solid:rotate" class="text-sky-500 mt-0.5 shrink-0" />
        {{ $t('lecturapp_help.use_sync') }}
      </p>
      <div class="flex flex-wrap gap-4 mt-4">
        <figure v-for="shot in useShots" :key="shot.src" class="w-40">
          <button type="button" class="block w-full rounded-lg overflow-hidden border border-slate-200 shadow-sm hover:shadow-md hover:border-sky-300 transition"
            :title="$t('lecturapp_help.enlarge')" @click="enlarged = shot">
            <img :src="shot.src" :alt="$t(shot.caption)" loading="lazy" class="w-full" />
          </button>
          <figcaption class="text-xs text-slate-500 text-center mt-1">{{ $t(shot.caption) }}</figcaption>
        </figure>
      </div>
    </section>

    <!-- Problemes habituals -->
    <section class="mb-8">
      <h2 class="font-semibold text-slate-700 mb-2">{{ $t('lecturapp_help.troubleshooting_title') }}</h2>
      <ul class="list-disc pl-6 space-y-1 text-slate-700">
        <li>{{ $t('lecturapp_help.trouble_login') }}</li>
        <li>{{ $t('lecturapp_help.trouble_no_batches') }}</li>
        <li>{{ $t('lecturapp_help.trouble_change_client') }}</li>
      </ul>
    </section>
  </div>

  <!-- Captura ampliada -->
  <div v-if="enlarged" class="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
    @click="enlarged = null">
    <figure class="max-h-full flex flex-col items-center" @click.stop>
      <img :src="enlarged.src" :alt="$t(enlarged.caption)" class="max-h-[85vh] w-auto rounded-lg shadow-2xl" />
      <figcaption class="text-white text-sm mt-2">{{ $t(enlarged.caption) }}</figcaption>
    </figure>
    <button type="button" class="absolute top-4 right-4 text-white text-2xl p-2 hover:text-slate-300"
      @click="enlarged = null"><Icon name="fa6-solid:xmark" /></button>
  </div>
</template>
