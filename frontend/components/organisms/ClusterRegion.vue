<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
// Importar el component SupplyPointRegion per a la subregion
import SupplyPointRegion from '~/components/organisms/SupplyPointRegion.vue';
import MeterRegion from '~/components/organisms/MeterRegion.vue';
import ClusterDetail from '../molecules/ClusterDetail.vue';
import ClusterDocumentsData from '../molecules/ClusterDocumentsData.vue';
import Pagination from '../molecules/Pagination.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);
const router = useRouter();
const toast = useToast();
const { $ClusterApiService, $ConfigProjectApiService } = useNuxtApp();
const { permissions, loading } = usePermissions();
const objectPermissions = ref(null);
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const nozzles = ref([]);
const splitNozzles = ref([]);
const nozzlesPending = ref(false);
const nozzlesError = ref(null);
const supplyPointCutStatusToken = ref(null);
const activeTab = ref('nozzles');
const SubRegion = ref(props.isSubRegionOpen);
const observationNumber = ref(0)
const documentNumber = ref(0)
const position_id = ref(null)
const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
});     //used for nozzles

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ClusterApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

// The backend marks the supply point with the status set in
// 'supply_point_status_cut_token' when it has an active supply cut.
const loadSupplyPointCutStatusToken = async () => {
  try {
    supplyPointCutStatusToken.value = await $ConfigProjectApiService.get('supply_point_status_cut_token');
  } catch (err) {
    supplyPointCutStatusToken.value = null;
  }
}

const isNozzleCut = (nozzle) => {
  if (!supplyPointCutStatusToken.value) return false;
  return nozzle.supply_points?.[0]?.status_token === supplyPointCutStatusToken.value;
}

const getNozzles = async (clusterId) => {
  if (!objectPermissions.value?.can_view) return
  nozzlesPending.value = true;
  nozzlesError.value = null;
  try {
    const result = await $ClusterApiService.getNozzles(clusterId, pagination.value.page);
    nozzles.value = [];
    result.results.forEach(nozzle => {
      if (nozzle.split_from == null) {
        nozzles.value.push(nozzle);
      }
      else {
        splitNozzles.value.push(nozzle);
      }
    });
    Object.assign(pagination.value, {
      total: result.count,
      totalPages: Math.ceil(result.count / pagination.value.perPage),
      previous: result.previous,
      next: result.next,
    });
    // nozzles.value = result.results;
  } catch (err) {
    nozzlesError.value = err;
  } finally {
    nozzlesPending.value = false;
  }
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getNozzles(props.id);
}

