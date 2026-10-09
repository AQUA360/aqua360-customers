<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import Pagination from '~/components/molecules/Pagination.vue';
// Importar el component SupplyPointRegion per a la subregion
import ReadingDocumentDetail from './ReadingDocumentDetail.vue';
import ReadingDetail from './ReadingDetail.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import ReadingBatchRegion from '../organisms/ReadingBatchRegion.vue';
import MeterRegion from '../organisms/MeterRegion.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion']);
const router = useRouter();
const { $ReadingDocumentApiService, $ReadingApiService, $MeterApiService } = useNuxtApp();
const pending = ref(true);
const loadingMeters = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('meters');
const totalMeters = ref(0);
const SubRegion = ref(props.isSubRegionOpen);

const meterSearchQuery = ref('');

const meters = ref({ count: 0, results: [] });

const objectPermissions = ref(null);
const expandedMeters = ref(new Set());
const showAllReadings = ref(false);
const showAllAlerts = ref(false);
const showAllRemoteAlerts = ref(false);
const isFiltering = ref(false);
const page = ref(1);
const pageSize = ref(50);

const meterPagination = computed(() => {
  const total = meters.value?.count || 0;
  const perPage = pageSize.value || 1;
  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return {
    page: page.value,
    perPage,
    total,
    totalPages,
    previous: meters.value?.previous ?? null,
    next: meters.value?.next ?? null,
    isFiltered: Boolean(meterSearchQuery.value || showAllAlerts.value || showAllRemoteAlerts.value)
  };
});

const toggleMeter = (meterId) => {
  if (expandedMeters.value.has(meterId)) {
    expandedMeters.value.delete(meterId);
  } else {
    expandedMeters.value.add(meterId);
  }
}

const toggleAllMeters = () => {
  if (showAllReadings.value) {
    expandedMeters.value.clear();
  } else {
    meters.value.results.forEach(meter => expandedMeters.value.add(meter.id));
  }
  showAllReadings.value = !showAllReadings.value;
}

