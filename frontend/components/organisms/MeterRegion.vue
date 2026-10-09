<script setup>
// components/organisms/MeterRegion.vue
import { ref, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import MeterDetail from '~/components/molecules/MeterDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import SupplyPointRegion from '~/components/organisms/SupplyPointRegion.vue';
import MeterSupplyPoints from '../molecules/MeterSupplyPoints.vue';
import ReadingDetail from '../molecules/ReadingDetail.vue';
import ContractRegion from '~/components/organisms/ContractRegion.vue';
import ModelLogs from '../molecules/ModelLogs.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import { AppColors } from '~/utils/config';

const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean,
  hideSupplyPoints: Boolean
});

const emit = defineEmits(['show-subregion', 'close-subregion']);

const router = useRouter();
const { $MeterApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('supply_points');
const SubRegion = ref(props.isSubRegionOpen);
const isGeneral = ref(false);
const objectPermissions = ref(null);
activeTab.value = props.hideSupplyPoints ? 'comunicacio' : 'supply_points';

const activeToken = ref(null)
const deactivateToken = ref(null)

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $MeterApiService.getPermissions();
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
    const result = await $MeterApiService.getDetail(props.id);
    data.value = result;

    isGeneral.value = data.value.is_general;
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  getData();
  regionDetailId.value = 0;
  closeSubRegion();
});


watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});


