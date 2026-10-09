<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import PriceRateDetail from '~/components/molecules/PriceRateDetail.vue';
import ExploitationRegion from '~/components/organisms/ExploitationRegion.vue';
import EditBillingRanges from './EditBillingRanges.vue';
import AddBillingRange from '../molecules/AddBillingRange.vue';
import BillingRangeRegion from './BillingRangeRegion.vue';
import PublicationRegion from './PublicationRegion.vue';
import ProductRegion from './ProductRegion.vue';
import AdjustmentsTable from '../molecules/AdjustmentsTable.vue';
// Importar el component SupplyPointRegion per a la subregion
import TimeRelative from '../atoms/TimeRelative.vue';
import AdjustmentRegion from './AdjustmentRegion.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';


const { t } = useI18n();
const toast = useToast();
const { permissions, loading } = usePermissions();
const objectPermissions = ref(null);

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);
const router = useRouter();
const { $PriceRateApiService, $BillingRangeApiService, $LoggerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('billing_range');
const SubRegion = ref(props.isSubRegionOpen);

const logChanges = ref([])

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $PriceRateApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    error.value = err;
  }
}

const getLogs = async () => {
  const response = await $LoggerApiService.getAll('price-rate-change', props.id);
  logChanges.value = response.results;
}


const getData = async () => {
  if (!objectPermissions.value?.can_view) {
    emit('close-subregion');
    return
  }
  pending.value = true;
  try {
    const result = await $PriceRateApiService.getDetail(props.id);
    data.value = result;
    console.log("get data ", data.value);
  } catch (err) {
    console.error(err);
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
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  }
  await getData();
  await getLogs();
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

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component.component;
  regionDetailId.value = component.id;
  showSubRegion();

}

const newBillingRange = async (new_br) => {
  new_br.price_rate = props.id
  new_br.publication = new_br.publication.id
  await $BillingRangeApiService.save(new_br)
  closeSubRegion()
  getData()
}

const edit = function () {
  return navigateTo('/pricing/price-rates/edit/' + props.id);
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
      <p>{{ t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('price_rate') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions.can_change" id="PriceRateRegionOptions">
          <DropdownOption :name="t('common.modify') + ' ' + t('price_rate')" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <PriceRateDetail :data="data" :isSubRegion="isSubRegion" :isSubRegionOpen="isSubRegionOpen"
          @show-detail="showDetail" :disabled="true" />

        <AtomsTabs>
          <!-- pestanya de orders -->

          <li class="me-2">
            <a href="#tab_billing_range" @click.prevent="setActiveTab('billing_range')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'billing_range', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'billing_range' }"
              class="inline-flex items-center justify-center p-4 border-b-2 rounded-t-lg group" aria-current="page">
              <Icon name="fa6-solid:calendar-days" class="display-inline mr-2" /> {{ $t("pricing_block.ranges") }}
            </a>
          </li>

          <li class="me-2">
            <a href="#tab_adjustments" @click.prevent="setActiveTab('adjustments')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'adjustments', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'adjustments' }"
              class="inline-flex items-center justify-center p-4 border-b-2 rounded-t-lg group" aria-current="page">
              <Icon name="fa6-solid:wrench" class="display-inline mr-2" /> {{ $t("pricing_block.adjustments") }}
            </a>
          </li>

          <li class="me-2">
            <a href="#tab_logs" @click.prevent="setActiveTab('logs')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'logs', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'logs' }"
              aria-current="page">
              <Icon name="fa6-solid:arrows-rotate" class="display-inline mr-2" />
              {{ $t("common.changes") }} ({{ logChanges?.length || 0 }})
            </a>
          </li>

        </AtomsTabs>
        <div id="order_tabpanels">
          <!-- panells -->

          <section v-show="activeTab === 'logs'" role="tabpanel" id="tab_logs" class="bg-white antialiased overflow-y-auto"
          :style="{ minHeight: 'calc(100vh - 450px)', maxHeight: 'calc(100vh - 450px)' }">
            <template v-for="entry in logChanges" :key="`${entry._type}-${entry.id}`">
              <article
                class="relative px-2 text-base bg-white group hover:bg-slate-50 px-4 mt-0 pt-0 pb-2 border-l hover:border-slate-400">
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
          </section>


          <section v-show="activeTab === 'billing_range'" role="tabpanel" id="tab_billing_range"
            class="bg-white antialiased">
            <EditBillingRanges :id="props.id"
              :activeBillingRange="data.billing_range_active ? data.billing_range_active.id : null"
              @get-interval="getLastInterval" @show-subregion="showDetail" :isSubRegion="isSubRegion"
              :canChange="objectPermissions?.can_change" />
          </section>


          <section v-show="activeTab === 'adjustments'" role="tabpanel" id="tab_adjustments"
            class="bg-white antialiased">
            <AdjustmentsTable :pr_id="props.id" @show-detail="showDetail" :isSubRegion="isSubRegion" />
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
        <ExploitationRegion v-if="showRegionDetailComponent === 'ExploitationRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <BillingRangeRegion v-if="showRegionDetailComponent === 'BillingRangeRegion'" :inPriceRate="true"
          :id="parseInt(regionDetailId)" :isSubRegion="true" />
        <AddBillingRange v-if="showRegionDetailComponent === 'AddBillingRange'" :br_id="null" :pr_id="props.id"
          :li_id="data.billing_range_active ? data.billing_range_active.id : null" :isSubRegion="true"
          @new-br="newBillingRange" />
        <PublicationRegion v-if="showRegionDetailComponent === 'PublicationRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" @new-br="newBillingRange" />
        <ProductRegion v-if="showRegionDetailComponent === 'ProductRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" @new-br="newBillingRange" />
        <AdjustmentRegion v-if="showRegionDetailComponent === 'AdjustmentRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" @new-br="newBillingRange" />

      </div>
    </div>
  </div><!-- end region__content -->
</template>
