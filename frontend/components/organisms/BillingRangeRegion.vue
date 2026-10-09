<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
// Importar el component SupplyPointRegion per a la subregion
import BillingRangeDetail from '../molecules/BillingRangeDetail.vue';
import PriceRateRegion from './PriceRateRegion.vue';
import PublicationRegion from './PublicationRegion.vue';
import LineItemTypeRegion from './LineItemTypeRegion.vue';
import EditLineItemType from './EditLineItemType.vue';
import LineItemTypeEdit from './LineItemTypeEdit.vue';


const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  id: Number, // ID de l'element
  inPriceRate: {
    type: Boolean,
    default: null
  },
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close']);
const { $BillingRangeApiService, $LineItemTypeApiService, $PriceRateApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('line_item_types');
const SubRegion = ref(props.isSubRegionOpen);
const showRegion = ref(false);

const getData = async () => {
  pending.value = true;
  
  try {
    const result = await $BillingRangeApiService.getDetail(props.id);
    data.value = result;

  } catch (err) {
    console.error(err);
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
  objectPermissions.value = await checkPermission($PriceRateApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  getData();
});

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  if (showRegionDetailComponent.value != 'AddLineItemType') {
    SubRegion.value = true;
  } else {
    showRegion.value = true;
  }
  emit('show-subregion', SubRegion.value);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component.component;
  regionDetailId.value = component.id;
  showSubRegion();
}

const handleNewLineItemType = async (new_lit) => {

  new_lit.price_rate = props.id

  await $LineItemTypeApiService.save(new_lit)

  closeSubRegion()
  getData()
}

const edit = function () {
  const priceRateId = data.value?.price_rate?.id || data.value?.price_rate || null;
  return navigateTo({
    path: '/pricing/billing-ranges/edit/' + props.id,
    query: priceRateId ? { price_rate_id: priceRateId } : {}
  });
}


const setActiveTab = (tab) => {
  activeTab.value = tab;
}

</script>

<template>
  <div v-if="objectPermissions?.can_view" class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('pricing_block.billing_ranges') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="PriceRateRegionOptions">
          <DropdownOption :name="`${$t('common.modify')} ${$t('pricing_block.billing_range_detail')}`" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <BillingRangeDetail :id="props.id" :data="data" :isSubRegion="isSubRegion?true:null" :isSubRegionOpen="isSubRegionOpen"
          @show-detail="showDetail" />

        <AtomsTabs>

          <li class="me-2">
            <a href="#tab_line_item_types" @click.prevent="setActiveTab('line_item_types')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'line_item_types', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'line_item_types' }"
              class="inline-flex items-center justify-center p-4 border-b-2 rounded-t-lg group" aria-current="page">
              <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" /> {{ $t("pricing_block.line_items") }}
            </a>
          </li>


        </AtomsTabs>
        <div id="order_tabpanels">
          <section v-show="activeTab === 'line_item_types'" role="tabpanel" id="tab_line_item_types"
            class="bg-white antialiased">
            <EditLineItemType :id="props.id" :pr_id="data.price_rate" :inPriceRate="inPriceRate" @show-subregion="showDetail" :isSubRegion="isSubRegion" :canChange="objectPermissions?.can_change" />
          </section>
        </div>

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
    class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white ml-5 fixed top-0 right-0 w-[48vw] z-50"
    :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- Subregions aqui -->
        <PriceRateRegion v-if="showRegionDetailComponent === 'PriceRateRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <PublicationRegion v-if="showRegionDetailComponent === 'PublicationRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <LineItemTypeRegion v-if="showRegionDetailComponent === 'LineItemTypeRegion'" :id="regionDetailId"
          :isSubRegion="true" />

        <!-- /end Subregions aqui -->
      </div>
    </div>



  </div><!-- end region__content -->
</template>
