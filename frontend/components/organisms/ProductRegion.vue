<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import ProductDetail from '../molecules/ProductDetail.vue';
import PriceRateRegionDetail from './PriceRateRegionDetail.vue';
import ExploitationRegion from './ExploitationRegion.vue';
import CompanyRegion from './CompanyRegion.vue';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';
import TimeRelative from '../atoms/TimeRelative.vue';

const { t } = useI18n();
const route = useRoute()
const router = useRouter();
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
const { $PriceRateApiService, $ProductApiService, $LoggerApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('price_rates');
const SubRegion = ref(props.isSubRegionOpen);

const price_rates = ref([])
const logChanges = ref([])

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $ProductApiService.getPermissions();
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
    const result = await $ProductApiService.getDetail(props.id);
    data.value = result;

    getPriceRates();
    getLogs();

  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const getPriceRates = async () => {
  const response = await $PriceRateApiService.getAll('', [], 1, null, false, props.id);
  price_rates.value = []
  response.results.forEach(item => {
    price_rates.value.push(item)
  })
}

const getLogs = async () => {
  const response = await $LoggerApiService.getAll('product-change', props.id);
  logChanges.value = response.results;
}

const refresh = async (close = false) => {
  if (close) closeSubRegion();
  await getData();
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

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
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

const showDetail = async function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  await showSubRegion();
  if (route.query.price_rate_id) {
    router.replace({ query: { ...route.query, price_rate_id: undefined } });
  }
}

const deactivate = async () => {
  if (!confirm(t('confirmation_text_block.confirm_deactivate'))) return;
  try {
    let save_data = {
      id: data.value.id,
      is_active: false
    }
    let response = await $ProductApiService.save(save_data);
    if (response) {
      toast.success(t('common.deactivated'));
      emit('close-subregion');
    }
    //await getData();
  } catch (err) {
    console.error(err);
  }
}

const edit = function () {
  return router.push('/pricing/products/edit/' + props.id);
}

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value?.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return;
  }
  await getData();
  if (route.query.price_rate_id) {
    showDetail('PriceRateRegion', route.query.price_rate_id);
  }
});

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('product') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions.can_change" id="PriceRateRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('product')}`" @click="edit"></DropdownOption>
          <DropdownOption :name="`${t('common.deactivate')} ${t('product')}`" @click="deactivate"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <ProductDetail :data="data" :isSubRegion="isSubRegion" :isSubRegionOpen="isSubRegionOpen"
          @show-detail="showDetail" />
      </div><!-- end if data -->

      <AtomsTabs>
        <!-- pestanya de price_rates -->
        <li class="me-2">
          <a href="#tab_price_rates" @click.prevent="setActiveTab('price_rates')"
            :class="{ 'text-sky-600 border-sky-600': activeTab === 'price_rates', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'price_rates' }"
            aria-current="page">
            <Icon name="fa6-solid:file-contract" class="display-inline mr-2" />{{ $t("common.price_rates") }} ({{
              price_rates?.length || 0 }})
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
      <div id="cluster_tabpanels">

        <section v-show="activeTab === 'logs'" role="tabpanel" id="tab_logs" class="bg-white antialiased"
        :style="{ minHeight: 'calc(100vh - 400px)', maxHeight: 'calc(100vh - 400px)' }">
          <template v-for="entry in logChanges" :key="`${entry._type}-${entry.id}`">
            <article
              class="relative p-2 text-base bg-white group hover:bg-slate-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-slate-400">
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

        <!-- panell de orders -->
        <section v-show="activeTab === 'price_rates'" role="tabpanel" id="tab_price_rates"
          class="bg-white antialiased py-3">
          <div v-if="price_rates.length != 0" class="my-1 rounded-md border border-gray-300 divide-y bg-white" :style="{
            overflowY: 'auto',
            maxWidth: '100%',
            maxHeight: 'calc(100vh - 300px)'
          }">
            <table class="min-w-full text-sm text-slate-800 border-b border-gray-300 divide-y">
              <thead class="sticky top-0">
                <tr class="bg-white border-b text-left">
                  <th class="p-2">{{ t('common.name') }}</th>
                  <th class="p-2">{{ t('common.identification') }}</th>
                  <th class="p-2">{{ t('common.range') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pr in price_rates.sort((a, b) => a.name.localeCompare(b.name))" :key="pr.id" class="border-b"
                  :class="{
                    'bg-yellow-50': pr.id === regionDetailId,
                    'bg-slate-50 text-slate-500': !pr.is_active
                  }">
                  <td class="p-2">
                    <span v-if="isSubRegion" class="text-slate-600 truncate">{{ pr.name }} {{ pr.is_active ? '' : '(' +
                      t('common.deactivated') + ')' }}</span>
                    <div v-else class="flex items-center gap-x-2">
                      <button class="text-sky-600 underline cursor-pointer hover:text-sky-400 truncate"
                        @click="showDetail('PriceRateRegion', pr.id)">
                        {{ pr.name }} {{ pr.is_active ? '' : '(' + t('common.deactivated') + ')' }}
                      </button>
                      <AtomsRedirectButton :id="pr.id" :path="'/pricing/price-rates/'" />

                    </div>
                  </td>
                  <td class="p-2 text-slate-600">{{ pr.token }}</td>
                  <td class="p-2 text-slate-600">
                    <span v-if="pr.billing_range_active">{{ pr.billing_range_active.name }} &nbsp;<em>({{
                      formatDate(pr.billing_range_active.start) }})</em></span>
                    <span v-else>-</span>
                  </td>
                </tr>
              </tbody>
            </table>


          </div>

          <div v-else class="footering text-slate-500 p-2">
            {{ t('common.no_records') }}
          </div>
        </section>
      </div>

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
        <PriceRateRegionDetail v-if="showRegionDetailComponent === 'PriceRateRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" @close="refresh(true)" />
        <ExploitationRegion v-if="showRegionDetailComponent === 'ExploitationRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <CompanyRegion v-if="showRegionDetailComponent === 'CompanyRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <ProductRegion v-if="showRegionDetailComponent === 'ProductRegion'" :id="parseInt(regionDetailId)"
          :isSubRegion="true" />
        <!-- /end Subregions aqui -->
      </div>
    </div>
  </div><!-- end region__content -->
</template>
