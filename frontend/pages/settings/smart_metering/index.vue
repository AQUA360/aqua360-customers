<script setup>
import { ref, computed, watch } from 'vue';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const { $SmartMeteringApiService } = useNuxtApp();
const { permissions, loading: permissionsLoading } = usePermissions();

const canView = computed(() => Boolean(permissions.value?.permissions?.view_user));

const settings = ref(null);
const loadingSettings = ref(false);
const loadError = ref(false);

const readingDate = ref(localIsoDate(new Date()));
const meterCode = ref('');

const connectivityLoading = ref(false);
const connectivityResult = ref(null);
const readingsLoading = ref(false);
const readingsResult = ref(null);
const readingsError = ref('');
const downloadingOpenapi = ref(false);
const downloadingCurl = ref(false);

const probesEnabled = computed(() => Boolean(settings.value?.enabled && settings.value?.api_url));
const showToken = ref(false);
const maskedToken = computed(() => {
  const token = settings.value?.authentication_token || '';
  return token ? '*'.repeat(token.length) : '';
});

watch([permissionsLoading, permissions], () => {
  if (!permissionsLoading.value && permissions.value && !canView.value) {
    toast.error(t('common.no_permissions'));
    navigateTo('/settings/');
  }
});

watch(canView, (allowed) => {
  if (allowed) loadSettings();
}, { immediate: true });

