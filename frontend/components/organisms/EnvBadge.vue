<script setup lang="ts">
// components/organisms/EnvBadge.vue
// Etiqueta de l'entorn (TEST, STAGING, LOCAL…) a dalt a l'esquerra. A test/staging/local, els
// administradors hi tenen un botó per activar/desactivar la sincronització nocturna de dades
// des de prod. El backend decideix qui hi té accés: el botó només surt si GET /coredata/db-sync/ respon.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDateTime } from '~/utils/date';

type SyncStatus = {
  env: string;
  control_dir_ok: boolean;
  nightly_enabled: boolean;
  disabled_by: string | null;
  disabled_at: string | null;
};

const TEST_ENVS = ['test', 'staging', 'local'];
const focusRing = 'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500';

const { t } = useI18n();
const toast = useToast();
const route = useRoute();
const config = useRuntimeConfig();
const { $DbSyncApiService } = useNuxtApp() as any;

const env = ((config.public.env as string) || '').trim();
const showBadge = computed(() => !!env && !['prod', 'production'].includes(env.toLowerCase()));
const isTestEnv = TEST_ENVS.includes(env.toLowerCase());

const canManage = ref(false);
const open = ref(false);
const status = ref<SyncStatus | null>(null);
const loading = ref(false);
const loadError = ref(false);
const saving = ref(false);

// Amb la sincronització desactivada, el botó porta una marca perquè es vegi que no és l'habitual.
const syncBlocked = computed(() => !!status.value && !status.value.nightly_enabled);
const settingsLabel = computed(() =>
  t(syncBlocked.value ? 'db_sync.open_settings_blocked' : 'db_sync.open_settings')
);

// Comprova si l'usuari hi té accés (admin a test/staging/local) sense mostrar cap error.
const probeAccess = async () => {
  if (!isTestEnv || canManage.value || !localStorage.getItem('auth_token')) return;
  try {
    status.value = await $DbSyncApiService.getStatus();
    canManage.value = true;
  } catch {
    canManage.value = false;
  }
};

const loadStatus = async () => {
  loading.value = true;
  try {
    status.value = await $DbSyncApiService.getStatus();
    loadError.value = false;
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
};

const openPanel = () => {
  open.value = true;
  loadStatus();
};

const closePanel = () => {
  open.value = false;
};

const toggleNightly = async () => {
  if (!status.value || saving.value) return;
  saving.value = true;
  try {
    status.value = await $DbSyncApiService.setNightlyEnabled(!status.value.nightly_enabled);
    toast.success(t(status.value!.nightly_enabled ? 'db_sync.nightly_enabled_toast' : 'db_sync.nightly_disabled_toast'));
  } catch (err: any) {
    const code = err?.response?._data?.code;
    toast.error(code ? t(`db_sync.error_${code}`) : t('db_sync.save_error'));
  } finally {
    saving.value = false;
  }
};

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && open.value) closePanel();
};

onMounted(() => {
  probeAccess();
  window.addEventListener('keydown', onKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
});

// Després d'iniciar sessió es torna a comprovar; en tancar-la, s'amaga.
watch(() => route.path, () => {
  if (!localStorage.getItem('auth_token')) {
    canManage.value = false;
    closePanel();
    return;
  }
  probeAccess();
});
</script>

<template>
  <div v-if="showBadge">
    <div
      :class="[
        'fixed top-0 left-0 z-[9999] flex items-center gap-2 text-white pl-4 pb-1 text-sm font-bold shadow-lg rounded-br-md',
        canManage ? 'pr-2' : 'pr-4',
        env.toUpperCase() === 'LOCAL' ? 'bg-green-500' : 'bg-orange-500'
      ]"
    >
      <span>{{ env.toUpperCase() }}</span>
      <button
        v-if="canManage"
        type="button"
        :class="['flex items-center gap-1 rounded p-0.5 hover:bg-white/20', focusRing]"
        :aria-label="settingsLabel"
        :title="settingsLabel"
        :aria-expanded="open"
        @click="openPanel"
      >
        <Icon name="fa6-solid:gear" class="text-xs" aria-hidden="true" />
        <span
          v-if="syncBlocked"
          class="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white text-[10px] font-black leading-none text-red-600"
          aria-hidden="true"
        >!</span>
      </button>
    </div>

    <Teleport to="body">
      <div v-if="open">
        <div class="fixed inset-0 bg-black/50 z-[10000]" aria-hidden="true" @click="closePanel" />
        <div class="fixed inset-0 z-[10001] flex items-center justify-center overflow-y-auto pointer-events-none">
          <div
            class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 my-8 relative pointer-events-auto"
            role="dialog"
            aria-modal="true"
            aria-labelledby="db-sync-title"
          >
            <button
              type="button"
              :class="['absolute top-4 right-4 text-gray-500 hover:text-gray-700 rounded', focusRing]"
              :aria-label="t('db_sync.close')"
              @click="closePanel"
            >
              <Icon name="fa6-solid:xmark" class="text-xl" aria-hidden="true" />
            </button>

            <h3 id="db-sync-title" class="text-xl font-bold text-slate-800 mb-1 pr-8 flex items-center gap-2">
              <Icon name="fa6-solid:rotate-right" class="text-slate-500" aria-hidden="true" />
              {{ t('db_sync.title') }}
            </h3>
            <p class="text-sm text-slate-500 mb-5">
              {{ t('db_sync.subtitle', { env: env.toUpperCase() }) }}
            </p>

            <!-- Càrrega -->
            <div v-if="loading && !status" class="h-24 rounded-lg bg-slate-100 animate-pulse motion-reduce:animate-none" aria-busy="true" />

            <!-- Error -->
            <div v-else-if="loadError || !status" role="alert" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {{ t('db_sync.load_error') }}
              <button type="button" :class="['ml-2 underline font-medium rounded', focusRing]" @click="loadStatus">
                {{ t('db_sync.retry') }}
              </button>
            </div>

            <div v-else class="space-y-4">
              <div v-if="!status.control_dir_ok" role="alert" class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {{ t('db_sync.error_control_dir_unavailable') }}
              </div>

              <section class="rounded-lg border border-slate-200 p-3">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <h4 id="db-sync-nightly" class="text-sm font-semibold text-slate-800">{{ t('db_sync.nightly_title') }}</h4>
                    <p class="text-xs text-slate-500 mt-0.5">{{ t('db_sync.nightly_help') }}</p>
                    <p v-if="!status.nightly_enabled && status.disabled_by" class="text-xs text-amber-700 mt-1">
                      {{ t('db_sync.disabled_by', { user: status.disabled_by, date: formatDateTime(status.disabled_at) }) }}
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    :aria-checked="status.nightly_enabled"
                    aria-labelledby="db-sync-nightly"
                    :disabled="saving || !status.control_dir_ok"
                    :class="[
                      'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full disabled:opacity-50',
                      focusRing,
                      status.nightly_enabled ? 'bg-sky-500' : 'bg-gray-300'
                    ]"
                    @click="toggleNightly"
                  >
                    <span
                      class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform motion-reduce:transition-none"
                      :class="status.nightly_enabled ? 'translate-x-6' : 'translate-x-1'"
                    />
                  </button>
                </div>
                <p class="text-xs font-medium mt-2" :class="status.nightly_enabled ? 'text-green-700' : 'text-slate-500'">
                  {{ status.nightly_enabled ? t('db_sync.nightly_on') : t('db_sync.nightly_off') }}
                </p>
              </section>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
