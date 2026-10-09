<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import LineItemTypeDetail from '../molecules/LineItemTypeDetail.vue';
import PriceIntervalRegion from './PriceIntervalRegion.vue';
import AdjustmentRegion from './AdjustmentRegion.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close']);
const { $LineItemTypeApiService, $PriceRateApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('');
const SubRegion = ref(props.isSubRegionOpen);


const getData = async () => {
  pending.value = true;

  try {
    const result = await $LineItemTypeApiService.getDetail(props.id);
    data.value = result;
    console.log("data.value");
    console.log(data.value);
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
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

</script>

<template>
  <div v-if="objectPermissions?.can_view" class="region__content">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('pricing_block.line_item_type') }}</H1Region>
      </div>

      <div v-if="data" id="item_data" :data-rel=id class="my-3">

        <LineItemTypeDetail :id="id" :data="data" :isSubRegion="isSubRegion" :isSubRegionOpen="isSubRegionOpen"
          @show-detail="showDetail" :canChange="objectPermissions?.can_change" />

      </div><!-- end if data -->

      

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
        <!-- Subregions aqui -->
        <PriceIntervalRegion v-if="showRegionDetailComponent === 'PriceIntervalRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <AdjustmentRegion v-if="showRegionDetailComponent === 'AdjustmentRegion'" :id="regionDetailId"
          :isSubRegion="true" />
        <!-- /end Subregions aqui -->
      </div>
    </div>
  </div><!-- end region__content -->
</template>
