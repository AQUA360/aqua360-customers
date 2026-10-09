<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import LineItemTypeSimpleDetail from './LineItemTypeSimpleDetail.vue';
import LineItemTypeRegion from './LineItemTypeRegion.vue';
import PriceIntervalRegion from './PriceIntervalRegion.vue';
import DropdownOption from '../atoms/DropdownOption.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import TimeRelative from '../atoms/TimeRelative.vue';


const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
});

const emit = defineEmits(['show-subregion', 'changed', 'close']);
const { $PriceRateApiService, $BillingRangeApiService, $LoggerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeBillingRangeId = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const logChanges = ref([])
const showLogsDropdown = ref(false)
const logsDropdownWrapper = ref(null)

const toggleLogsDropdown = () => {
  showLogsDropdown.value = !showLogsDropdown.value;
}

const onLogsClickOutside = (event) => {
  if (!logsDropdownWrapper.value || logsDropdownWrapper.value.contains(event.target)) return;
  showLogsDropdown.value = false;
}

watch(showLogsDropdown, (visible) => {
  if (visible) {
    document.addEventListener('mousedown', onLogsClickOutside);
  } else {
    document.removeEventListener('mousedown', onLogsClickOutside);
  }
});

onUnmounted(() => {
  document.removeEventListener('mousedown', onLogsClickOutside);
});

const getLogs = async () => {
  const response = await $LoggerApiService.getAll('price-rate-change', props.id);
  logChanges.value = response.results;
}

const getData = async () => {
  pending.value = true;

  try {
    const result = await $PriceRateApiService.getDetail(props.id);
    data.value = result;
    activeBillingRangeId.value = data.value.billing_range_active?.id || null;
    await getLogs();
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const openPriceRate = () => {
  return navigateTo({
    path: '/pricing/price-rates/',
    query: {
      action: 'showDetail',
      pr_id: data.value.id
    }
  })
}

const deactivate = async () => {
  if (!confirm(t('confirmation_text_block.confirm_deactivate'))) return;
  try {
    let save_data = {
      id: data.value.id,
      is_active: false
    }
    let response = await $PriceRateApiService.save(save_data);
    if (response){
      toast.success(t('common.deactivated'));
      emit('close');
    }
    //await getData();
  } catch (err) {
    console.error(err);
  }
}

const edit = function () {
  //return navigateTo('/pricing/price-rates/edit/' + data.value.id);
  return navigateTo({
    path: '/pricing/price-rates/edit/' + data.value.id,
    query: {
      inprod: true
    }
  })
}

watch(() => props.id, () => {
  getData();
});

onMounted(async () => {
  objectPermissions.value = await checkPermission($PriceRateApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  getData();
});

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component
  regionDetailId.value = id
  toggleRegion(true);
}



const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  isSubRegionOpen.value = showRegion.value;
  if (showRegion.value == false) {
    showRegionDetailComponent.value = null
    regionDetailId.value = null
  }
}


</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending">
    <AppLoading :text="$t('common.loading')" />
  </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': showRegion }">
      <div v-if="data" id="item_data" :data-rel=id>
        <div class="flex justify-between items-center relative">
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-slate-500">{{ data.product.name }}</h2>
              <span v-if="!data.is_active" class="text-slate-500 italic">({{ t('common.deactivated') }})</span>
            </div>
            <AtomsH1Region class="mb-3">{{ data.name }}</AtomsH1Region>
          </div>
          <OptionsDropdown v-if="objectPermissions.can_change && data.is_active" id="OrderRegionOptions">
            <DropdownOption :name="`${t('common.modify')} ${t('price_rate').toLowerCase()}`" @click="edit"></DropdownOption>
            <DropdownOption :name="`${t('common.deactivate')} ${t('price_rate').toLowerCase()}`" @click="deactivate"></DropdownOption>
          </OptionsDropdown>
        </div>

        <div class="flex justify-end gap-2">
          <div v-if="data.is_return_fee"
            class="bg-orange-50 border border-orange-400 px-3 py-2 mb-4 flex items-center w-fit gap-2 rounded-md">
            <span class="text-orange-500 font-semibold">
              {{ t('return_fee') }}
            </span>
          </div>
          <div v-if="data.is_bail" class="bg-orange-50 border border-orange-400 px-3 py-2 mb-4 flex items-center w-fit gap-2 rounded-md">
            <!-- <Icon name="fa6-solid:circle-info" class="text-lg text-orange-400" /> -->
            <span class="text-orange-500 font-semibold">
              {{ t('bail') }}
            </span>
  
          </div>
        </div>

        <fieldset v-if="activeBillingRangeId"
          class="mb-3 px-3 w-full border border-gray-300 rounded p-4 bg-slate-50 relative">
          <legend class="px-3 font-semibold bg-white shadow">{{ $t('pricing_block.current_billing_range') }}</legend>
          <div class="group">
            <button
              class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-2 top-1 rounded-md text-slate-600 hover:text-blue-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
              @click="openPriceRate(true)">
              <Icon name="fa-solid:history" />
            </button>
            <MoleculesBillingRangeDetail :id="activeBillingRangeId" :isSubRegion="true" :isDetail="true" />
          </div>
        </fieldset>
        <div v-else>
          <span class="text-slate-500 mt-1 font-medium italic text-sm rounded-md px-2 py-1">
            {{ t('informative_block.info_no_active_price_rate') }}
          </span>
        </div>

        <div v-if="logChanges?.length" ref="logsDropdownWrapper" class="relative mb-3 z-20">
          <button type="button"
            class="inline-flex items-center gap-2 px-3 py-1 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-md hover:bg-slate-50 hover:border-slate-300 focus:outline-none"
            @click="toggleLogsDropdown">
            <Icon name="fa6-solid:arrows-rotate" class="text-xs" />
            {{ $t('common.changes') }} ({{ logChanges.length }})
            <Icon :name="showLogsDropdown ? 'fa6-solid:chevron-up' : 'fa6-solid:chevron-down'" class="text-[10px] text-slate-400" />
          </button>
          <div v-show="showLogsDropdown"
            class="absolute left-0 right-0 top-full mt-1 z-30 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto">
            <template v-for="entry in logChanges" :key="`${entry._type}-${entry.id}`">
              <article
                class="relative px-4 text-base bg-white group hover:bg-slate-50 ml-2 mt-0 pt-0 pb-2 border-l border-transparent hover:border-slate-400">
                <span class="absolute left-[-5px] top-0 text-[10px]">
                  <Icon name="fa6-solid:circle" class="text-slate-400" />
                </span>
                <footer class="flex justify-between items-center pt-1">
                  <p class="text-sm text-gray-700">{{ entry.user?.username || t('common.admin') }}</p>
                  <p class="inline-flex items-center justify-end text-sm text-gray-900 font-semibold">
                    <TimeRelative :datetime="entry.timestamp" />
                  </p>
                </footer>
                <p class="text-sm flex items-center gap-2 mt-1">
                  <span class="font-medium text-slate-600">{{ t('logs.' + entry.changed_field) }}</span>
                  <span class="text-slate-400">{{ entry.previous_value || t('common.no_value') }}</span>
                  <Icon name="fa6-solid:arrow-right" class="text-slate-400 text-xs" />
                  <span class="text-slate-900 font-medium">{{ entry.new_value || t('common.no_value') }}</span>
                </p>
              </article>
            </template>
          </div>
        </div>

        <div v-if="data.billing_range_active">

          <p class="px-3 font-semibold bg-white border-b border-slate-200">{{ $t('pricing_block.line_items')
          }}:
          </p>
          <LineItemTypeSimpleDetail :id="parseInt(data.billing_range_active.id)" :price_rate_id="parseInt(props.id)"
            :isSubRegion="isSubRegion" :in_detail="true" @show-detail="showDetail"
            :canChange="objectPermissions?.can_change && data.is_active" />
        </div>
        <div v-else-if="!data.billing_range_active && activeBillingRangeId">
          <p>{{ $t('common.no_records') }}</p>
        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->
    <div v-else>
      <p>{{ $t('common.no_permissions') }}</p>
    </div>

    <div v-if="showRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <LineItemTypeRegion v-if="showRegionDetailComponent === 'LineItemTypeRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <PriceIntervalRegion v-if="showRegionDetailComponent === 'PriceIntervalRegion'" :id="regionDetailId"
          :isSubRegion="true" />
      </div>

    </div>

  </div><!-- end region__content -->
</template>
