<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import ButtonAcceptarRegion from '~/components/atoms/ButtonAcceptarRegion.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';

import SupplyPointRequestDetail from '~/components/molecules/SupplyPointRequestDetail.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
});

const emit = defineEmits(['accept', 'show-subregion', 'deleted']);

const router = useRouter();
const { $SupplyPointRequestApiService, $ConfiglistApiService, $LoggerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('observations');
const observationNumber = ref(0)
const logNumber = ref(0)

const editingChangeStatus = ref(false);
const SubRegion = ref(false);
const statuses = ref([]);

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateLogCount = (num) => {
  logNumber.value = num;
}

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {

    // agafem la llista d'statuses
    ({ results: statuses.value } = await $ConfiglistApiService.getAll('service/supply-point-request-status'));

    // agafem els valors de l'entitat
    const result = await $SupplyPointRequestApiService.getDetail(props.id);

    data.value = result;

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  getData();
});

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

getData();

const closeSubRegion = function () {
  SubRegion.value = false;
  regionDetailId.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

// subregions details

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (res) {
  showRegionDetailComponent.value = res.component;
  regionDetailId.value = res.id;
  showSubRegion();
}


const deleteRequest = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    await $SupplyPointRequestApiService.deleteRequest(props.id);
    emit('deleted')
  }
}

const handleStatusChanged = () => {
  closeSubRegion();
  getData();
}

const handleClickChangeStatus = () => {
  showSubRegion();
  editingChangeStatus.value = true;
}

const handleClickModify = () => {
  router.push(`/service/supplypoint-requests/edit/${props.id}`);
}
const goToSupplyPoint = () => {
  router.push(`/service/supplypoints?id=${data.value.supply_point}`);
}

</script>

<template>
  <div class="region__content">
    <div v-if="pending" class="h-full min-h-[400px]">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>{{t('common.error')}}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between">
        <H1Region class="mb-3">{{ $t('service_block.supply_point_request') }}</H1Region>
        <div class="relative">
          <OptionsDropdown id="ConnectionRequestRegionOptions">
            <DropdownOption :disabled="data.supply_point != null" :name="`${$t('common.modify')} ${$t('common.request')}`"
              @click="handleClickModify"></DropdownOption>
              <DropdownOption :name="`${$t('common.change')} ${$t('common.status')}`" @click="handleClickChangeStatus"></DropdownOption>
              <DropdownOption :name="`${$t('common.delete')} ${$t('common.request')}`" @click="deleteRequest"></DropdownOption>
            <hr class="my-2" />
            <DropdownOption :disabled="data.supply_point == null" :name="`${$t('common.show')} ${$t('supply_point')}`"
              @click="goToSupplyPoint"></DropdownOption>
          </OptionsDropdown>
        </div>
      </div>

      <AtomsStatusesNav :statuses="statuses" :active="data.status" class="my-3 mb-6" />

      <div v-if="pending">
        <AppLoading :text="$t('common.loading')" :size="40" />
      </div>
      <div v-else>
        <SupplyPointRequestDetail :id="props.id" @clickChangeStatus="handleClickChangeStatus">
        </SupplyPointRequestDetail>
      </div>

      <AtomsTabs>
        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("observations") }} ({{
              observationNumber }})
          </a>
        </li>
        <li class="me-2">
          <a href="#tab_log" @click.prevent="setActiveTab('log')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("common.history") }} ({{ logNumber }})
          </a>
        </li>
      </AtomsTabs>
      <div id="cluster_tabpanels">
        <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations"
          class="bg-white antialiased">
          <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount"
            parent_entity="supplypoint_request" url_entity="supply-point-request" :id="props.id" module="service">
          </MoleculesObservationList>
        </section>
        <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log" class="bg-white antialiased">
          <MoleculesLogList v-if="data" entity="supply-point-request-status" parent_entity="supplypoint_request"
            :id="props.id" @update:count="updateLogCount" :service="$LoggerApiService">
          </MoleculesLogList>
        </section>
      </div>
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ChangeStatus v-if="editingChangeStatus" entity="supply-point-request" parent_entity="supplypoint_request"
          :id="props.id" :status="data.status?.id" module="service" @changed="handleStatusChanged" />
      </div>
    </div>

  </div>
</template>