const getData = async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = true;
  error.value = null;
  try {
    const result = await $ClusterApiService.getDetail(props.id);
    data.value = result;
    documentNumber.value = (result.documentation_files || []).filter(d => d.is_active !== false).length;
    await getNozzles(props.id); // Crida per obtenir els supply_points després de les dades del clúster
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  loadSupplyPointCutStatusToken();
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    await getData();
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

const handlePositionChanged = () => {
  //closeSubRegion();
  //getData();
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}
const showCluster = function (res) {
  showRegionDetailComponent.value = res.component;
  regionDetailId.value = res.id;
  position_id.value = res.position_id;
  showSubRegion();
}

const getStrDestinationFromSupply = (nozzle) => {
  if (nozzle.supply_points && nozzle.supply_points.length > 0 && nozzle.supply_points[0].address) {
    return nozzle.supply_points[0].address.floor || '' + ' ' + nozzle.supply_points[0].address.door || '' + ' ' + nozzle.supply_points[0].address.stair || '' + ' ' + nozzle.supply_points[0].address.building || '';
  }
}

const handleClickChangeClusterStatus = () => {
  closeSubRegion();
  showRegionDetailComponent.value = 'ClusterChangeStatus';
  showSubRegion();
}

const handleStatusChanged = () => {
  closeSubRegion();
  getData();
  emit('changed');
}

const edit = function () {
  navigateTo('/service/clusters/edit/' + props.id);
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}
</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('cluster') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('cluster')}`" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <ClusterDetail @show-detail="showCluster" :id="props.id" :data="data" :nozzles="nozzles" :isSubRegion="isSubRegion"
          @clickChangeStatus="handleClickChangeClusterStatus" :canChange="objectPermissions?.can_change"></ClusterDetail>
        <AtomsTabs>
          <li class="me-2">
            <a href="#tab_nozzles" @click.prevent="setActiveTab('nozzles')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'nozzles', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'nozzles' }"
              aria-current="page">
              <Icon name="fa6-solid:street-view" class="display-inline mr-2" />{{ $t("common.supplys") }}
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }">
              <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.observations") }} ({{
                observationNumber }})
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_documents" @click.prevent="setActiveTab('documents')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'documents', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'documents' }">
              <Icon name="fa6-solid:file" class="display-inline mr-2" /> {{ $t("common.docs") }} ({{ documentNumber }})
            </a>
          </li>
        </AtomsTabs>
        <div id="tabpanels">
          <section v-show="activeTab === 'nozzles'" role="tabpanel" id="tab_nozzles" class="bg-white antialiased py-3 flex flex-col"
          :style="{
            maxWidth: '100%',
            minHeight: 'calc(100vh - 320px)',
            maxHeight: 'calc(100vh - 320px)',
          }">
            <div v-if="nozzlesPending" class="flex-1">
              <p>{{ $t('common.loading') }}...</p>
            </div>
            <div v-else-if="nozzlesError" class="flex-1">
              <p>{{ $t('common.error') }}: {{ nozzlesError.message }}</p>
            </div>
            <div v-else class="flex flex-col flex-1 min-h-0">
              <div class="flex-1 overflow-y-auto overflow-x-auto">
                <div v-for="(nozzle, index) in nozzles" :key="index"
                  :class="[index % 2 === 0 ? 'bg-slate-100' : 'bg-white', { 'bg-red-100 text-red-700': isNozzleCut(nozzle) }]">
                  <div class="grid grid-cols-[50px,1fr,60px,80px,50px,60px,180px,110px,60px]">
                    <span>{{ index + 1 }}.</span>
                    <span>
                      <strong class="font-medium">{{ nozzle.token }}</strong>
                      <Icon v-if="isNozzleCut(nozzle)" name="fa6-solid:droplet-slash" class="ml-1 text-red-600"
                        :title="t('service_block.active_supply_cut_warning')" />
                    </span>
                    <span>{{ nozzle.status?.name || nozzle.status?.token }}</span>
                    <span><em class="not-italic text-slate-400">{{t('common.type')}}:</em> {{ nozzle.type?.name || nozzle.type?.token
                      }}</span>
                    <span><em class="not-italic text-slate-400">{{t('editor_block.row')}}:</em> {{ nozzle.row }}</span>
                    <span><em class="not-italic text-slate-400">{{t('editor_block.short_column')}}:</em> {{ nozzle.col }}</span>
                    <span><em class="not-italic text-slate-400">{{t('service_block.usage_destination')}}:</em> {{ nozzle.destination ? nozzle.destination : getStrDestinationFromSupply(nozzle)}}</span>

                    <span>
                      <em class="not-italic text-slate-400">{{ t('meter') }}:</em>
                      <template v-if="nozzle.supply_points[0]?.meter_code">
                        <span v-if="isSubRegion">{{ nozzle.supply_points[0]?.meter_code }}</span>
                        <button v-else @click="showDetail('MeterRegion', nozzle.supply_points[0]?.meter_id)"
                          class="text-sky-500 underline hover:no-underline">{{ nozzle.supply_points[0]?.meter_code
                          }}</button>
                      </template>
                      <span v-else>-</span>
                    </span>

                    <span v-if="isSubRegion">{{ nozzle.supply_points[0]?.token || '-' }}</span>
                    <button v-else-if="nozzle.supply_points[0] && !isSubRegion"
                      @click="showDetail('SupplyPointRegion', nozzle.supply_points[0]?.id)"
                      class="text-sky-500 underline hover:no-underline">{{ nozzle.supply_points[0]?.token || '-'
                      }}</button>
                    <span v-else>-</span>

                  </div>
                  <div v-for="(split, index) in splitNozzles" :key="index">
                    <div v-if="split.split_from == nozzle.id"
                      class="grid grid-cols-[50px,1fr,60px,80px,50px,60px,180px,110px,60px]"
                      :class="{ 'bg-red-100 text-red-700': isNozzleCut(split) }">
                      <span></span>
                      <span>
                        <strong class="font-medium">{{ split.token }}</strong>
                        <Icon v-if="isNozzleCut(split)" name="fa6-solid:droplet-slash" class="ml-1 text-red-600"
                          :title="t('service_block.active_supply_cut_warning')" />
                      </span>
                      <span>{{ split.status?.name || split.status?.token }}</span>
                      <span><em class="not-italic text-slate-400">{{t('common.type')}}:</em> {{ split.type?.name || split.type?.token
                        }}</span>
                      <span><em class="not-italic text-slate-400">{{t('editor_block.row')}}:</em> {{ split.row }}</span>
                      <span><em class="not-italic text-slate-400">{{t('editor_block.short_column')}}:</em> {{ split.col }}</span>
                      <span><em class="not-italic text-slate-400">{{t('service_block.usage_destination')}}:</em> {{ split.destination }}</span>

                      <span>
                        <em class="not-italic text-slate-400">{{ t('meter') }}:</em>
                        <template v-if="split.supply_points[0]?.meter_code">
                          <span v-if="isSubRegion">{{ split.supply_points[0]?.meter_code }}</span>
                          <button v-else @click="showDetail('MeterRegion', split.supply_points[0]?.meter_id)"
                            class="text-sky-500 underline hover:no-underline">{{ split.supply_points[0]?.meter_code
                            }}</button>
                        </template>
                        <span v-else>-</span>
                      </span>

                      <span v-if="isSubRegion">{{ split.supply_points[0]?.token || '-' }}</span>
                      <button v-else-if="split.supply_points[0] && !isSubRegion"
                        @click="showDetail('SupplyPointRegion', split.supply_points[0]?.id)"
                        class="text-sky-500 underline hover:no-underline">{{ split.supply_points[0]?.token || '-'
                        }}</button>
                      <span v-else>-</span>
                    </div>
                  </div>
                </div>
                <div id="list__footer" class="sticky bottom-0 bg-white border-t border-gray-200 pt-2 pb-2 z-10">
                  <Pagination v-if="nozzles.length > 0" :pagination="pagination" @update:page="handlePageChange" />
                </div>
              </div>
            </div>
          </section>
          <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
            class="bg-white antialiased py-3 flex flex-col"
            :style="{
              minHeight: 'calc(100vh - 320px)',
              maxHeight: 'calc(100vh - 320px)',
            }">
            <div class="flex-1 overflow-y-auto">
              <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
                parent_entity="cluster" :id="props.id" module="service"></MoleculesObservationList>
            </div>
          </section>
          <section v-show="activeTab === 'documents'" role="tabpanel" id="tab_documents"
            class="bg-white antialiased py-3">
            <ClusterDocumentsData v-if="data" :cluster="data" @update-item="(updated) => { data = updated; documentNumber = (updated.documentation_files || []).filter(d => d.is_active !== false).length; }" />
          </section>
        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ChangeStatus v-if="showRegionDetailComponent === 'ClusterChangeStatus'" entity="cluster"
          parent_entity="cluster" :id="props.id" :status="data.status?.id" module="service"
          @changed="handleStatusChanged" />
        <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :id="regionDetailId" :isSubRegion="true" />
        <OrganismsConnectionRegion v-if="showRegionDetailComponent === 'ConnectionRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <OrganismsRoutePositionEdit v-if="showRegionDetailComponent === 'RouteRegion'" :id="regionDetailId"
          :position_id="position_id" :isSubRegion="true" @change="handlePositionChanged" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
