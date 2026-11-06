<script setup>
import { computed, ref, watch } from 'vue';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { usePermissions } from '~/middleware/permission';
import { useConfigStore } from '~/stores/useConfigStore';

const { t } = useI18n();
const toast = useToast();
const { $SendBatchApiService, $ConfigProjectApiService } = useNuxtApp();
const { permissions, loading: permissionsLoading } = usePermissions();
const configStore = useConfigStore();

const canView = computed(() => Boolean(permissions.value?.permissions?.view_user));
const canEditConfig = computed(() => Boolean(permissions.value?.can_edit_config_project));

const loading = ref(true);
const saving = ref(false);
const ensuring = ref(false);
const overview = ref(null);

const editing = ref({ kind: null, id: null });
const draft = ref({});

watch([permissionsLoading, permissions], () => {
  if (!permissionsLoading.value && permissions.value && !canView.value) {
    toast.error(t('common.no_permissions'));
    navigateTo('/settings/');
  }
});

watch(canView, (allowed) => {
  if (allowed) loadSettings();
}, { immediate: true });

const hasMissing = computed(() => Boolean(overview.value?.has_missing));
const missingSummary = computed(() => {
  const missing = overview.value?.missing;
  if (!missing) return [];
  const parts = [];
  if (missing.providers?.length) {
    parts.push(t('settings_block.send_batch_missing_providers', { count: missing.providers.length }));
  }
  if (missing.types?.length) {
    parts.push(t('settings_block.send_batch_missing_types', { count: missing.types.length }));
  }
  if (missing.statuses?.length) {
    parts.push(t('settings_block.send_batch_missing_statuses', { count: missing.statuses.length }));
  }
  if (missing.config_projects?.length) {
    parts.push(t('settings_block.send_batch_missing_configs', { count: missing.config_projects.length }));
  }
  return parts;
});

async function loadSettings() {
  loading.value = true;
  try {
    overview.value = await $SendBatchApiService.getSettings();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
    overview.value = null;
  } finally {
    loading.value = false;
  }
}

function startEdit(kind, item) {
  editing.value = { kind, id: item.id ?? item.token };
  draft.value = { ...item };
  if (kind === 'type') {
    draft.value.provider_id = item.provider_id ?? item.provider?.id ?? null;
  }
}

function cancelEdit() {
  editing.value = { kind: null, id: null };
  draft.value = {};
}

function isEditing(kind, item) {
  const id = item.id ?? item.token;
  return editing.value.kind === kind && editing.value.id === id;
}

async function ensureDefaults() {
  ensuring.value = true;
  try {
    const result = await $SendBatchApiService.ensureDefaults();
    overview.value = result.overview;
    if (result.skipped_config_projects?.length && !canEditConfig.value) {
      toast.error(t('settings_block.send_batch_config_create_denied'));
    } else {
      toast.success(t('settings_block.send_batch_ensure_success'));
    }
    // ODOO_ENABLED pot haver canviat: forcem recalcular el menú de lots.
    configStore.sendBatchEnabled = null;
    await configStore.fetchSendBatchEnabled();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    ensuring.value = false;
  }
}

