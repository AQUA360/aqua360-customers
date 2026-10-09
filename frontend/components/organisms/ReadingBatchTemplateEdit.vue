<script setup>
import { ref, onMounted } from 'vue';
import RouteSelect from '~/components/molecules/RouteSelect.vue';

const { t } = useI18n()
const { $ReadingBatchTemplateApiService } = useNuxtApp();

const props = defineProps({
  id: {
    type: String,
    required: false,
  },
});

const is_active = ref(true);
const loading = ref(true);

const showRegion = ref(false);

const token = ref('')
const name = ref('')

const routes = ref([]);
const editingRoutes = ref(false);


const isSubRegionOpen = ref(false);

const openRouteRegion = () => {
  toggleRegion(true);
  editingRoutes.value = true;
}

const toggleRegion = (force) => {
  editingRoutes.value = false;
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const removeRoute = (item) => {
  routes.value = routes.value.filter(r => r.id != item.id);
}

const save = async () => {

  const routeIds = routes.value.map(r => r.id);

  const data = {
    id: props.id || null,
    token: token.value,
    name: name.value,
    route_ids: routeIds
  }

  const response = await $ReadingBatchTemplateApiService.save(data)

  navigateTo('/reading/reading-batch-templates/');
}

const activate = async (active) => {
  const data = {
    id: props.id,
    is_active: active
  }
  let conf_text = active ? t('confirmation_text_block.confirm_activate_reading_batch_template') : t('confirmation_text_block.confirm_deactivate_reading_batch_template');

  if (confirm(conf_text)) {
    const response = await $ReadingBatchTemplateApiService.save(data)
    navigateTo('/reading/reading-batch-templates/');
  }
}

const loadData = async () => {
  const res = await $ReadingBatchTemplateApiService.getDetail(props.id);
  name.value = res.name;
  token.value = res.token;
  routes.value = res.routes || [];

  is_active.value = res.is_active;
  loading.value = false;
}

onMounted(() => {
  if (props.id) {
    loadData();
  }
  else {
    loading.value = false;
  }
});

</script>

<template>
  <div class="text-base">


    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <div class="border border-gray-300 rounded-b p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">

      <div class="grid grid-cols-2 gap-4">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
          <input type="text" v-model="token" class="input" :disabled="!is_active" />
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="name" class="input" :disabled="!is_active" />
        </div>
        <div class="footering col-span-2">
          <div :class="{ 'mt-1': routes.length != 0 }" class="text-gray-900 divide-y rounded shadow">
            <div v-if="routes.length != 0" class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
              <span class="p-1 text-slate-400">
                {{ t('common.identification') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('common.name') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('service_block.zone') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('readings') }}
              </span>
            </div>
            <div v-for="item in routes" class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
              <div class="p-2 text-slate-800">{{ item.token }}</div>
              <div class="p-2 text-slate-800 relative">
                {{ item.name }}
              </div>
              <div class="p-2 text-slate-800 relative">
                {{ item.zone_name }}
              </div>
              <div class="p-2 text-slate-800 relative">
                {{ item.num_total_readings }}
                <button @click="removeRoute(item)"
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering flex ">
              <button @click="openRouteRegion" :disabled="!is_active"
                class="display-block block w-full px-1 py-1 text-base shadow rounded text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                <Icon name="fa6-solid:pencil" class="text-slate-400 mx-2" /> {{ $t('common.select') }} {{ t('common.routes') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="col-span-3 flex flex-row-reverse mt-4" v-if="!is_active">
        <button @click="activate(true)" class="button-primary">
          <Icon name="fa6-solid:check" />&nbsp; {{ t('common.activate') }}
        </button>

      </div>
      <div class="col-span-3 flex flex-row-reverse mt-4" v-if="is_active">
        <button @click="save" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
        </button>
        <button @click="activate(false)" class="button-delete mr-4" v-if="props.id">
          <Icon name="fa6-solid:x" />&nbsp; {{ t('common.deactivate') }}
        </button>
      </div>

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació de ContractRequestEdit -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">

        <RouteSelect v-model="routes" @item-clicked="onSelectedRoute" v-if="editingRoutes" />

        <!-- <BillingBatchTemplateSelect v-model="batch_templates" @item-clicked="onSelectedTemplate" v-if="selectingTemplates" />
        <BillingBatchTemplateEdit @on-saved="onSaved" @on-removed="onRemoved" @show-subregion="handleSubRegionEvent" :id="templateId" v-if="editingTemplate" /> -->
      </div>
    </div>
  </div>
</template>