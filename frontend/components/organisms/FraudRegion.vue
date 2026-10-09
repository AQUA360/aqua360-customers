<script setup>
import { useRouter } from 'vue-router';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import FraudDetail from '../molecules/FraudDetail.vue';
import ContractRegion from './ContractRegion.vue';
import SupplyPointRegion from './SupplyPointRegion.vue';
import FraudReportMiniDetail from '../molecules/FraudReportMiniDetail.vue';
import AddFraud from '../molecules/AddFraud.vue';
import FraudReportEdit from '../molecules/FraudReportEdit.vue';
import PersonRegion from './PersonRegion.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);

const router = useRouter();
const { $FraudApiService, $ConfigProjectApiService } = useNuxtApp();
const objectPermissions = ref(null);
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('reports');

const observationNumber = ref(0)
const reportNumber = ref(0)
const logNumber = ref(0)

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const pendingStatusFraudToken = ref(null)
const activeStatusFraudToken = ref(null)
const expiredStatusFraudToken = ref(null)
const resolvedStatusFraudToken = ref(null)

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const updateReportCount = (num) => {
  reportNumber.value = num;
}

const updateLogCount = (num) => {
  logNumber.value = num;
}

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $FraudApiService.getPermissions();
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
  error.value = null;
  try {
    const result = await $FraudApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = async function (component, id) {
  await closeSubRegion()
  showRegionDetailComponent.value = component
  regionDetailId.value = parseInt(id);
  showSubRegion();
}

const refresh = async (close = true) => {
  await getData()
  if (close) closeSubRegion()
  emit('changed')
}

const changeStatus = async (token) => {
  if (!confirm(t("confirmation_text_block.confirm_change_status"))) return
  try {
    let save_data = {
      id: props.id,
      status_token: token
    }
    const response = await $FraudApiService.save(save_data);
    if (response) {
      refresh()
    }
  } catch (error) {
    console.error('Error saving document:', error);
  }
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
});

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  }
  expiredStatusFraudToken.value = await $ConfigProjectApiService.get('fraud_status_expired_token');
  pendingStatusFraudToken.value = await $ConfigProjectApiService.get('fraud_status_pending_token');
  activeStatusFraudToken.value = await $ConfigProjectApiService.get('fraud_status_active_token');
  resolvedStatusFraudToken.value = await $ConfigProjectApiService.get('fraud_status_resolved_token');
  getData();
});
</script>

<template>
  <div class="region__content">
    <div v-if="pending || loading">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions.can_view" class="transition-all duration-500 ease"
      :class="{ 'mr-[47%]': SubRegion }">
      <div class="flex justify-between relative mb-3">
        <H1Region class="mb-3">{{ $t('common.fraud_records') }}</H1Region>
        <OptionsDropdown
          v-if="(((data.status.token != expiredStatusFraudToken) || (data.status.token != resolvedStatusFraudToken))) && objectPermissions.can_change"
          id="FraudRegionOptions">
          <DropdownOption :name="`${t('common.modify')}`" @click="showDetail('AddFraud', props.id)">
            <Icon name="fa6-solid:pencil" class="display-inline mr-2" /> {{ t('common.modify') }}
          </DropdownOption>
          <DropdownOption v-if="data.status.token == pendingStatusFraudToken" :name="`${t('common.activate')}`"
            @click="changeStatus(activeStatusFraudToken)">
            <Icon name="fa6-solid:toggle-on" class="display-inline mr-2" /> {{ t('common.activate') }}
          </DropdownOption>
          <DropdownOption v-if="data.status.token == activeStatusFraudToken" :name="`${t('service_block.mark_as_resolved')}`"
            @click="changeStatus(resolvedStatusFraudToken)">
            <Icon name="fa6-solid:circle-check" class="display-inline mr-2" /> {{ t('service_block.mark_as_resolved') }}
          </DropdownOption>
          <DropdownOption v-if="data.status.token == activeStatusFraudToken" :name="`${t('common.add')} ${t('common.report_detail')}`"
            @click="showDetail('FraudReportEdit', null)">
            <Icon name="fa6-solid:paperclip" class="display-inline mr-2" /> {{ t('common.add') }} {{ t('common.report_detail') }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <FraudDetail :id="props.id" :data="data" @show-detail="showDetail" :isSubRegion="isSubRegion" />
      </div>

      <AtomsTabs>

        <li class="me-2">
          <a href="#tab_reports" @click.prevent="setActiveTab('reports')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'reports', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'reports' }"
            aria-current="page">
            <Icon name="fa6-solid:newspaper" class="display-inline mr-2" />
            {{ $t('common.reports') }} ({{ reportNumber }})
          </a>
        </li>

        <li class="me-2">
          <a href="#tab_observations" @click.prevent="setActiveTab('observations')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'observations', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'observations' }"
            aria-current="page">
            <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t('common.observations') }} ({{
              observationNumber }})
          </a>
        </li>

        <li class="me-2">
          <a href="#tab_log" @click.prevent="setActiveTab('log')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'log', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'log' }">
            <Icon name="fa6-solid:list" class="display-inline mr-2" /> {{ $t('common.history') }} ({{ logNumber }})
          </a>
        </li>

      </AtomsTabs>

      <section v-show="activeTab === 'observations'" role="tabpanel" id="tab_observations" class="bg-white antialiased">
        <MoleculesObservationList v-if="data" @update:observation-count="updateObservationCount" parent_entity="fraud"
          url_entity="fraud" :id="props.id" module="fraud">
        </MoleculesObservationList>
      </section>

      <section v-show="activeTab === 'reports'" role="tabpanel" id="tab_reports" class="bg-white antialiased">
        <FraudReportMiniDetail v-if="data" @show-detail="showDetail" :id="props.id" @update:count="updateReportCount" />
      </section>

      <section v-show="activeTab === 'log'" role="tabpanel" id="tab_log" class="bg-white antialiased">
        <MoleculesLogList v-if="data" entity="fraud-status" parent_entity="fraud" :id="props.id"
          @update:count="updateLogCount" :service="$LoggerApiService">
        </MoleculesLogList>
      </section>

    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
    class="h-full border-l border-gray-100 py-2 text-base bg-white transition-all duration-500 ease fixed top-0 right-0 z-10 w-[47%] overflow-y-auto overflow-x-hidden"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }"
      >
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <PersonRegion v-if="showRegionDetailComponent === 'PersonRegion'" :id="regionDetailId" :isSubRegion="true" />
        <AddFraud v-if="showRegionDetailComponent === 'AddFraud'" :id="data.id" @changed="refresh()" />
        <FraudReportEdit v-if="showRegionDetailComponent === 'FraudReportEdit'" :fraud_id="data.id" :id="regionDetailId"
          @changed="refresh" :canChange="objectPermissions?.can_change" />
      </div>
    </div>
  </div>
</template>
