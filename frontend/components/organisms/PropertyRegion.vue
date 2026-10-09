<script setup>
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import PropertyDetail from '~/components/molecules/PropertyDetail.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import SupplyPointRegion from './SupplyPointRegion.vue';
import MoleculesAddSupplyPoints from '~/components/molecules/AddSupplyPoints.vue';

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
const { $PropertyApiService, $SupplyPointApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const SubRegion = ref(props.isSubRegionOpen);
const objectPermissions = ref(null);
const activeTab = ref('supplypoints');

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $PropertyApiService.getPermissions();
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
    const result = await $PropertyApiService.getDetail(props.id);
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

watch(() => props.id, () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  closeSubRegion();
  getData();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
  if (!newValue) {
    showRegionDetailComponent.value = null;
  }
});

const edit = function () {
  navigateTo('/service/properties/edit/' + props.id);
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = (component, id) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const supplyPointClicked = async (supplyPoint) => {
  if (!supplyPoint || !supplyPoint.id) return;
  const currentIds = (data.value?.supply_points || []).map(sp => sp.id);
  const index = currentIds.indexOf(supplyPoint.id);
  if (index > -1) {
    currentIds.splice(index, 1);
  } else {
    currentIds.push(supplyPoint.id);
  }

  try {
    const payload = [{
      property_id: Number(props.id),
      supply_points: currentIds
    }];
    await $SupplyPointApiService.bulkUpdateProperty(payload);
    await getData();
    toast.success(t('common.saved_successfully') || 'Guardat correctament');
  } catch (err) {
    console.error('Failed to update property supply points:', err);
    toast.error(t('common.error'));
  }
}

const removeSupplyPoint = async (supplyPoint) => {
  if (!supplyPoint || !supplyPoint.id) return;
  const currentIds = (data.value?.supply_points || []).map(sp => sp.id).filter(id => id !== supplyPoint.id);
  try {
    const payload = [{
      property_id: Number(props.id),
      supply_points: currentIds
    }];
    await $SupplyPointApiService.bulkUpdateProperty(payload);
    await getData();
    toast.success(t('common.saved_successfully') || 'Guardat correctament');
  } catch (err) {
    console.error('Failed to remove supply point from property:', err);
    toast.error(t('common.error'));
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
  closeSubRegion();
  await getData();
});
</script>

<template>
  <div class="region__content h-full">

    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('property') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('property')}`" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>


      <div v-if="data" id="item_data" :data-rel=id>
        <PropertyDetail :id="props.id" :data="data"></PropertyDetail>
        <div class="border-b border-gray-200">
          <ul class="flex flex-wrap -mb-px text-sm font-medium text-center text-gray-500">
            <li class="me-2">
              <a href="#tab_supplypoints" @click.prevent="setActiveTab('supplypoints')"
                :class="{ 'text-sky-600 border-sky-600': activeTab === 'supplypoints', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'supplypoints' }"
                class="inline-flex items-center justify-center p-4 border-b-2 rounded-t-lg group" aria-current="page">
                <Icon name="fa6-solid:street-view" class="display-inline mr-2" />{{ $t("common.short_supply_points") }}
                ({{
                  data.supply_points?.length }})
              </a>
            </li>
          </ul>
        </div>
        <div id="tabpanels">
          <section v-show="activeTab === 'supplypoints'" role="tabpanel" id="tab_supplypoints"
            class="bg-white antialiased py-3">
            <div class="mb-3">
              <button v-if="objectPermissions?.can_change" @click="showDetail('AddSupplyPoints', null)" class="button-primary text-sm py-1 px-3">
                <Icon name="fa6-solid:plus" class="mr-1" /> {{ t('common.add') }} {{ t('supply_point') }}
              </button>
            </div>
            <div class="divide-y divide-slate-300">
              <div class="grid grid-cols-[1fr,2fr,1fr,1fr,30px] gap-3 pt-2 font-bold items-center">
                <span>{{ t('common.identification') }}</span>
                <span>{{ t('address_block.address') }}</span>
                <span>{{ t('common.type') }}</span>
                <span>{{ t('common.status') }}</span>
                <span></span>
              </div>
              <div v-if="data.supply_points && data.supply_points.length > 0" class="max-h-[55vh] overflow-y-auto">
                <div v-for="item in data.supply_points" :key="item.id"
                  class="grid grid-cols-[1fr,2fr,1fr,1fr,30px] gap-3 py-2 border-b items-center group">
                  <span>
                    <button v-if="!props.isSubRegionOpen"
                      class="group flex justify-between w-full items-center p-1 text-sky-500 text-nowrap text-left"
                      @click="showDetail('SupplyPointRegion', item.id)">
                      {{ item.token }}
                    </button>
                    <span v-else>{{ item.token }}</span>
                  </span>
                  <span>{{ item.address_complete }}</span>
                  <span>{{ item.type_name || item.type_token }}</span>
                  <span>
                    <AtomsColorBadge :value="item.status_name || item.status_token" :color="item.status_color">
                    </AtomsColorBadge>
                  </span>
                  <span class="text-center">
                    <button v-if="objectPermissions?.can_change" @click="removeSupplyPoint(item)" class="text-slate-400 hover:text-red-600 transition-colors duration-200" :title="t('common.delete')">
                      <Icon name="fa6-solid:trash" />
                    </button>
                  </span>
                </div>
              </div>
              <div v-else>
                <span class="text-slate-500">{{ t('common.no_records') }}</span>
              </div>
            </div>
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
        <!-- Subregions aqui -->
        <SupplyPointRegion v-if="showRegionDetailComponent === 'SupplyPointRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <MoleculesAddSupplyPoints v-if="showRegionDetailComponent === 'AddSupplyPoints'"
          :selected_items="data?.supply_points || []" @item-clicked="supplyPointClicked"
          :multiple="true" :show="true" />

        <!-- /end Subregions aqui -->
      </div>
    </div>
  </div>
</template>