const getMeterStats = (meter) => {
  if (!meter.readings || meter.readings.length === 0) return null;
  const totalConsumption = meter.readings.reduce((sum, r) => sum + (r.calculated_value || 0), 0);
  const latestReading = meter.readings[0]; // Assuming sorted by date
  return {
    totalConsumption,
    latestReading,
    readingsCount: meter.readings.length
  };
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ReadingApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getData = async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = true;

  try {
    // ({ results: statuses.value } = await $ConfiglistApiService.getAll('contract/aca-document-status'));
    const result = await $ReadingDocumentApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const getMeters = async () => {
  loadingMeters.value = true;
  try {
    const get_data = {
      reading_document: props.id,
      show_alerts: showAllAlerts.value,
      show_remote_alerts: showAllRemoteAlerts.value,
      search_query: meterSearchQuery.value,
      page: page.value,
      page_size: pageSize.value,
    }
    const result = await $MeterApiService.getByReadingDocument(get_data);
    meters.value = result;
  } catch (err) {
    console.error(err);
  } finally {
    loadingMeters.value = false;
  }
}


watch(() => props.id, async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  await getData();
  await getMeters();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
    await getMeters();
    totalMeters.value = meters.value.count;
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
  }
});

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDocument = function () {
  window.open(data.value.file, '_blank');
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const onClickModify = function () {
  return navigateTo('/contract/aca-documents/edit/' + props.id);
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

let filterTimeout = null;

// Watch for filter changes and trigger loading state
watch([meterSearchQuery, showAllAlerts, showAllRemoteAlerts], () => {
  isFiltering.value = true;
  page.value = 1;

  if (filterTimeout) {
    clearTimeout(filterTimeout);
  }

  filterTimeout = setTimeout(async () => {
    isFiltering.value = false;
    await getMeters();
  }, 300);
});


const handleMeterPageChange = (newPage) => {
  const totalPages = meterPagination.value.totalPages;
  if (newPage < 1 || newPage > totalPages || newPage === page.value) {
    return;
  }
  page.value = newPage;
  getMeters();
};

</script>

<template>
  <div class="region__content">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="transition-all duration-500 ease"
      :class="{ 'mr-[48vw]': SubRegion }">

      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('billing_block.readings_file') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ReadingDocumentRegionOptions">
          <DropdownOption :name="`${t('common.download')} ${t('common.doc')}`" @click="showDocument()"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" class="">
        <!-- <a :href="data.file" target="_blank" class="button-default">{{ t('Consulta el document') }}</a> -->
        <ReadingDocumentDetail :id="data.id" :data="data" :isSubRegion="SubRegion" :isSubRegionOpen="SubRegion"
          @show-detail="showDetail" />

        <AtomsTabs>
          <li v-if="permissions?.permissions?.view_service" class="me-2">
            <a href="#tab_meters" @click.prevent="setActiveTab('meters')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'meters', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'meters' }"
              class="inline-flex items-center justify-center p-4 border-b-2 rounded-t-lg group" aria-current="page">
              <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />
              {{ $t("service_block.read_meters") }} ({{ totalMeters || 0 }})
            </a>
          </li>
          <li v-if="permissions?.permissions?.view_service" class="me-2">
            <a href="#tab_not_found" @click.prevent="setActiveTab('not_found')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'not_found', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'not_found' }"
              class="inline-flex items-center justify-center p-4 border-b-2 rounded-t-lg group" aria-current="page">
              <Icon name="fa6-solid:eye-slash" class="display-inline mr-2" />
              {{ $t("common.not_found") }} ({{ data?.not_found_readings?.length || 0 }})
            </a>
          </li>
        </AtomsTabs>

        <div id="reading_document_tabpanels" class="">

          <section v-show="activeTab === 'not_found'" role="tabpanel"
            id="tab_not_found" class="bg-white antialiased py-2 mt-2 flex flex-col overflow-hidden gap-2" :style="{
              minHeight: 'calc(100vh - 320px)',
              maxHeight: 'calc(100vh - 320px)',
              overflowY: 'auto',
            }">
            <div class="p-2 rounded bg-slate-50 flex grid grid-cols-2 items-center gap-x-2" v-for="reading in data?.not_found_readings"
              :key="reading.id">
              <!-- <Icon name="fa6-solid:meter" class="text-slate-700 w-4 h-4 flex-shrink-0" /> -->
              <FieldDetail :label="t('service_block.meter_code')" :value="reading.meter_code" />
              <FieldDetail :label="t('billing_block.reading_date')" :value="formatDate(reading.reading_date)" />
              <FieldDetail :label="t('reading')" :value="reading.reading_value" />
              <FieldDetail :label="t('common.origin')" :value="reading.origin || t('service_block.telecontrol')" />
              <FieldDetail :label="t('common.observation')" :value="reading.observation || t('common.no_value') " />
              <FieldDetail :label="t('billing_block.control_reading')">
                <Icon :name="reading.is_control ? 'fa6-solid:check' : 'fa6-solid:x'" :class="reading.is_control ? 'text-green-500' : 'text-red-500'" />
              </FieldDetail>
            </div>
            <div v-if="data?.not_found_readings?.length === 0">
              <div class="footering text-slate-500 p-2">
                {{ t('common.no_data_found') }}
              </div>
            </div>
          </section>

          <section v-if="permissions?.permissions?.view_service" v-show="activeTab === 'meters'" role="tabpanel"
            id="tab_meters" class="bg-white antialiased py-2 h-[68vh] mt-2 flex flex-col overflow-hidden">

            <div class="flex flex-col h-full">
              <!-- Controls Bar -->
              <div class="mb-3 px-1 space-y-1 sticky top-0 bg-white pb-2 z-10">
                <!-- Search Input -->
                <div class="input relative">
                  <Icon name="fa6-solid:magnifying-glass"
                    class="absolute left-2.5 top-1/2 transform -translate-y-1/2 text-slate-400 h-3.5 w-3.5" />
                  <input v-model="meterSearchQuery" type="text"
                    :placeholder="`${t('dashboard.search')} ${t('service_block.meter_code').toLowerCase()}...`"
                    class="pl-9 text-sm w-full focus:outline-none" />
                </div>

                <!-- Action Buttons -->


                <!-- Results Info -->
                <div class="flex items-center justify-between text-[11px]">
                  <div class="flex items-center gap-2">
                    <!-- Expand/Collapse All Button -->
                    <button @click="toggleAllMeters"
                      class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded transition-colors duration-150 whitespace-nowrap flex items-center gap-1.5">
                      <Icon :name="showAllReadings ? 'fa6-solid:compress' : 'fa6-solid:expand'" class="h-3 w-3" />
                      {{ showAllReadings ? `${t('common.collapse')} ${t('common.all').toLowerCase()}` :
                        `${t('common.expand')} ${t('common.all').toLowerCase()}` }}
                    </button>

                    <!-- Additional Button (placeholder) -->
                    <button @click="showAllAlerts = !showAllAlerts"
                      class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded transition-colors duration-150 whitespace-nowrap flex items-center gap-1.5">
                      <Icon :name="showAllAlerts ? 'fa6-solid:eye' : 'fa6-solid:triangle-exclamation'"
                        class="h-3 w-3" />
                      {{ showAllAlerts ? `${t('common.show')} ${t('common.all').toLowerCase()}` : `${t('common.show')}
                      ${t('billing_block.alerts').toLowerCase()}` }}
                    </button>

                    <button @click="showAllRemoteAlerts = !showAllRemoteAlerts"
                      class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded transition-colors duration-150 whitespace-nowrap flex items-center gap-1.5">
                      <Icon :name="showAllRemoteAlerts ? 'fa6-solid:eye' : 'fa6-solid:triangle-exclamation'"
                        class="h-3 w-3" />
                      {{ showAllRemoteAlerts ? `${t('common.show')} ${t('common.all').toLowerCase()}` :
                        `${t('common.show')}
                      ${t('billing_block.remote_alerts').toLowerCase()}` }}
                    </button>
                  </div>
                  <span class="text-slate-500">
                    <span v-if="meters?.results?.length > 0" class="text-green-500 font-bold">
                      {{ meters?.results?.length }} {{ t('common.total_filtered') }} -
                    </span>
                    <span>{{ meters?.count || 0 }} {{ t('common.meters') }}</span>
                  </span>
                </div>
              </div>

              <!-- Filtering Loader -->
              <!-- Meters List -->
              <div v-if="loadingMeters" class="flex-1 flex items-center justify-center">
                <AppLoading :text="$t('common.loading')" :size="40" />
              </div>
              <div v-else class="flex-1 overflow-y-auto space-y-1.5 pr-1">
                <div v-for="meter in meters?.results" :key="meter.id"
                  class="border border-slate-200 rounded-md hover:border-slate-300 transition-all duration-150"
                  :class="{ 'bg-yellow-100': meter.readings?.some(reading => reading.alert) }">

                  <!-- Meter Header -->
                  <div class="p-2 flex items-center justify-between">
                    <div class="flex items-center gap-2 flex-1 min-w-0">
                      <button @click="toggleMeter(meter.id)"
                        class="flex-shrink-0 h-6 w-6 flex items-center justify-center text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors duration-150">
                        <Icon name="fa6-solid:chevron-right" class="h-3 w-3 transition-transform duration-200"
                          :class="{ 'rotate-90': expandedMeters.has(meter.id) }" />
                      </button>

                      <Icon name="my-icon:meter-icon-black" class="text-slate-700 w-4 h-4 flex-shrink-0" />

                      <div class="flex items-center gap-x-2">
                        <button v-if="!isSubRegion" @click="showDetail('MeterRegion', meter.id)"
                          class="text-sky-600 hover:text-sky-700 font-medium text-sm truncate">
                          {{ meter.code }}
                        </button>
                        <span v-else class="text-slate-800 font-medium text-sm truncate">{{ meter.code }}</span>
                        <abbr v-if="meter.readings?.some(reading => reading.alert)"
                          :title="meter.readings?.find(reading => reading.alert)?.alert || t('billing_block.alerts')">
                          <Icon name="fa6-solid:triangle-exclamation" class="text-red-500 w-3 h-3" />
                        </abbr>
                      </div>

                      <!-- Quick Stats -->
                      <div class="grid ml-auto gap-3 text-xs text-slate-500" :class="{
                        'grid-cols-[auto,30px,100px]': meter.readings?.some(reading => reading.remote_alert),
                        'grid-cols-[30px,100px]': !meter.readings?.some(reading => reading.remote_alert)
                      }">
                        <span v-if="meter.readings?.some(reading => reading.remote_alert)"
                          class="border border-orange-500 rounded-md text-orange-500 text-center bg-white px-1">
                          {{meter.readings?.find(reading => reading.remote_alert)?.remote_alert}}
                        </span>
                        <span class="flex items-center gap-1">
                          <Icon name="fa6-solid:list" class="h-3 w-3" />
                          {{ meter.readings?.length || 0 }}
                        </span>
                        <span v-if="getMeterStats(meter)" class="flex items-center gap-1">
                          <Icon name="fa6-solid:droplet" class="h-3 w-3" />
                          {{ getMeterStats(meter).totalConsumption.toFixed(1) }} m³
                        </span>
                      </div>
                    </div>

                    <!-- Actions -->
                    <div class="flex items-center gap-1.5 ml-2 flex-shrink-0">
                      <abbr :title="`${t('common.check')} ${t('readings')}`">
                        <button
                          class="h-6 w-6 text-slate-500 border border-slate-300 rounded hover:bg-slate-50 hover:border-slate-400 hover:text-slate-700 flex items-center justify-center transition-colors duration-150"
                          @click="showDetail('ReadingDetail', meter.id)">
                          <Icon name="fa6-solid:eye" class="h-3 w-3" />
                        </button>
                      </abbr>
                    </div>
                  </div>

                  <!-- Readings Table (Expandable) -->
                  <div v-if="expandedMeters.has(meter.id) && meter.readings?.length > 0"
                    class="border-t border-slate-200 bg-slate-50">
                    <div class="overflow-x-auto">
                      <table class="w-full text-xs">
                        <thead class="bg-slate-100 text-slate-600">
                          <tr>
                            <th class="px-2 py-1.5 text-left font-medium">{{ t('common.date') }}</th>
                            <th class="px-2 py-1.5 text-left font-medium">{{ t('reading') }}</th>
                            <th class="px-2 py-1.5 text-left font-medium">{{ t('billing_block.consumption') }}</th>
                            <th class="px-2 py-1.5 text-left font-medium">{{ t('billing_block.estimated') }}</th>
                            <th class="px-2 py-1.5 text-left font-medium">{{ t('billing_block.leak') }}</th>
                            <th class="px-2 py-1.5 text-center font-medium">
                              <abbr :title="t('billing_block.control_reading')">{{
                                t('billing_block.short_control_reading') }}</abbr>
                            </th>
                          </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                          <tr v-for="reading in meter.readings" :key="reading.id"
                            class="hover:bg-slate-100 transition-colors duration-100">
                            <td class="px-2 py-1.5 text-slate-700">{{ formatDate(reading.reading_date) }} </td>
                            <td class="px-2 py-1.5 text-left text-slate-700 font-medium">{{ reading.reading_value }}
                            </td>
                            <td class="px-2 py-1.5 text-left text-slate-700">{{ reading.calculated_value }} m³</td>
                            <td class="px-2 py-1.5 text-left text-slate-600">
                              {{ reading.estimated_used ? reading.estimated_used + ' m³' : '—' }}
                            </td>
                            <td class="px-2 py-1.5 text-left text-slate-600">{{ reading.leak_value }} m³</td>
                            <td class="px-2 py-1.5 text-center">
                              <span v-if="reading.is_control"
                                class="inline-flex items-center justify-center h-5 w-5 rounded-full bg-sky-100 text-sky-700">
                                <Icon name="fa6-solid:check" class="h-2.5 w-2.5" />
                              </span>
                              <span v-else class="text-slate-400">—</span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <!-- Empty State -->
                  <div v-else-if="expandedMeters.has(meter.id) && (!meter.readings || meter.readings.length === 0)"
                    class="border-t border-slate-200 bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">
                    {{ t('service_block.no_readings') }}
                  </div>
                </div>

                <!-- Empty State for Search -->
                <div v-if="meters?.results?.length === 0 && meterSearchQuery" class="text-center py-8 text-slate-500">
                  <Icon name="fa6-solid:magnifying-glass" class="h-8 w-8 mx-auto mb-2 text-slate-400" />
                  <p class="text-sm">{{ t('common.no_data_found') }}</p>
                </div>
              </div>

              <div v-if="meterPagination.totalPages > 1" class="mt-4 pt-3 border-t sticky bottom-0 bg-white">
                <Pagination :pagination="meterPagination" @update:page="handleMeterPageChange" />
              </div>
            </div>
          </section>
        </div>
      </div>
      <!-- end if pending -->
    </div><!-- end region__content -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="mx-10">
        <ReadingDetail v-if="showRegionDetailComponent === 'ReadingDetail'" :contract_ids="[]"
          :meter_id="regionDetailId" :isSubRegion="true" />
        <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId" :isSubRegion="true" />
        <ReadingBatchRegion v-if="showRegionDetailComponent === 'ReadingBatchRegion'" :contract_id="null"
          :id="regionDetailId" :isSubRegion="true" />
      </div>
    </div>
  </div>
</template>
