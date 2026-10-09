<script setup>
// components/organisms/ClusterDetail.vue
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import ChangeStatus from '~/components/molecules/ChangeStatus.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

// Importar el component SupplyPointRegion per a la subregion
import FieldDetail from '~/components/atoms/FieldDetail.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion']);
const router = useRouter();
const { $BillingBatchApiService, $ConfiglistApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('contracts');
const SubRegion = ref(props.isSubRegionOpen);

// const readingBatchStatuses = ref([]);
// const readingBatchStatus = ref(null);

const editingChangeStatus = ref(false);

const getData = async () => {
  pending.value = true;
  try {
    const result = await $BillingBatchApiService.getDetail(props.id);
    data.value = result;

    // await fetchConfigData('billing/reading-batch-status', readingBatchStatuses);

    if (data.value && data.value.status) {
      // readingBatchStatus.value = data.value.status;
    }
    else {
      // const defaultStatus = readingBatchStatuses.value.find(s => s.is_default == true);
      // if (defaultStatus) {
      //   readingBatchStatus.value = defaultStatus;
      // }
    }
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll(entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
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

const changeStatus = async () => {
  if (confirm(t('confirmation_text_block.confirm_cancel'))) {

    try {
      const token = await $ConfigProjectApiService.get('batch_status_cancel_token');
      console.log(token)
  
      const data = {
        id: props.id,
        status_token: token
      }
      const res = await $BillingBatchApiService.update(data);
      getData();
    }
    catch (error) {
      console.log(error)
    }
  }
  
}

const handleStatusChanged = () => {
  editingChangeStatus.value = false;
  SubRegion.value = false;
  emit('show-subregion', false)
  getData()
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

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const edit = () => {
  return navigateTo('/billing/billing-batches/edit/' + props.id)
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

</script>

<template>
  <div class="region__content">
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
        <H1Region class="mb-3">{{ $t('common.billing_batch_detail') }}</H1Region>
        <OptionsDropdown id="BillingBatchRegionOptions">
          <DropdownOption :name="`${$t('common.modify')} ${$t('common.billing_batch_detail')}`" @click="edit"></DropdownOption>
          <!-- <DropdownOption name="Cancelar lot" @click="changeStatus"></DropdownOption> -->
        </OptionsDropdown>
      </div>
      <!-- <StatusesNav v-if="readingBatchStatuses" :active="readingBatchStatus" :statuses="readingBatchStatuses"/> -->

      <div class="mt-4" v-if="data" id="item_data" :data-rel=id>
        <div class="flex flex-col mb-4">
          <div class="grid grid-cols-2 gap-3">
            <FieldDetail :label='$t("common.identification")' :value=data.token></FieldDetail>
            <FieldDetail :label='$t("common.name")' :value=data.name></FieldDetail>
            <FieldDetail :label='$t("common.date")' :value=formatDate(data.created_at)></FieldDetail>
          </div>
        </div>
        <div class="divide-y divide-slate-300">
          <div class="grid grid-cols-[1fr,2fr,1fr,1fr,1fr] gap-3 pt-2">
            <span>{{ t('common.creation_date') }}</span>
            <span>{{ t('contract') }}</span>
            <span>{{ t('reading') }}</span>
            <span>{{ t('billing_block.consumption') }}</span>
            <span>{{ t('common.origin') }}</span>
          </div>
          <div v-for="item in data.readings" :key="item.id" class="grid grid-cols-[1fr,2fr,1fr,1fr,1fr] gap-3 pt-2">
            <span>{{ item.reading_date }}</span>
            <span>{{ item.supply_point }}</span>
            <span>{{ item.reading_value }}</span>
            <span>{{ item.calculated_value }}</span>
            <span>{{ item.origin }}</span>
          </div>
        </div>
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
        <!-- <ChangeStatus v-if="editingChangeStatus" entity="reading-batch" parent_entity="reading_batch"
        :id="props.id" :status="readingBatchStatus?.id" module="billing" @changed="handleStatusChanged" /> -->
      </div>
    </div>
  </div><!-- end region__content -->
</template>