async function saveProvider(item) {
  saving.value = true;
  try {
    const payload = {
      token: draft.value.token,
      name: draft.value.name,
      position: numberOrNull(draft.value.position),
      is_default: Boolean(draft.value.is_default),
    };
    if (item.id) {
      await $SendBatchApiService.updateProvider(item.id, payload);
    } else {
      await $SendBatchApiService.createProvider(payload);
    }
    toast.success(t('common.correct_save'));
    cancelEdit();
    await loadSettings();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
}

async function saveType(item) {
  saving.value = true;
  try {
    const payload = {
      token: draft.value.token,
      name: draft.value.name,
      endpoint: draft.value.endpoint,
      position: numberOrNull(draft.value.position),
      is_default: Boolean(draft.value.is_default),
      provider_id: draft.value.provider_id,
    };
    if (item.id) {
      await $SendBatchApiService.updateType(item.id, payload);
    } else {
      await $SendBatchApiService.createType(payload);
    }
    toast.success(t('common.correct_save'));
    cancelEdit();
    await loadSettings();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
}

async function saveStatus(item) {
  saving.value = true;
  try {
    const payload = {
      token: draft.value.token,
      name: draft.value.name,
      color: draft.value.color || null,
      position: numberOrNull(draft.value.position),
      is_default: Boolean(draft.value.is_default),
    };
    if (item.id) {
      await $SendBatchApiService.updateStatus(item.id, payload);
    } else {
      await $SendBatchApiService.createStatus(payload);
    }
    toast.success(t('common.correct_save'));
    cancelEdit();
    await loadSettings();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
}

async function saveConfig(item) {
  if (!canEditConfig.value) {
    toast.error(t('settings_block.send_batch_config_create_denied'));
    return;
  }
  saving.value = true;
  try {
    const value = draft.value.value ?? '';
    if (item.missing) {
      await $ConfigProjectApiService.create({
        token: item.token,
        name: draft.value.name || item.name,
        value,
        file: item.file || 'General',
      });
    } else {
      await $ConfigProjectApiService.updateByToken(item.token, {
        name: draft.value.name || item.name,
        value,
      });
    }
    if (item.token === 'ODOO_ENABLED') {
      localStorage.setItem('config_ODOO_ENABLED', JSON.stringify(value));
      configStore.sendBatchEnabled = null;
      await configStore.fetchSendBatchEnabled();
    }
    toast.success(t('common.correct_save'));
    cancelEdit();
    await loadSettings();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
}

function numberOrNull(value) {
  if (value === '' || value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function addProvider() {
  startEdit('provider', {
    id: 'new',
    token: '',
    name: '',
    position: (overview.value?.providers?.length || 0) + 1,
    is_default: false,
  });
}

function addType() {
  const defaultProviderId = overview.value?.providers?.[0]?.id || null;
  startEdit('type', {
    id: 'new',
    token: '',
    name: '',
    endpoint: '',
    position: (overview.value?.types?.length || 0) + 1,
    is_default: false,
    provider_id: defaultProviderId,
  });
}

function addStatus() {
  startEdit('status', {
    id: 'new',
    token: '',
    name: '',
    color: '',
    position: (overview.value?.statuses?.length || 0) + 1,
    is_default: false,
  });
}
</script>

<template>
  <div class="pb-6 px-4">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <H1 class="!mb-0">{{ t('settings_block.send_batch_config') }}</H1>
        <p class="mt-1 text-sm text-slate-600">{{ t('settings_block.send_batch_config_help') }}</p>
      </div>
      <NuxtLink to="/settings/" class="text-sm text-sky-500 underline hover:no-underline">
        {{ t('common.settings') }}
      </NuxtLink>
    </div>

    <div v-if="permissionsLoading || loading" class="rounded-md border border-slate-200 bg-white p-8">
      <AppLoading :text="t('common.loading')" />
    </div>

    <template v-else-if="canView && overview">
      <section v-if="hasMissing" class="mb-6 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        <p class="font-medium">{{ t('settings_block.send_batch_missing_title') }}</p>
        <ul class="mt-2 list-disc pl-5">
          <li v-for="(part, index) in missingSummary" :key="index">{{ part }}</li>
        </ul>
        <button class="button-primary mt-3" :disabled="ensuring" @click="ensureDefaults">
          <Icon v-if="ensuring" name="fa6-solid:spinner" class="animate-spin mr-1" />
          {{ t('settings_block.send_batch_ensure_defaults') }}
        </button>
      </section>

      <!-- ConfigProject -->
      <section class="mb-8 rounded-md border border-slate-200 bg-white p-4 shadow-sm">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="text-lg font-semibold text-slate-900">{{ t('settings_block.send_batch_configs') }}</h2>
        </div>
        <p class="mb-4 text-sm text-slate-600">{{ t('settings_block.send_batch_configs_help') }}</p>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-slate-500">
              <tr>
                <th class="px-2 py-2 font-medium">{{ t('common.identification') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.name') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.value') }}</th>
                <th class="px-2 py-2 font-medium w-28"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.config_projects" :key="item.token"
                class="border-t border-slate-100" :class="{ 'bg-amber-50': item.missing }">
                <td class="px-2 py-2 font-mono text-xs">{{ item.token }}</td>
                <td class="px-2 py-2">
                  <template v-if="isEditing('config', item)">
                    <input v-model="draft.name" type="text" class="input !py-1 w-full" />
                  </template>
                  <template v-else>{{ item.name || '—' }}</template>
                </td>
                <td class="px-2 py-2">
                  <template v-if="isEditing('config', item)">
                    <input v-model="draft.value" type="text" class="input !py-1 w-full font-mono"
                      @keyup.enter="saveConfig(item)" @keyup.esc="cancelEdit()" />
                  </template>
                  <template v-else>
                    <span v-if="item.missing" class="text-amber-700">{{ t('settings_block.send_batch_missing_value') }}</span>
                    <span v-else class="font-mono">{{ item.value }}</span>
                  </template>
                </td>
                <td class="px-2 py-2 text-right">
                  <template v-if="isEditing('config', item)">
                    <button class="button-secondary !py-1 mr-1" :disabled="saving" @click="saveConfig(item)">
                      {{ t('common.save') }}
                    </button>
                    <button class="button-default-xs !py-1" :disabled="saving" @click="cancelEdit">
                      {{ t('common.cancel') }}
                    </button>
                  </template>
                  <button v-else-if="canEditConfig" class="text-sky-500 hover:text-sky-700"
                    :title="t('common.edit')" @click="startEdit('config', item)">
                    <Icon name="fa6-solid:pen-to-square" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Providers -->
      <section class="mb-8 rounded-md border border-slate-200 bg-white p-4 shadow-sm">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="text-lg font-semibold text-slate-900">{{ t('send_batch_block.provider') }}</h2>
          <button class="button-secondary !py-1" @click="addProvider">{{ t('common.add') }}</button>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-slate-500">
              <tr>
                <th class="px-2 py-2 font-medium">{{ t('common.identification') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.name') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.position') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('default') }}</th>
                <th class="px-2 py-2 font-medium w-28"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="isEditing('provider', { id: 'new' })" class="border-t border-slate-100 bg-sky-50">
                <td class="px-2 py-2"><input v-model="draft.token" type="text" class="input !py-1 w-full font-mono" /></td>
                <td class="px-2 py-2"><input v-model="draft.name" type="text" class="input !py-1 w-full" /></td>
                <td class="px-2 py-2"><input v-model="draft.position" type="number" class="input !py-1 w-20" /></td>
                <td class="px-2 py-2"><input v-model="draft.is_default" type="checkbox" /></td>
                <td class="px-2 py-2 text-right">
                  <button class="button-secondary !py-1 mr-1" :disabled="saving" @click="saveProvider({ id: null })">
                    {{ t('common.save') }}
                  </button>
                  <button class="button-default-xs !py-1" :disabled="saving" @click="cancelEdit">
                    {{ t('common.cancel') }}
                  </button>
                </td>
              </tr>
              <tr v-for="item in overview.providers" :key="item.id" class="border-t border-slate-100">
                <template v-if="isEditing('provider', item)">
                  <td class="px-2 py-2"><input v-model="draft.token" type="text" class="input !py-1 w-full font-mono" /></td>
                  <td class="px-2 py-2"><input v-model="draft.name" type="text" class="input !py-1 w-full" /></td>
                  <td class="px-2 py-2"><input v-model="draft.position" type="number" class="input !py-1 w-20" /></td>
                  <td class="px-2 py-2"><input v-model="draft.is_default" type="checkbox" /></td>
                  <td class="px-2 py-2 text-right">
                    <button class="button-secondary !py-1 mr-1" :disabled="saving" @click="saveProvider(item)">
                      {{ t('common.save') }}
                    </button>
                    <button class="button-default-xs !py-1" :disabled="saving" @click="cancelEdit">
                      {{ t('common.cancel') }}
                    </button>
                  </td>
                </template>
                <template v-else>
                  <td class="px-2 py-2 font-mono text-xs">{{ item.token }}</td>
                  <td class="px-2 py-2">{{ item.name }}</td>
                  <td class="px-2 py-2">{{ item.position }}</td>
                  <td class="px-2 py-2">
                    <Icon v-if="item.is_default" name="fa6-solid:check" class="text-green-600" />
                  </td>
                  <td class="px-2 py-2 text-right">
                    <button class="text-sky-500 hover:text-sky-700" :title="t('common.edit')"
                      @click="startEdit('provider', item)">
                      <Icon name="fa6-solid:pen-to-square" />
                    </button>
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Types -->
      <section class="mb-8 rounded-md border border-slate-200 bg-white p-4 shadow-sm">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="text-lg font-semibold text-slate-900">{{ t('send_batch_block.type') }}</h2>
          <button class="button-secondary !py-1" @click="addType">{{ t('common.add') }}</button>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-slate-500">
              <tr>
                <th class="px-2 py-2 font-medium">{{ t('send_batch_block.provider') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.identification') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.name') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('settings_block.send_batch_endpoint') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.position') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('default') }}</th>
                <th class="px-2 py-2 font-medium w-28"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="isEditing('type', { id: 'new' })" class="border-t border-slate-100 bg-sky-50">
                <td class="px-2 py-2">
                  <select v-model="draft.provider_id" class="input !py-1">
                    <option v-for="provider in overview.providers" :key="provider.id" :value="provider.id">
                      {{ provider.name }}
                    </option>
                  </select>
                </td>
                <td class="px-2 py-2"><input v-model="draft.token" type="text" class="input !py-1 w-full font-mono" /></td>
                <td class="px-2 py-2"><input v-model="draft.name" type="text" class="input !py-1 w-full" /></td>
                <td class="px-2 py-2"><input v-model="draft.endpoint" type="text" class="input !py-1 w-full font-mono" /></td>
                <td class="px-2 py-2"><input v-model="draft.position" type="number" class="input !py-1 w-20" /></td>
                <td class="px-2 py-2"><input v-model="draft.is_default" type="checkbox" /></td>
                <td class="px-2 py-2 text-right">
                  <button class="button-secondary !py-1 mr-1" :disabled="saving" @click="saveType({ id: null })">
                    {{ t('common.save') }}
                  </button>
                  <button class="button-default-xs !py-1" :disabled="saving" @click="cancelEdit">
                    {{ t('common.cancel') }}
                  </button>
                </td>
              </tr>
              <tr v-for="item in overview.types" :key="item.id" class="border-t border-slate-100">
                <template v-if="isEditing('type', item)">
                  <td class="px-2 py-2">
                    <select v-model="draft.provider_id" class="input !py-1">
                      <option v-for="provider in overview.providers" :key="provider.id" :value="provider.id">
                        {{ provider.name }}
                      </option>
                    </select>
                  </td>
                  <td class="px-2 py-2"><input v-model="draft.token" type="text" class="input !py-1 w-full font-mono" /></td>
                  <td class="px-2 py-2"><input v-model="draft.name" type="text" class="input !py-1 w-full" /></td>
                  <td class="px-2 py-2"><input v-model="draft.endpoint" type="text" class="input !py-1 w-full font-mono" /></td>
                  <td class="px-2 py-2"><input v-model="draft.position" type="number" class="input !py-1 w-20" /></td>
                  <td class="px-2 py-2"><input v-model="draft.is_default" type="checkbox" /></td>
                  <td class="px-2 py-2 text-right">
                    <button class="button-secondary !py-1 mr-1" :disabled="saving" @click="saveType(item)">
                      {{ t('common.save') }}
                    </button>
                    <button class="button-default-xs !py-1" :disabled="saving" @click="cancelEdit">
                      {{ t('common.cancel') }}
                    </button>
                  </td>
                </template>
                <template v-else>
                  <td class="px-2 py-2">{{ item.provider?.name || '—' }}</td>
                  <td class="px-2 py-2 font-mono text-xs">{{ item.token }}</td>
                  <td class="px-2 py-2">{{ item.name }}</td>
                  <td class="px-2 py-2 font-mono text-xs">{{ item.endpoint }}</td>
                  <td class="px-2 py-2">{{ item.position }}</td>
                  <td class="px-2 py-2">
                    <Icon v-if="item.is_default" name="fa6-solid:check" class="text-green-600" />
                  </td>
                  <td class="px-2 py-2 text-right">
                    <button class="text-sky-500 hover:text-sky-700" :title="t('common.edit')"
                      @click="startEdit('type', item)">
                      <Icon name="fa6-solid:pen-to-square" />
                    </button>
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Statuses -->
      <section class="mb-8 rounded-md border border-slate-200 bg-white p-4 shadow-sm">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="text-lg font-semibold text-slate-900">{{ t('common.statuses') }}</h2>
          <button class="button-secondary !py-1" @click="addStatus">{{ t('common.add') }}</button>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-slate-50 text-left text-slate-500">
              <tr>
                <th class="px-2 py-2 font-medium">{{ t('common.identification') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.name') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.color') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('common.position') }}</th>
                <th class="px-2 py-2 font-medium">{{ t('default') }}</th>
                <th class="px-2 py-2 font-medium w-28"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="isEditing('status', { id: 'new' })" class="border-t border-slate-100 bg-sky-50">
                <td class="px-2 py-2"><input v-model="draft.token" type="text" class="input !py-1 w-full font-mono" /></td>
                <td class="px-2 py-2"><input v-model="draft.name" type="text" class="input !py-1 w-full" /></td>
                <td class="px-2 py-2"><input v-model="draft.color" type="text" class="input !py-1 w-full" /></td>
                <td class="px-2 py-2"><input v-model="draft.position" type="number" class="input !py-1 w-20" /></td>
                <td class="px-2 py-2"><input v-model="draft.is_default" type="checkbox" /></td>
                <td class="px-2 py-2 text-right">
                  <button class="button-secondary !py-1 mr-1" :disabled="saving" @click="saveStatus({ id: null })">
                    {{ t('common.save') }}
                  </button>
                  <button class="button-default-xs !py-1" :disabled="saving" @click="cancelEdit">
                    {{ t('common.cancel') }}
                  </button>
                </td>
              </tr>
              <tr v-for="item in overview.statuses" :key="item.id" class="border-t border-slate-100">
                <template v-if="isEditing('status', item)">
                  <td class="px-2 py-2"><input v-model="draft.token" type="text" class="input !py-1 w-full font-mono" /></td>
                  <td class="px-2 py-2"><input v-model="draft.name" type="text" class="input !py-1 w-full" /></td>
                  <td class="px-2 py-2"><input v-model="draft.color" type="text" class="input !py-1 w-full" /></td>
                  <td class="px-2 py-2"><input v-model="draft.position" type="number" class="input !py-1 w-20" /></td>
                  <td class="px-2 py-2"><input v-model="draft.is_default" type="checkbox" /></td>
                  <td class="px-2 py-2 text-right">
                    <button class="button-secondary !py-1 mr-1" :disabled="saving" @click="saveStatus(item)">
                      {{ t('common.save') }}
                    </button>
                    <button class="button-default-xs !py-1" :disabled="saving" @click="cancelEdit">
                      {{ t('common.cancel') }}
                    </button>
                  </td>
                </template>
                <template v-else>
                  <td class="px-2 py-2 font-mono text-xs">{{ item.token }}</td>
                  <td class="px-2 py-2">{{ item.name }}</td>
                  <td class="px-2 py-2">{{ item.color || '—' }}</td>
                  <td class="px-2 py-2">{{ item.position }}</td>
                  <td class="px-2 py-2">
                    <Icon v-if="item.is_default" name="fa6-solid:check" class="text-green-600" />
                  </td>
                  <td class="px-2 py-2 text-right">
                    <button class="text-sky-500 hover:text-sky-700" :title="t('common.edit')"
                      @click="startEdit('status', item)">
                      <Icon name="fa6-solid:pen-to-square" />
                    </button>
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
