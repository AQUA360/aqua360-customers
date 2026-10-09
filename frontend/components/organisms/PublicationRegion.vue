<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';

// Importar el component SupplyPointRegion per a la subregion
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import BillingRangeDetail from '../molecules/BillingRangeDetail.vue';
import PriceRateRegion from './PriceRateRegion.vue';
import PublicationDetail from '../molecules/PublicationDetail.vue';


const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed']);
const router = useRouter();
const { $PublicationApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('');
const SubRegion = ref(props.isSubRegionOpen);
const observationNumber = ref(0)


const updateObservationCount = (num) => {
  observationNumber.value = num;
  console.log(observationNumber.value)
}

const getData = async () => {
  pending.value = true;

  try {
    const result = await $PublicationApiService.getDetail(props.id);
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

getData();

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component.component;
  regionDetailId.value = component.id;
  showSubRegion();
}


const setActiveTab = (tab) => {
  activeTab.value = tab;
}

</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('pricing_block.publication_detail') }}</H1Region>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>

        <PublicationDetail :id="props.id" :data="data" :isSubRegion="isSubRegion" :isSubRegionOpen="isSubRegionOpen"
          @show-detail="showDetail" />

      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- Subregions aqui -->

        <!-- /end Subregions aqui -->
      </div>
    </div>
  </div><!-- end region__content -->
</template>
