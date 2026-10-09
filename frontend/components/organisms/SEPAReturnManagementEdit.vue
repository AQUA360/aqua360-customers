<script setup>
import { ref, onMounted } from 'vue';
import { add, format } from 'date-fns';
import PaymentRegion from './PaymentRegion.vue';
import ContractRegion from './ContractRegion.vue';
import SEPAReturnSetup from './SEPAReturnSetup.vue';
import AddInvoices from '../molecules/AddInvoices.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n()
const router = useRouter()
const toast = useToast();
const objectPermissions = ref(null);
const emit = defineEmits(['refresh']);
const { $PaymentApiService } = useNuxtApp();

const loading = ref(true);

const selectedReturnPayments = ref([])
const selectedClaimPayments = ref([])
const paymentsToReturn = ref([])

const showRegion = ref(false);
const showDetailRegion = ref(null);
const showDetailId = ref(null);
const isSubRegionOpen = ref(false);

const ogMsId = ref(null);
const fileToReturn = ref(null);

const saveResponse = ref(false);
const returnedData = ref(null);
const isSaving = ref(false);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!showRegion.value) {
    showDetailRegion.value = null;
    showDetailId.value = null;
    isSubRegionOpen.value = false;
  }
}

const clickFinalize = async () => {
  try {
    let text = t("confirmation_text_block.confirm_finish")
    if (selectedReturnPayments.value.length > 0) {
      text += "\n\n" + t("informative_block.info_return_invoice_mng") + selectedReturnPayments.value.length
    }
    if (selectedClaimPayments.value.length > 0) {
      text += "\n\n" + t("informative_block.info_claim_payments_mng") + selectedClaimPayments.value.length
    }
    if (selectedReturnPayments.value.length == 0 && selectedClaimPayments.value.length == 0) {
      text += "\n\n" + t("informative_block.info_return_payments_no_action")
    }
    if (confirm(text)) {
      await save();
      //router.push('/billing/invoice');
    }
  }
  catch (error) {
    console.error(error);
  }
}

const updateFile = (file) => {
  fileToReturn.value = file;
}

const showDetail = async (region, id) => {
  await toggleRegion(false);
  showDetailRegion.value = region;
  showDetailId.value = id;
  toggleRegion(true);
}

const handleSubRegionOpen = (value) => {
  isSubRegionOpen.value = value;
}

onMounted(async () => {
  objectPermissions.value = await checkPermission($PaymentApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  loading.value = false;
});

const handleChanged = (allPayments, returnPayments, claimPayments, ogMsgId) => {
  selectedReturnPayments.value = returnPayments;
  selectedClaimPayments.value = claimPayments;
  paymentsToReturn.value = allPayments;
  ogMsId.value = ogMsgId;
}

const save = async () => {
  try{
    isSaving.value = true;
    let data = {
      file: fileToReturn.value,
      return_payments: selectedReturnPayments.value,
      claim_payments: selectedClaimPayments.value,
      payments_to_return: paymentsToReturn.value,
      og_msg_id: ogMsId.value,
      // Data de retorn del fitxer: la primera rjt_dt informada, no només la del primer pagament
      return_date: paymentsToReturn.value.find(payment => payment.rjt_dt)?.rjt_dt ?? null
    }
    const response = await $PaymentApiService.manageRejectionPayments(data);
    /* if (response){
      router.push('/billing/sepa');
    } */

    if (response){
      saveResponse.value = !saveResponse.value;
      returnedData.value = response.rejections;
    }
  } catch (error) {
    console.error(error);
  } finally {
    isSaving.value = false;
  }
} 
</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base">


    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">

      <div class="mb-6">
        <SEPAReturnSetup @show-detail="showDetail" @changed="handleChanged" 
        @update-file="updateFile" :save_response="saveResponse" :returned_data="returnedData" />
      </div>

      <hr v-if="selectedReturnPayments.length > 0 || selectedClaimPayments.length > 0 || paymentsToReturn.length > 0" />
      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4" v-if="selectedReturnPayments.length > 0 || selectedClaimPayments.length > 0 || paymentsToReturn.length > 0">
        <div class="flex gap-3">
          <button @click="clickFinalize" :disabled="isSaving"
            class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold flex items-center">
            <Icon name="fa6-solid:circle-check" />&nbsp; {{ $t('common.save') }}
          </button>
        </div>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació de ContractRequestEdit -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[50%]': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PaymentRegion v-if="showDetailRegion == 'PaymentRegion'" :id="showDetailId" 
        @show-subregion="handleSubRegionOpen" />
        <ContractRegion v-if="showDetailRegion == 'ContractRegion'" :id="showDetailId" @show-subregion="handleSubRegionOpen" />
        <AddInvoices v-if="showDetailRegion == 'AddInvoices'" :info="true" :payment_bank_final="showDetailId"
        :selected_items="[]" />
      </div>
    </div>
  </div>
</template>