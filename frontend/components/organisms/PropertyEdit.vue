<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';

const props = defineProps({
  property: Object
});

const { t } = useI18n();
const { $PropertyApiService, $RouteApiService } = useNuxtApp();
const toast = useToast();
const objectPermissions = ref(null);
const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const name = ref(null);
const token = ref(null);
const cadastral = ref(null);
const latitude = ref(null);
const longitude = ref(null);

const route_position = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const addingToRoute = ref(false);
const editingRoutePosition = ref(false);
const assigningRoute = ref(false);

const address_data = ref({});

const getData = async () => {

  if (props.property != null && props.property.id > 0) {
    setValues();
  }
  else {
    token.value = _.random(100000, 999999)
  }

  loading.value = false;
}

const handleUpdateAddressData = async (updatedValue) => {
  address_data.value = updatedValue;
};

const save = async () => {

  attemptedSave.value = true;
  if (isValid()) {
    saving.value = true;

    const data = {
      token: token.value,
      name: name.value,
      cadastral: cadastral.value,
      latitude: latitude.value,
      longitude: longitude.value,
      is_active: true,
    };

    if (props.property != null) {
      data.id = props.property.id;
    }

    if (address_data.value != null) {
        data.address_city_id = address_data.value?.city?.code;
        data.address_postal_code_id = address_data.value?.cp?.code;

        data.address_street_id = address_data.value?.streetId;
        data.address_street_name = address_data.value?.street_name;
        data.address_street_type_id = address_data.value?.street_type?.code;
        data.address_street_type_abbreviation = address_data.value?.street_type?.label;
        data.address_street_number_id = address_data.value?.streetNumberId;
        data.address_street_number_number = address_data.value?.streetNumberNumber;
        data.address_street_number_number_end = address_data.value?.streetNumberEnd || null;
        data.address_street_number_number_suffix = address_data.value?.streetNumberSuffix || null;
        data.address_street_number_number_end_suffix = address_data.value?.streetNumberEndSuffix || null;
        data.address_street_number_type = address_data.value?.streetNumberType;
      }

    $PropertyApiService.save(data)

    return navigateTo('/service/properties/')
  }
  else {
    saving.value = false;
  }
}

const setValues = () => {
  name.value = props.property.name;
  token.value = props.property.token;
  cadastral.value = props.property.cadastral;
  latitude.value = props.property.latitude;
  longitude.value = props.property.longitude;
  route_position.value = props.property.route_position;
}

const isValid = () => {
  if (token.value == '' || token.value == null) return false;
  return true;
}

const openRegion = (region) => {
  closeAllRegions();

  if (region === 'route') {
    addingToRoute.value = true;
  }
  else if (region === 'edit_position') {
    editingRoutePosition.value = true;
  }

  showRegion.value = true;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    addingToRoute.value = false;
    editingRoutePosition.value = false;
  }
}

const closeAllRegions = () => {
  showRegion.value = false;
  isSubRegionOpen.value = false;
  addingToRoute.value = false;
  editingRoutePosition.value = false;
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

const onPositionUpdated = (updatedPosition) => {
  route_position.value = updatedPosition;
  toast.success(t('common.saved_successfully'));
  closeAllRegions();
};

const onRouteSelected = async (route) => {
  if (assigningRoute.value) return;
  assigningRoute.value = true;

  try {
    const occupied = await $RouteApiService.getOccupiedPositions(route.id);
    const position = (occupied.last_position || 0) + 1;
    const routeToken = route.token;

    const data = {
      name: '',
      token: `${routeToken}_${position}`,
      notebook: '',
      reader_observation: '',
      position,
      supply_points_ids: [],
      property_ids: [props.property.id],
      route_id: route.id,
      address_postal_code: null,
      address_city: null,
      address_street: null,
      address_street_number: null,
      latitude: 0,
      longitude: 0,
    };

    await $RouteApiService.createRoutePosition(data);

    const updatedProperty = await $PropertyApiService.getDetail(props.property.id);
    route_position.value = updatedProperty.route_position;

    toast.success(t('common.saved_successfully'));
    closeAllRegions();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    assigningRoute.value = false;
  }
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($PropertyApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  getData()
});

const deleteProperty = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    await $PropertyApiService.deleteProperty(props.property.id);
    return navigateTo('/service/properties/')
  }
}

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div v-if="loading">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="border border-gray-300 rounded p-4 bg-white">
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
          <input type="text" :disabled="props.property != null" v-model="token" class="input" :class="{ 'invalid': attemptedSave && ( token == '' || attemptedSave && token == null ) }" />
        </div>
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="name" class="input" :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }"/>
        </div>
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.cadastral') }}</label>
          <input type="text" v-model="cadastral" class="input" :class="{ 'invalid': attemptedSave && cadastral == '' || attemptedSave && cadastral == null }"/>
        </div>
        <MoleculesAddPartialAddress class="col-span-2" :attempted_save="attemptedSave" :data="props.property" @valueChanged="handleUpdateAddressData" />
        <div v-if="route_position" class="col-span-2 mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('route') }}</label>
          <div class="grid grid-cols-[2fr,1fr,1fr,auto] gap-2 items-end">
            <div>
              <input type="text"
                :value="`${route_position.route?.token} - ${route_position.route?.name}`"
                class="input w-full"
                disabled />
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">{{ t('order') }}</label>
              <input type="text" :value="route_position.position" class="input w-full text-center" disabled />
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">{{ t('common.identificator') }}</label>
              <input type="text" :value="route_position.token" class="input w-full" disabled />
            </div>
            <button @click="openRegion('edit_position')"
              class="button-default h-11 w-11 flex items-center justify-center"
              :title="t('common.modify')">
              <Icon name="fa6-solid:pencil" />
            </button>
          </div>
        </div>
        <div v-else-if="props.property != null" class="col-span-2 mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('route') }}</label>
          <button @click="openRegion('route')" class="button-default">
            <Icon name="fa6-solid:plus" />&nbsp; {{ t('common.add') }} {{ t('route').toLowerCase() }}</button>
        </div>
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.latitude') }}</label>
          <input type="text" v-model="latitude" class="input" />
        </div>
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.longitude') }}</label>
          <input type="text" v-model="longitude" class="input"/>
        </div>
      </div>

      <div class="col-span-3 flex flex-row-reverse mt-4">
        <button v-if="props.property != null" @click="deleteProperty" class="button-default mx-5">
          &nbsp; {{ $t('common.delete') }}</button>
        <button @click="save" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}</button>
      </div>

    </div>
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10 overflow-x-hidden"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300"><Icon name="fa6-solid:angles-right"
            class="text-slate-500" /></button>
      </div>
      <div class="h-full" :class="{ 'overflow-y-auto px-10 pb-24': !editingRoutePosition }">
        <MoleculesAddRoute v-if="addingToRoute" :selected_items="[]" @item-clicked="onRouteSelected" />
        <div :class="{ 'px-10 pb-24 h-full': editingRoutePosition }">
          <OrganismsAddRoutePosition v-if="editingRoutePosition"
            :routeToken="route_position?.route?.token + ''"
            :route_id="route_position?.route?.id"
            :editingPosition="route_position"
            :selectedOptions="[]"
            :numPositions="0"
            :isSubRegionOpen="isSubRegionOpen"
            @created="onPositionUpdated"
            @show-subregion="handleSubRegionEvent" />
        </div>
      </div>
    </div>
  </div>
</template>
