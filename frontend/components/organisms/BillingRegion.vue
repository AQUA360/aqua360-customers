<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import BillingDetail from '../molecules/BillingDetail.vue';
import ReadingBatchRegion from '../organisms/ReadingBatchRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { usePermissions } from '~/middleware/permission';

const { permissions, loading } = usePermissions();

const { t } = useI18n();
const toast = useToast();

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
const { $BillingApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const statusProcessedToken = ref(null);
const status_pending_token = ref(null);

const activeTab = ref('billings');
const SubRegion = ref(props.isSubRegionOpen);
const objectPermissions = ref(null);

const clickPdf = async () => {
  $BillingApiService.getBatchPdf(props.id).then(response => response.arrayBuffer())
    .then(buffer => {
      const blob = new Blob([buffer], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `billing_${new Date().toLocaleString('default', { month: '2-digit', year: '2-digit' }).replace(/\//g, '_')}.pdf`;
      a.click();
    })
}

const getPermissions = async () => {
  error.value = null;
  try {
    const data = await $BillingApiService.getPermissions();
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
    statusProcessedToken.value = await $ConfigProjectApiService.get('billing_batch_processed')
    const result = await $BillingApiService.getDetail(props.id);
    data.value = result;
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
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

onMounted(async () => {
  await getPermissions();
  if (objectPermissions.value?.can_view) {
    getData();
  } else {
    toast.error(t('common.no_permissions'));
    emit('close-subregion');
    return navigateTo('/');
  }
});

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

const openSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  emit('show-subregion', false);
}

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = (component, id) => {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  openSubRegion();
}

const editBilling = function (id) {
  navigateTo('/billing/billing/edit/' + props.id);
}

const clickCommunicationProcess = function () {
  return navigateTo('/communication/process-communications/add?billing_id=' + props.id);
}

const cancelBilling = async () => {
  if (!confirm(t("confirmation_text_block.confirm_cancel"))) return
  try {
    await $BillingApiService.cancel(props.id);
    toast.success(t("common.saved_successfully") || "Saved successfully");
    await getData(false);
    emit('changed');
  } catch (err) {
    console.error(err);
    toast.error(t("common.error") || "Error");
  }
}

</script>

<template>
  <div class="region__content h-full">
    <div v-if="pending || loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="objectPermissions?.can_view" class="pr-2 relative pb-24 transition-all duration-500 ease"
      :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">
          {{ $t('billing') }}
        </H1Region>
        <OptionsDropdown v-slot:default v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="`${$t('common.check')} ${$t('billing')}`" @click="editBilling"></DropdownOption>
          <hr class="my-2" />
          <DropdownOption :disabled="!data.status?.token == statusProcessedToken" :name="`${t('common.download')} ${t('common.doc')}`"
            @click="clickPdf"></DropdownOption>
          <DropdownOption :disabled="!data.status?.token == statusProcessedToken" :name="t('customer_service_block.new_comms_process')"
            @click="clickCommunicationProcess"></DropdownOption>
          <DropdownOption v-if="data.status?.token !== '-1'" :name="`${t('common.cancel')} ${t('billing').toLowerCase()}`"
            @click="cancelBilling"></DropdownOption>
          <!-- <DropdownOption v-if="data.status?.token == status_pending_token" name="Confirmar Factura" @click="confirmInvoice"></DropdownOption> -->
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <BillingDetail :id="id" :data="data" :isSubRegion="isSubRegion" :isRegion="true" @show-detail="showDetail" />
        <div v-if="objectPermissions?.can_change" class="flex flex-row-reverse mt-4">
          <button class="button-default" @click="editBilling">
            {{ t('common.check') }} {{ t('billing') }}
          </button>
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
        <ReadingBatchRegion v-if="showRegionDetailComponent === 'ReadingBatchRegion'" :id="regionDetailId" />
      </div>
    </div>
  </div><!-- end region__content -->
</template>
