<script setup>
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import StatusesNav from '~/components/atoms/StatusesNav.vue';
import DeliquencyRequestSetup from './DeliquencyRequestSetup.vue';
import DeliquencyRequestSummary from './DeliquencyRequestSummary.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const route = useRoute()
const router = useRouter()
const toast = useToast();
const { $InvoiceApiService, $PaymentApiService } = useNuxtApp();

const objectPermissions = ref(null);

const props = defineProps({
  request: Object,
});

const emit = defineEmits(['refresh']);

const request = ref(null);

const steps = ref(['1', '2']);
const currentStep = ref(0);
const maxStep = ref(0);

const loading = ref(false);

const showRegion = ref(false);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}

const affectedContracts = ref([])
const affectedInvoicesIds = ref([])
const endowmentDate = ref(null)


const setContracts = (data) => {
  affectedContracts.value = data.contracts
  if (data.invoices) affectedInvoicesIds.value = data.invoices
  if (data.endowment_date) endowmentDate.value = data.endowment_date
}

const finalStep = async () => {
  try {
    //if (!confirm(t("Estàs segur que vols finalitzar aquesta sol·licitud? Aquesta passarà a provisional"))) return
    let confirmation_text = t("confirmation_text_block.confirm_finalize_request") + "\n" + t("warning_block.warning_irreversible")
    if (!confirm(confirmation_text)) return
    
    let save_date = {
      contracts: affectedContracts.value.map(el => el.id),
      invoices: affectedInvoicesIds.value,
      saving:true,
    }
    let response = await $PaymentApiService.manageDeliquency(save_date)
    if (response){
      await nextTick()
      await navigateTo('/billing/wallet-managements/')
    }
    //navigateTo('/billing/deliquency-requests/')
  }
  catch (error) {
    console.error(error);
  }
}


const nextStep = async () => {
  if (currentStep.value < steps.value.length - 1) {
    currentStep.value++;
    if (currentStep.value > maxStep.value) {
      maxStep.value = currentStep.value;
    }
    setUrlStep();
  }
};


const setUrlStep = () => {
  router.replace({
    query: {
      ...route.query, // Keep existing query parameters
      step: currentStep.value + 1
    }
  });
}


onMounted(async () => {
  objectPermissions.value = await checkPermission($InvoiceApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  if (route.query.step) {
    currentStep.value = parseInt(route.query.step) - 1;
    maxStep.value = currentStep.value;
  }
  setUrlStep();
  if (props.request) {
    request.value = props.request;
  }
});

watch(() => props.request, (newVal) => {
  if (newVal.person || newVal.address) {
  }
});

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base">
    <div class="border-gray-300 mb-2">
      <div class="flex space-x-4 justify-between">
        <div class="buttons flex gap-4 ml-4">
          <button v-for="(step, index) in steps" :disabled="index > maxStep"
            class="px-4 py-2 rounded-full focus:outline-none" :class="{
              'bg-blue-500 text-white': currentStep === index,
              'bg-gray-200 text-gray-600 cursor-not-allowed': index > maxStep,
              'bg-blue-100 text-blue-500': maxStep >= index
            }" @click="currentStep = index; setUrlStep()"> Pas {{ step
            }}
          </button>
        </div>
      </div>
    </div>

    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded-b p-4 bg-white">

      <div v-if="currentStep === 0" class="tab-content mb-6">
        <DeliquencyRequestSetup @changed="setContracts" />
      </div>

      <div v-if="currentStep === 1" class="tab-content mb-6">
        <DeliquencyRequestSummary :contracts="affectedContracts" @changed="setContracts" />
      </div>

      <hr />

      <!-- Botons de navegació -->
      <div class="flex flex-row-reverse mt-4">
        <button v-if="currentStep !== steps.length - 1" @click="nextStep"
          :disabled="currentStep === 0 && (endowmentDate == null || affectedContracts.length == 0)"
          class="px-4 py-2 bg-green-500 text-white rounded enabled:hover:bg-green-600 disabled:opacity-70">
          {{ $t('common.next') }} &nbsp;&rarr;
        </button>
        <button v-else
          :disabled="affectedContracts.length == 0 && endowmentDate == null && affectedInvoicesIds.length == 0"
          @click="finalStep"
          class="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50 enabled:hover:bg-green-600 font-bold flex items-center">
          <Icon name="fa6-solid:circle-check" />&nbsp; {{ $t('common.finish') }}
        </button>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació de Persona/Adreça -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">

      </div>
    </div>
  </div>
</template>