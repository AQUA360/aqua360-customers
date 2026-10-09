<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import ButtonSeleccio from '../atoms/ButtonSeleccio.vue';

const { $ReadingBatchTemplateApiService } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  initialData: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['change']);

const selectedTemplate = ref("all");
const templates = ref([]);
const token = ref("AR");
const name = ref(t('billing_block.all_supplies'));

const selectedRoutes = ref([]);
const includeTelecontrol = ref(true);
const includeManual = ref(true);

const loadingFile = ref(false);
const useDocument = ref(false);
const uploadedFile = ref(null);
const fileMeters = ref([]);
const fileReadings = ref([]);

// Sufix any/mes actual (p. ex. "2026/M08"), afegit al codi/nom en triar una plantilla.
const getCurrentPeriodSuffix = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${year}/M${month}`;
};

const emitChange = () => {

  let data = {
    route_ids: selectedRoutes.value.map(route => route.id),
    token: token.value,
    name: name.value,
    include_telecontrol: includeTelecontrol.value,
    include_manual: includeManual.value,
    fileMeters: fileMeters.value,
    fileReadings: fileReadings.value,
  }
  emit('change', data);
};


const loadData = async () => {
  const result = await $ReadingBatchTemplateApiService.getAll();
  templates.value = (result.results || []).filter((t) => t.is_active);
  applyInitialData();
  emitChange();
};

/** Best-effort prefill when reopening this step for an already-created batch. */
const applyInitialData = () => {
  const data = props.initialData;
  if (!data) return;

  if (data.name) name.value = data.name;
  if (data.token) token.value = data.token;
  if (data.include_telecontrol !== undefined) includeTelecontrol.value = data.include_telecontrol;
  if (data.include_manual !== undefined) includeManual.value = data.include_manual;

  const routeIds = Array.isArray(data.route_ids) ? data.route_ids : (Array.isArray(data.routes) ? data.routes.map(r => r.id) : null);
  if (routeIds && routeIds.length > 0) {
    const matchingTemplate = templates.value.find(template => {
      const templateRouteIds = (template.routes || []).map(r => r.id);
      return templateRouteIds.length === routeIds.length && templateRouteIds.every(id => routeIds.includes(id));
    });
    if (matchingTemplate) {
      selectedTemplate.value = matchingTemplate.id;
    } else if (Array.isArray(data.routes) && data.routes.length > 0) {
      selectedRoutes.value = data.routes;
    }
  }
};

const handleDocumentUpdate = async (file) => {
  uploadedFile.value = file;
  loadingFile.value = true;
  try {
    const result = await $ReadingBatchTemplateApiService.loadBatchTemplateByFile(file);
    console.log('result::', result);
    fileMeters.value = result.meters;
    fileReadings.value = result.readings;
  } catch (error) {
    console.error(error);
  } finally {
    loadingFile.value = false;
  }
};

onMounted(() => {
  loadData();
});

// Observa canvis per emetre l'esdeveniment
watch([selectedTemplate], () => {
  const myTemplate = templates.value.find(template => template.id == selectedTemplate.value);
  if (myTemplate) {
    selectedRoutes.value = myTemplate.routes;
    const periodSuffix = getCurrentPeriodSuffix();
    token.value = `${myTemplate.token}/${periodSuffix}`;
    name.value = `${myTemplate.name}/${periodSuffix}`;
  } else {
    selectedRoutes.value = [];
  }
  emitChange();
});
watch([includeTelecontrol, includeManual, fileMeters, fileReadings], () => {
  emitChange();
});

watch(useDocument, () => {
  if (!useDocument.value) {
    fileMeters.value = [];
    fileReadings.value = [];
    uploadedFile.value = null;
  } else {
    selectedTemplate.value = 'all';
    token.value = 'AR';
    name.value = t('billing_block.all_supplies');
  }
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="grid grid-cols-2 gap-4">
      <div class="flex items-center gap-4">
        <h2 class="text-xl font-semibold mb-4">{{ $t('common.select') }} {{ $t('common.template') }}</h2>
        <div class="items-center h-full">
          <label for="useDocument" class="flex items-center cursor-pointer">
            <div class="relative">
              <input type="checkbox" id="useDocument" class="sr-only" v-model="useDocument">
              <div class="block w-10 h-6 rounded-full transition" :class="useDocument ? 'bg-blue-600' : 'bg-gray-300'">
              </div>
              <div class="dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition transform"
                :class="useDocument ? 'translate-x-full' : ''"></div>
            </div>
            <span class="ml-3 text-sm font-medium text-slate-500">
              {{ $t('billing_block.load_by_file') }}
            </span>
          </label>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <div class="items-center h-full">
          <label for="includeTelecontrol" class="flex items-center cursor-pointer">
            <div class="relative">
              <input type="checkbox" id="includeTelecontrol" class="sr-only" v-model="includeTelecontrol">
              <div class="block w-10 h-6 rounded-full transition"
                :class="includeTelecontrol ? 'bg-blue-600' : 'bg-gray-300'"></div>
              <div class="dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition transform"
                :class="includeTelecontrol ? 'translate-x-full' : ''"></div>
            </div>
            <span class="ml-3 text-sm font-medium text-slate-500">
              {{ $t('common.include_telecontrol') }}
            </span>
          </label>
        </div>
        <div class="items-center h-full">
          <label for="includeManual" class="flex items-center cursor-pointer">
            <div class="relative">
              <input type="checkbox" id="includeManual" class="sr-only" v-model="includeManual">
              <div class="block w-10 h-6 rounded-full transition"
                :class="includeManual ? 'bg-blue-600' : 'bg-gray-300'"></div>
              <div class="dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition transform"
                :class="includeManual ? 'translate-x-full' : ''"></div>
            </div>
            <span class="ml-3 text-sm font-medium text-slate-500">
              {{ $t('common.include_manual') }}
            </span>
          </label>
        </div>

      </div>
    </div>

    <!-- Selecció de Tipus -->
    <div class="mb-4">
      <div class="grid grid-cols-2 gap-4 mb-4">
        <div v-if="!useDocument">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.template') }}</label>
          <select v-model="selectedTemplate" class="w-full text-base border border-gray-300 rounded p-2 mb-3"
            id="template">
            <option value="all" selected="selected">
              {{ $t('billing_block.all_supplies') }}
            </option>
            <option v-for="template in templates" :value="template.id" :key="template.id">
              {{ template.name }}
            </option>
          </select>
        </div>
        <div v-else>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.file') }}</label>
          <AtomsInputFile @update="handleDocumentUpdate" @delete="uploadedFile = null; fileMeters = [];" :name="t('common.file')" :uploaded="uploadedFile"
            class="w-full" />
        </div>
        <div v-if="!useDocument">
          <div v-if="selectedTemplate == 'all'">
            <span class="text-sm text-gray-500">
              {{ $t('billing_block.all_routes') }}
            </span>
          </div>
          <div v-else-if="selectedRoutes.length > 0">
            <span class="text-sm text-slate-500">
              {{ $t('common.routes') }}:
            </span>
            <div class="ml-5 mt-2 space-y-1 divide-y divide-slate-300">
              <div v-for="route in selectedRoutes" :key="route.id" class="grid grid-cols-[1fr,auto] gap-4 items-center">
                <span class="text-sm text-slate-700">{{ route.name }}</span>
                <span class="text-sm text-slate-500">{{ includeTelecontrol && includeManual ? route.num_total_readings :
                  includeTelecontrol ? route.num_telecontrol_readings : includeManual ? route.num_total_readings -
                    route.num_telecontrol_readings : 0 }} {{ $t('common.supplys') }}</span>
              </div>
            </div>
          </div>
          <div v-else>
            <span class="text-sm text-orange-500">
              {{ $t('user_group.info_template_no_routes') }}
            </span>
          </div>
        </div>
        <div v-else>
          <div>
            <span class="text-sm text-gray-500">
              {{ $t('billing_block.meters_to_reread') }}
            </span>
            <div class="ml-5 mt-2 space-y-1 divide-y divide-slate-300">
              <div v-if="!loadingFile" class="grid grid-cols-[1fr,auto] gap-4 items-center">

                <span class="text-sm text-slate-700">{{ t('billing_block.loaded_meters') }}</span>
                <span class="text-sm text-slate-500">{{ fileMeters.length || 0 }} </span>
              </div>
              <div v-else class="flex items-center gap-3">
                <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
                <span class="text-sm text-slate-500">{{ $t('common.loading') }}...</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.code') }}</label>
          <input @change="emitChange" type="text" v-model="token" class="input" id="token"
            :placeholder="$t('common.code')" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input @change="emitChange" type="text" v-model="name" class="input" id="name"
            :placeholder="$t('common.name')" />
        </div>
      </div>
      <div v-if="fileMeters.length > 0"
        class="mt-2 bg-orange-50 rounded text-orange-500 border-l-2 p-2 text-sm border-orange-500">
        {{ $t('informative_block.info_continue_fix_reading_batch') }}
      </div>
    </div>
    <!-- /end Selecció de Tipus -->
  </div>
</template>