const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const changeMeterStatus = async (token) => {
  try {
    if (!confirm(t('confirmation_text_block.confirm_modify'))) return;
    let save_data = {
      id: props.id,
      status_token: token
    }
    let response = await $MeterApiService.updateStatus(save_data);
    if (response) {
      getData();
    }
  } catch (error) {
    console.error(error);
  }
}

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value?.can_view) {
    pending.value = false;
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  }
  await getData();
  activeToken.value = await $ConfigProjectApiService.get('meter_status_active_token');
  deactivateToken.value = await $ConfigProjectApiService.get('meter_status_inactive_token');
});
const closeSubRegion = function () {
  SubRegion.value = false;
  regionDetailId.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const edit = function () {
  navigateTo('/service/meters/edit/' + props.id);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const subMetersCount = computed(() => (data.value?.sub_meters && Array.isArray(data.value.sub_meters)) ? data.value.sub_meters.length : 0);

/** Formatea calle para mostrar: objeto API → "ABREV. Nombre", string → tal cual */
const formatStreetDisplay = (street) => {
  if (street == null || street === '') return '';
  if (typeof street === 'string') return street;
  const abbr = street.type_abbreviation ?? street.type?.abbreviation ?? '';
  const name = street.name ?? '';
  return name ? (abbr ? `${abbr}. ${name}` : name) : abbr;
};

/** Supply points del contador hijo: acepta supply_points, supply_point o supply_point_id */
const getSupplyPointsForItem = (item) => {
  const list = item?.supply_points;
  const single = item?.supply_point;
  const id = item?.supply_point_id;
  if (Array.isArray(list) && list.length > 0) return list;
  if (single && typeof single === 'object' && (single.id != null || single.token != null)) return [single];
  if (id != null) return [{ id: Number(id), token: String(id) }];
  return null;
};

/** Localización: del supply point si existe, si no del meter (address_street) */
const getLocationForItem = (item) => {
  const sps = getSupplyPointsForItem(item);
  const sp = sps?.[0];
  if (sp?.address_complete) return sp.address_complete;
  return formatStreetDisplay(item?.address_street) || '–';
};

/** Estado para badge; si hay supply point con status lo usamos */
const getStatusForRow = (item) => {
  const sps = getSupplyPointsForItem(item);
  const sp = sps?.[0];
  if (sp?.status_name != null || sp?.status?.name != null) {
    return { value: sp?.status_name ?? sp?.status?.name ?? '', color: sp?.status_color ?? sp?.status?.color ?? 'gray' };
  }
  return getStatusForBadge(item);
};

/** Estado para badge: item con status_name/status_color o status: { name, color } */
const getStatusForBadge = (item) => ({
  value: item?.status_name ?? item?.status?.name ?? '',
  color: item?.status_color ?? item?.status?.color ?? ''
});

const isRowSelected = (item) => {
  if (regionDetailId.value === item.id && showRegionDetailComponent.value === 'MeterRegion') return true;
  const sps = getSupplyPointsForItem(item);
  return sps?.some(sp => sp.id === regionDetailId.value) && showRegionDetailComponent.value === 'SupplyPointRegion';
};

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24" :class="{ 'h-full overflow-y-auto': !isSubRegion }">
      <div class="relative flex justify-between">
        <H1Region class="mb-3">{{ $t('meter') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="`${$t('common.modify')} ${$t('meter')}`" @click="edit"></DropdownOption>
          <DropdownOption :name="t('common.history_changes')" @click="showDetail('ShowLogs', props.id)"></DropdownOption>
          <DropdownOption v-if="data.status?.token == deactivateToken" :name="`${t('common.activate')}`" @click="changeMeterStatus(activeToken)"></DropdownOption>
          <DropdownOption v-if="data.status?.token == activeToken" :name="`${t('common.deactivate')}`" @click="changeMeterStatus(deactivateToken)"></DropdownOption>
        </OptionsDropdown>
      </div>


      <div v-if="data" id="item_data" :data-rel=id>

        <MeterDetail :id="props.id" :isSubRegion="props.isSubRegion" :isSubRegionOpen="props.isSubRegionOpen" :data="data"></MeterDetail>

        <AtomsTabs>
            <li v-if="!hideSupplyPoints" class="me-2">
              <a href="#tab_supply_points" @click.prevent="setActiveTab('supply_points')"
                :class="{ 'text-sky-600 border-sky-600': activeTab === 'supply_points', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'supply_points' }" >
                <Icon name="fa6-solid:list" class="display-inline mr-2" />{{ $t("common.supplys") }}
              </a>
            </li>
            <li v-if="!hideSupplyPoints" class="me-2">
              <a href="#tab_supply_children" @click.prevent="setActiveTab('supply_children')"
                :class="{ 'text-sky-600 border-sky-600': activeTab === 'supply_children', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'supply_children' }">
                <Icon name="fa6-solid:street-view" class="display-inline mr-2" />{{ $t("service_block.child_supply_points") }} ({{ subMetersCount }})
              </a>
            </li>
            <li class="me-2">
              <a href="#tab_comunicacio" @click.prevent="setActiveTab('comunicacio')"
                :class="{ 'text-sky-600 border-sky-600': activeTab === 'comunicacio', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'comunicacio' }"
                aria-current="page">
                <Icon name="fa6-solid:book" class="display-inline mr-2" />{{ $t("service_block.comm_tech") }}
              </a>
            </li>
            <li class="me-2">
              <a href="#tab_historial" @click.prevent="setActiveTab('historial')"
                :class="{ 'text-sky-600 border-sky-600': activeTab === 'historial', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'historial' }">
                <Icon name="fa6-solid:list" class="display-inline mr-2" />{{ $t("common.history_changes") }}
              </a>
            </li>
            <li class="me-2">
              <a href="#tab_lectures" @click.prevent="setActiveTab('lectures')"
                :class="{ 'text-sky-600 border-sky-600': activeTab === 'lectures', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'lectures' }">
                <Icon name="fa6-solid:list" class="display-inline mr-2" />{{ $t("readings") }}
              </a>
            </li>
          </AtomsTabs>
        <div id="tabpanels">
          <section v-if="!hideSupplyPoints" v-show="activeTab === 'supply_points'" role="tabpanel" id="tab_supply_points"
            class="bg-white antialiased py-3">
            <MeterSupplyPoints @show-detail="showDetail" :id="props.id" :isSubRegion="props.isSubRegion" :isSubRegionOpen="props.isSubRegionOpen" :selected="regionDetailId" :supply_points="data.supply_points"></MeterSupplyPoints>
          </section>
          <section v-if="!hideSupplyPoints" v-show="activeTab === 'supply_children'" role="tabpanel" id="tab_supply_children"
            class="bg-white antialiased py-3">
            <div v-if="data.sub_meters && data.sub_meters.length > 0" class="rounded-md border border-gray-300 overflow-hidden bg-white">
              <table class="w-full text-sm border-collapse" style="table-layout: fixed;">
                <colgroup>
                  <col style="width: 20%;" />
                  <col style="width: 18%;" />
                  <col style="width: 44%;" />
                  <col style="width: 18%;" />
                </colgroup>
                <thead>
                  <tr class="border-b border-gray-200 bg-slate-50">
                    <th class="text-left p-2 pl-3 text-slate-600 font-medium">{{ $t("supply_point") }}</th>
                    <th class="text-left p-2 pl-3 text-slate-600 font-medium">{{ $t("meter") }}</th>
                    <th class="text-left p-2 pl-3 text-slate-600 font-medium">{{ $t("address_block.address") }}</th>
                    <th class="text-left p-2 pl-3 text-slate-600 font-medium">{{ $t("common.status") }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in data.sub_meters" :key="item.id" class="border-b border-gray-100 hover:bg-slate-50/50" :class="{ 'bg-yellow-50': isRowSelected(item) }">
                    <td class="p-2 text-slate-800 align-middle">
                      <template v-if="getSupplyPointsForItem(item)">
                        <template v-for="(sp, idx) in getSupplyPointsForItem(item)" :key="sp.id">
                          <button v-if="!isSubRegion" type="button" @click.stop="showDetail('SupplyPointRegion', sp.id)" class="text-start text-sky-500 underline hover:no-underline block truncate" :class="{ 'mt-1': idx > 0 }">{{ sp.token ?? sp.address_complete ?? sp.id }}</button>
                          <span v-else :class="{ 'mt-1 block': idx > 0 }">{{ sp.token ?? sp.address_complete ?? sp.id }}</span>
                        </template>
                      </template>
                      <template v-else>
                        <!-- Sense punt de suministro: en blanc -->
                      </template>
                    </td>
                    <td class="p-2 text-slate-800 align-middle">
                      <button v-if="!isSubRegion" type="button" @click.stop="showDetail('MeterRegion', item.id)" class="text-start text-sky-500 underline hover:no-underline">{{ item.code }}</button>
                      <span v-else>{{ item.code }}</span>
                    </td>
                    <td class="p-2 text-slate-800 align-middle truncate" :title="getLocationForItem(item)">{{ getLocationForItem(item) }}</td>
                    <td class="p-2 text-slate-800 align-middle">
                      <AtomsColorBadge :value="getStatusForRow(item).value" :color="getStatusForRow(item).color" />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="footering text-slate-500 p-2">
              {{ $t('common.no_records') }}
            </div>
          </section>
          <section v-show="activeTab === 'comunicacio'" role="tabpanel" id="tab_comunicacio"
            class="bg-white antialiased py-3">
            <div role="row" class="grid grid-cols-2">
              <FieldDetail :label='$t("service_block.module")' :value=data.comm_module></FieldDetail>
              <FieldDetail :label='$t("service_block.comm_module_type")' :value=data.comm_module_type></FieldDetail>
              <FieldDetail :label='$t("service_block.tech")' :value=data.comm_technology></FieldDetail>
              <FieldDetail :label='$t("service_block.provider")' :value=data.network_provider></FieldDetail>
            </div>
          </section>
          <section v-show="activeTab === 'historial'" role="tabpanel" id="tab_historial"
            class="bg-white antialiased py-3">
            <ModelLogs :object_id="props.id" :service="$MeterApiService" :title="t('common.history_changes')" />
          </section>
          <section v-show="activeTab === 'lectures'" role="tabpanel" id="tab_lectures"
            class="bg-white antialiased py-3">
            <ReadingDetail :meter_id="props.id" :isSubRegion="isSubRegion" @show-detail="showDetail" />
          </section>
          
        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->


    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-full z-50"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <MeterRegion v-if="showRegionDetailComponent === 'MeterRegion'" :hideSupplyPoints="true" :id="regionDetailId"
          :isSubRegion="true" />
        <ContractRegion v-if="showRegionDetailComponent === 'ContractRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <ModelLogs v-if="showRegionDetailComponent === 'ShowLogs'" :object_id="regionDetailId"
          :service="$MeterApiService" :title="t('common.history_changes')" />
      </div>
    </div>
    
  </div><!-- end flex region-->
</template>