function localIsoDate(date) {
  const pad = (value) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

async function loadSettings() {
  loadingSettings.value = true;
  loadError.value = false;
  try {
    settings.value = await $SmartMeteringApiService.getSettings();
  } catch (error) {
    console.error(error);
    loadError.value = true;
    settings.value = null;
  } finally {
    loadingSettings.value = false;
  }
}

const connectivityTone = computed(() => {
  const result = connectivityResult.value;
  if (!result) return '';
  if (!result.reachable) return 'error';
  if (result.code === 'ok') return 'ok';
  return 'warning';
});

const connectivityMessage = computed(() => {
  const result = connectivityResult.value;
  if (!result) return '';
  if (!result.reachable) {
    if (result.code === 'not_configured') return t('settings_block.smart_metering_not_configured');
    if (result.code === 'url_missing') return t('settings_block.smart_metering_api_url_missing');
    return result.detail || t('settings_block.smart_metering_connectivity_fail');
  }
  const params = { status: result.status_code, ms: result.elapsed_ms };
  if (result.authenticated === false) return t('settings_block.smart_metering_connectivity_auth', params);
  if (result.status_code >= 500) return t('settings_block.smart_metering_connectivity_server', params);
  return t('settings_block.smart_metering_connectivity_ok', params);
});

function probeErrorMessage(error) {
  const data = error?.data || error?.response?._data || {};
  if (data.code === 'reading_date_required') return t('settings_block.smart_metering_date_required');
  if (data.code === 'reading_date_invalid') return t('settings_block.smart_metering_date_invalid');
  if (data.code === 'not_configured') return t('settings_block.smart_metering_not_configured');
  if (data.code === 'url_missing') return t('settings_block.smart_metering_api_url_missing');
  if (data.detail) return data.detail;
  return t('settings_block.smart_metering_probe_error');
}

async function checkConnectivity() {
  connectivityLoading.value = true;
  connectivityResult.value = null;
  try {
    connectivityResult.value = await $SmartMeteringApiService.probe({ action: 'connectivity' });
  } catch (error) {
    console.error(error);
    connectivityResult.value = {
      reachable: false,
      code: 'unreachable',
      detail: probeErrorMessage(error),
    };
  } finally {
    connectivityLoading.value = false;
  }
}

async function downloadOpenapi() {
  downloadingOpenapi.value = true;
  try {
    await $SmartMeteringApiService.downloadFile('openapi');
  } catch (error) {
    console.error(error);
    toast.error(probeErrorMessage(error));
  } finally {
    downloadingOpenapi.value = false;
  }
}

async function downloadCurl() {
  downloadingCurl.value = true;
  try {
    await $SmartMeteringApiService.downloadFile('curl', {
      reading_date: readingDate.value,
      meter: meterCode.value.trim() || null,
    });
  } catch (error) {
    console.error(error);
    toast.error(probeErrorMessage(error));
  } finally {
    downloadingCurl.value = false;
  }
}

async function fetchReadings() {
  if (!readingDate.value) {
    readingsError.value = t('settings_block.smart_metering_date_required');
    readingsResult.value = null;
    return;
  }
  readingsLoading.value = true;
  readingsError.value = '';
  readingsResult.value = null;
  try {
    const result = await $SmartMeteringApiService.probe({
      action: 'readings',
      reading_date: readingDate.value,
      meter: meterCode.value.trim() || null,
    });
    if (result?.code === 'not_configured') {
      readingsError.value = t('settings_block.smart_metering_not_configured');
      return;
    }
    if (result && result.ok === false) {
      readingsError.value = t('settings_block.smart_metering_probe_error');
      return;
    }
    readingsResult.value = result;
  } catch (error) {
    console.error(error);
    readingsError.value = probeErrorMessage(error);
  } finally {
    readingsLoading.value = false;
  }
}
</script>

<template>
  <div class="pb-6 px-4">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <H1 class="!mb-0">{{ t('settings_block.smart_metering_config') }}</H1>
        <p class="mt-1 text-sm text-slate-600">{{ t('settings_block.smart_metering_config_help') }}</p>
      </div>
      <NuxtLink to="/settings/" class="text-sm text-sky-500 underline hover:no-underline">
        {{ t('common.settings') }}
      </NuxtLink>
    </div>

    <div v-if="permissionsLoading || loadingSettings" class="rounded-md border border-slate-200 bg-white p-8">
      <AppLoading :text="t('common.loading')" />
    </div>

    <div v-else-if="loadError" class="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      {{ t('settings_block.smart_metering_probe_error') }}
    </div>

    <template v-else-if="canView && settings">
      <section v-if="!settings.enabled" class="mb-8 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        {{ t('settings_block.smart_metering_not_configured') }}
      </section>

      <template v-else>
        <section class="mb-8 rounded-md border border-slate-200 bg-white p-4 shadow-sm">
          <h2 class="text-lg font-semibold text-slate-900">{{ t('settings_block.smart_metering_connection') }}</h2>

          <dl class="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <dt class="text-sm font-medium text-slate-500">{{ t('settings_block.smart_metering_api_url') }}</dt>
              <dd class="mt-1 break-all font-mono text-sm text-slate-900">
                {{ settings.api_url || '—' }}
              </dd>
              <p v-if="!settings.api_url" class="mt-1 text-sm text-amber-800">
                {{ t('settings_block.smart_metering_api_url_missing') }}
              </p>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">{{ t('settings_block.smart_metering_token') }}</dt>
              <dd class="mt-1 flex items-start gap-2 font-mono text-sm text-slate-900">
                <span class="break-all">{{ showToken ? (settings.authentication_token || '—') : (maskedToken || '—') }}</span>
                <button v-if="settings.authentication_token" type="button"
                  class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-sky-500"
                  :title="showToken ? t('settings_block.smart_metering_hide_token') : t('settings_block.smart_metering_show_token')"
                  :aria-label="showToken ? t('settings_block.smart_metering_hide_token') : t('settings_block.smart_metering_show_token')"
                  :aria-pressed="showToken"
                  @click="showToken = !showToken">
                  <Icon :name="showToken ? 'fa6-solid:eye-slash' : 'fa6-solid:eye'" class="text-xs" />
                </button>
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">{{ t('settings_block.smart_metering_auth_param') }}</dt>
              <dd class="mt-1 text-sm text-slate-900">{{ settings.auth_param }}</dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">{{ t('settings_block.smart_metering_timeout') }}</dt>
              <dd class="mt-1 text-sm text-slate-900">
                {{ t('settings_block.smart_metering_seconds', { n: settings.timeout }) }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">{{ t('settings_block.smart_metering_margin') }}</dt>
              <dd class="mt-1 text-sm text-slate-900">
                {{ t('settings_block.smart_metering_margin_days', { n: settings.margin }) }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">{{ t('settings_block.smart_metering_inbound') }}</dt>
              <dd class="mt-1 break-all font-mono text-sm text-slate-900">{{ settings.inbound_endpoint }}</dd>
              <p class="mt-1 text-sm text-slate-500">{{ t('settings_block.smart_metering_inbound_help') }}</p>
            </div>
          </dl>

          <div class="mt-4 border-t border-slate-100 pt-4">
            <button type="button" class="button-default flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="downloadingOpenapi" @click="downloadOpenapi">
              <Icon :name="downloadingOpenapi ? 'fa6-solid:spinner' : 'fa6-solid:file-code'"
                :class="{ 'animate-spin': downloadingOpenapi }" />
              {{ t('settings_block.smart_metering_download_openapi') }}
            </button>
            <p class="mt-2 text-sm text-slate-500">{{ t('settings_block.smart_metering_download_openapi_help') }}</p>
          </div>
        </section>

        <section class="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
          <h2 class="text-lg font-semibold text-slate-900">{{ t('settings_block.smart_metering_tests') }}</h2>
          <p class="mt-1 text-sm text-slate-600">{{ t('settings_block.smart_metering_tests_help') }}</p>

          <p class="mt-4 text-sm text-slate-500">{{ t('settings_block.smart_metering_connectivity_help') }}</p>

          <div class="mt-3 flex flex-wrap items-center gap-3">
            <button type="button" class="button-primary flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="connectivityLoading || !probesEnabled" @click="checkConnectivity">
              <Icon :name="connectivityLoading ? 'fa6-solid:spinner' : 'fa6-solid:plug'"
                :class="{ 'animate-spin': connectivityLoading }" />
              {{ t('settings_block.smart_metering_check_connectivity') }}
            </button>
          </div>

          <p v-if="connectivityResult" class="mt-3 rounded-md border px-3 py-2 text-sm" :class="{
            'border-emerald-200 bg-emerald-50 text-emerald-900': connectivityTone === 'ok',
            'border-amber-200 bg-amber-50 text-amber-950': connectivityTone === 'warning',
            'border-red-200 bg-red-50 text-red-900': connectivityTone === 'error',
          }">
            {{ connectivityMessage }}
          </p>

          <div class="mt-6 grid gap-4 md:grid-cols-2">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-600" for="smart-metering-reading-date">
                {{ t('billing_block.reading_date') }}
              </label>
              <input id="smart-metering-reading-date" v-model="readingDate" type="date" class="input"
                :disabled="readingsLoading" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-600" for="smart-metering-meter">
                {{ t('settings_block.smart_metering_meter_optional') }}
              </label>
              <input id="smart-metering-meter" v-model="meterCode" type="text" class="input"
                :disabled="readingsLoading" />
              <p class="mt-1 text-sm text-slate-500">{{ t('settings_block.smart_metering_meter_help') }}</p>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-3">
            <button type="button" class="button-primary flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="readingsLoading || !probesEnabled || !readingDate" @click="fetchReadings">
              <Icon :name="readingsLoading ? 'fa6-solid:spinner' : 'fa6-solid:tower-broadcast'"
                :class="{ 'animate-spin': readingsLoading }" />
              {{ t('reading_block.smart_metering_get_readings') }}
            </button>
            <button type="button" class="button-default flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="downloadingCurl || !probesEnabled || !readingDate" @click="downloadCurl">
              <Icon :name="downloadingCurl ? 'fa6-solid:spinner' : 'fa6-solid:terminal'"
                :class="{ 'animate-spin': downloadingCurl }" />
              {{ t('settings_block.smart_metering_download_curl') }}
            </button>
          </div>
          <p class="mt-2 text-sm text-slate-500">{{ t('settings_block.smart_metering_download_curl_help') }}</p>

          <p v-if="readingsError" class="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
            {{ readingsError }}
          </p>

          <div v-if="readingsResult" class="mt-4">
            <p class="text-sm text-slate-700">
              <span class="font-semibold">{{ t('settings_block.smart_metering_readings_count', { count: readingsResult.count }) }}</span>
              <span class="mx-2 text-slate-300">·</span>
              {{ t('settings_block.smart_metering_elapsed', { ms: readingsResult.elapsed_ms }) }}
              <span class="mx-2 text-slate-300">·</span>
              {{ t('settings_block.smart_metering_endpoint') }}:
              <span class="font-mono">{{ readingsResult.endpoint }}</span>
            </p>
            <p v-if="!readingsResult.count" class="mt-2 text-sm text-slate-600">
              {{ t('settings_block.smart_metering_no_readings') }}
            </p>
            <template v-else>
              <p v-if="readingsResult.sample?.length < readingsResult.count" class="mt-1 text-sm text-slate-500">
                {{ t('settings_block.smart_metering_readings_sample', {
                  shown: readingsResult.sample.length,
                  count: readingsResult.count,
                }) }}
              </p>
              <div class="mt-3 overflow-x-auto">
                <table class="w-full text-left text-sm">
                  <thead>
                    <tr class="border-b border-slate-200 text-slate-500">
                      <th class="py-2 pr-4 font-medium">{{ t('meter') }}</th>
                      <th class="py-2 pr-4 font-medium">{{ t('settings_block.smart_metering_reading_value') }}</th>
                      <th class="py-2 font-medium">{{ t('settings_block.smart_metering_timestamp') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, index) in readingsResult.sample" :key="`${row.meter}-${index}`"
                      class="border-b border-slate-100">
                      <td class="py-2 pr-4 font-mono">{{ row.meter || '—' }}</td>
                      <td class="py-2 pr-4">{{ row.reading ?? '—' }}</td>
                      <td class="py-2">{{ row.timestamp || '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>
