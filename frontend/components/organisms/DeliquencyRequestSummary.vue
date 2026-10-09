<script setup>
import { ca } from 'date-fns/locale';
import { useI18n } from 'vue-i18n';
import TableHeader from '../atoms/TableHeader.vue';
import ContractRegion from './ContractRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import AffectedClaimContracts from '../molecules/AffectedClaimContracts.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const { $PaymentApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);

const props = defineProps({
  contracts: Object,
});

const affectedContracts = ref([]);
const affectedInvoices = ref([]);
const sharedContractsInvoices = ref([]);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const showRegionDetail = ref(null);

const dialogOpen = ref(false);
const dialogPosition = ref({ x: 0, y: 0 });
const selectedItem = ref(null); // Store the entire selected item

const emit = defineEmits(['changed']);

const getData = async () => {
  pending.value = true;
  try {
    let request_data = {
      contracts: affectedContracts.value.map((c) => c.id),
      fetching: true,
    };
    let response = await $PaymentApiService.manageDeliquency(request_data);
    affectedInvoices.value = response.invoices.sort((a, b) => a.contract_token - b.contract_token);
    let invoicesIds = affectedInvoices.value.map((i) => i.id);
    let data = {
      contracts: affectedContracts.value,
      invoices: invoicesIds,
    };

    getSharedContractsInvoices(response)

    emit('changed', data)
  } catch (err) {
    console.error(err);
  } finally {
    pending.value = false;
  }
};

const getSharedContractsInvoices = (response) => {
  sharedContractsInvoices.value = response.contracts.map((contract) => {
    const relatedInvoices = response.invoices
      .filter((invoice) => invoice.contract === contract.id)
      .map((invoice) => ({
        id: invoice.id,
        token: invoice.token,
        serie_final: invoice.serie_final,
        left_to_pay: invoice.left_to_pay,
        title_final: invoice.title_final,
        total_final: invoice.total_final,
        currently_paid: invoice.currently_paid,
      }));

    return relatedInvoices.length > 0 ? { ...contract, invoices: relatedInvoices } : null;
  }).filter((item) => item !== null);
}

const removeContract = async (item) => {
  /* if (!selectedItem.value) return;
  console.log('Removing contract for item:', selectedItem.value.id);
  closeDialog(); */
  //if (!confirm(t("Estàs segur que vols treure aquest contracte de la gestió?"))) return
  //affectedContracts.value = affectedContracts.value.filter(x => String(x.id) !== String(item));
  for (let contract of item) {
    affectedContracts.value = affectedContracts.value.filter(x => String(x.id) !== String(contract.contract_id));
  }
  getData();
};

const openRegion = (entity, detail) => {
  showRegionDetailComponent.value = entity;
  showRegionDetail.value = detail;
  toggleRegion(true);
}

const toggleDialog = (event, item) => {
  event.stopPropagation();

  dialogOpen.value = !dialogOpen.value;
  selectedItem.value = item;

  if (dialogOpen.value) {
    const buttonRect = event.target.getBoundingClientRect();
    dialogPosition.value = {
      x: buttonRect.left - 250,
      y: buttonRect.top,
    };
  }
};

const closeDialog = () => {
  dialogOpen.value = false;
  selectedItem.value = null;
};


const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (!force) {
    showRegionDetailComponent.value = null
    showRegionDetail.value = null
    isSubRegionOpen.value = false;
  }
}

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

onMounted(() => {
  affectedContracts.value = props.contracts;
  getData();

  document.addEventListener('click', () => {
    closeDialog();
  });
});

onBeforeUnmount(() => {
  document.removeEventListener('click', () => {
    closeDialog();
  });
});

watch(() => props.contracts, (newVal) => {
  affectedContracts.value = newVal;
});

</script>

<template>
  <div id="wrapper" class="p-6 text-gray-800">
    <h2 class="text-xl font-semibold mb-4">
      {{ $t('contract_block.affected_contracts') }}
    </h2>

    <div v-if="!pending" class="mt-2">
      <AffectedClaimContracts :data="sharedContractsInvoices" @show-detail="openRegion" 
      @remove="removeContract" />
    </div>
    <div v-else>
      <AppLoading :text="$t('common.loading')" />
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[60%]': !isSubRegionOpen,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ContractRegion v-if="showRegionDetailComponent == 'ContractRegion'" :id="showRegionDetail" 
        @show-subregion="handleSubRegionEvent"/>
        <InvoiceRegion v-if="showRegionDetailComponent == 'InvoiceRegion'" :id="showRegionDetail" 
        @show-subregion="handleSubRegionEvent" />
      </div>
    </div>
    <!-- <teleport to="body">
      <div v-if="dialogOpen" class="dialog-dropdown" 
      :style="{
        left: dialogPosition.x + 'px',
        top: dialogPosition.y + 'px',
      }">
        <p>{{ t('Selecciona què vols eliminar per aquesta sol·licitud') }}</p>
        <button class="button-primary" @click="removeContract">{{ t('Contracte') }}</button>
        <button class="button-primary" @click="removeInvoice">{{ t('Factura') }}</button>
        <button class="button-default" @click="closeDialog">{{ t('Cancel·lar') }}</button>
      </div>
    </teleport> -->
  </div>
</template>

<style scoped>
.dialog-dropdown {
  position: absolute;
  background-color: white;
  padding: 10px;
  border-radius: 5px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  z-index: 100;
  width: 250px;
}

</style>
