<script setup>
import { ref, watch, computed } from 'vue';
import H1Region from '~/components/atoms/H1Region.vue';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';

const props = defineProps({
  id: Number, // ID de la gestió d'impagats
  contractId: Number, // Opcional: contracte des del qual s'obre (mostra les seves factures a la gestió)
  isSubRegion: {
    type: Boolean,
    default: false
  },
});

const { $ClaimRequestApiService, $ConfigProjectApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const contractData = ref(null);
const paymentStatusPaidToken = ref(null);

// Identificador de la càrrega vigent: si es canvia de gestió mentre una càrrega
// encara és en curs, la resposta antiga es descarta i no substitueix la nova.
let currentLoadId = 0;

const getData = async () => {
  const loadId = ++currentLoadId;
  pending.value = true;
  error.value = null;

  try {
    const [detail, contracts, paidToken] = await Promise.all([
      $ClaimRequestApiService.getDetail(props.id),
      props.contractId ? $ClaimRequestApiService.getContracts(props.id, null, null, props.contractId) : null,
      props.contractId ? $ConfigProjectApiService.get('payment_status_paid_token') : null,
    ]);
    if (loadId !== currentLoadId) return;
    data.value = detail;
    contractData.value = contracts?.results?.[0] || null;
    paymentStatusPaidToken.value = paidToken;
  } catch (err) {
    if (loadId !== currentLoadId) return;
    error.value = err;
  } finally {
    if (loadId === currentLoadId) pending.value = false;
  }
}

watch(() => [props.id, props.contractId], getData, { immediate: true });

// Ordres de tall / retirada i baixes de la gestió que són d'aquest contracte
const contractCutOrders = computed(() =>
  contractData.value ? (data.value?.cut_suply_orders || []).filter(o => o.contract_token === contractData.value.token) : []
);
const contractRemoveOrders = computed(() =>
  contractData.value ? (data.value?.remove_meter_orders || []).filter(o => o.contract_token === contractData.value.token) : []
);
const contractTerminations = computed(() =>
  contractData.value ? (data.value?.contract_termination_requests || []).filter(r => r.contract?.id === contractData.value.id) : []
);

const isClaimPaymentPaid = (claimPayment) =>
  Boolean(paymentStatusPaidToken.value && claimPayment?.payment?.status?.token === paymentStatusPaidToken.value);

const openClaimRequest = () => {
  return navigateTo(`/billing/claim-managements/edit/${props.id}`);
}
</script>

<template>
  <div class="region__content pr-4">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else-if="data" id="item_data" :data-rel="id" class="min-w-0">
      <div class="flex justify-between items-start gap-2 mb-3">
        <H1Region class="min-w-0">
          {{ $t('claim_block.claim_payments') }}: {{ data.token }}
        </H1Region>
        <button @click="openClaimRequest" class="button-primary !px-2.5 !py-1 text-xs shrink-0">
          <Icon name="fa6-solid:arrow-up-right-from-square" />
          <span class="ml-1">{{ $t('common.show_detail') }}</span>
        </button>
      </div>

      <!-- Capçalera: tres parelles etiqueta / valor per fila -->
      <dl class="claim-summary">
        <dt>{{ $t('billing_block.step') }}</dt>
        <dd class="span-3">{{ data.current_step_name || '-' }}</dd>
        <dt>{{ $t('billing_block.due_step') }}</dt>
        <dd>{{ data.current_step_due_date ? formatDate(data.current_step_due_date) : '-' }}</dd>
        <dt class="row-start">{{ $t('common.status') }}</dt>
        <dd><AtomsColorBadge :value="data.status_name" :color="data.status_color" /></dd>
        <template v-if="data.description">
          <dt class="row-start">{{ $t('common.description') }}</dt>
          <dd class="row-rest">{{ data.description }}</dd>
        </template>
      </dl>

      <!-- Resum en caixes amb el mateix estil que les de la fitxa del contracte (Pagament, Comunicació).
           Mateixos comptadors que ClaimRequestManage -->
      <hr class="my-4" />

      <div class="grid grid-cols-3 gap-3">
        <fieldset class="claim-box">
          <legend>{{ $t('billing_block.payments') }}</legend>
          <dl class="claim-box-list">
            <dt>{{ $t('billing_block.pending_payments') }}</dt>
            <dd>{{ data.pending_payments_count }}</dd>
            <dt>{{ $t('reports_block.paid_payments') }}</dt>
            <dd>{{ data.paid_payments_count }}</dd>
            <dt>{{ $t('common.amount') }}</dt>
            <dd>{{ formatMoneyWithCurrency(data.amount) }}</dd>
          </dl>
        </fieldset>

        <fieldset class="claim-box">
          <legend>{{ $t('billing_block.contracts_and_invoices') }}</legend>
          <dl class="claim-box-list">
            <dt>{{ $t('contract_block.affected_contracts') }}</dt>
            <dd>{{ data.total_contracts - data.excluded_contracts_count }}</dd>
            <template v-if="data.contract_termination_requests?.length">
              <dt>{{ $t('common.contract_terminations') }}</dt>
              <dd>{{ data.contract_termination_requests.length }}</dd>
            </template>
            <dt>{{ $t('billing_block.affected_invoices_title') }}</dt>
            <dd>{{ data.affected_invoices_count }}</dd>
            <dt>{{ $t('billing_block.excluded_invoices') }}</dt>
            <dd>{{ data.excluded_invoices_count }}</dd>
          </dl>
        </fieldset>

        <fieldset class="claim-box">
          <legend>{{ $t('common.orders') }}</legend>
          <dl class="claim-box-list">
            <dt>{{ $t('order_block.cut_orders') }}</dt>
            <dd>{{ data.cut_suply_orders?.length || 0 }}</dd>
            <dt>{{ $t('order_block.remove_orders') }}</dt>
            <dd>{{ data.remove_meter_orders?.length || 0 }}</dd>
          </dl>
        </fieldset>

        <!-- Vulnerabilitat (només si n'hi ha) -->
        <fieldset v-if="data.vulnerable_requests_count > 0" class="claim-box">
          <legend>{{ $t('contract_block.vulnerability') }}</legend>
          <dl class="claim-box-list">
            <dt>{{ $t('common.vulnerable_reqs') }}</dt>
            <dd>{{ data.vulnerable_requests_count }}</dd>
            <dt>{{ $t('common.accepted_requests') }}</dt>
            <dd>{{ data.vulnerable_accepted_requests_count }}</dd>
            <dt>{{ $t('common.pending_requests') }}</dt>
            <dd>{{ data.vulnerable_pending_requests_count }}</dd>
          </dl>
        </fieldset>
      </div>

      <!-- Factures d'aquest contracte dins la gestió -->
      <hr v-if="contractData" class="my-4" />
      <div v-if="contractData">
        <div class="flex flex-wrap items-center gap-2 mb-1.5">
          <span class="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{{ $t('contract') }} {{ contractData.token }}</span>
          <span class="text-xs text-slate-500">
            · {{ contractData.pending_payments_count }} {{ (contractData.pending_payments_count === 1 ? $t('billing_block.payment') : $t('billing_block.payments')).toLowerCase() }}
            · <span class="font-bold text-slate-700">{{ formatMoneyWithCurrency(contractData.pending_payments_amount) }}</span>
          </span>
          <span v-if="contractData.is_excluded"
            class="text-xs font-medium px-2 py-0.5 rounded bg-red-100 text-red-700">
            {{ $t('billing_block.excluded') }}
          </span>
          <span v-if="contractData.claim_payments?.some(cp => cp.is_vulnerable)"
            class="text-xs font-medium px-2 py-0.5 rounded bg-amber-100 text-amber-700">
            {{ $t('contract_block.vulnerable') }}
          </span>
        </div>

        <div class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table class="min-w-full divide-y divide-slate-200">
          <thead class="bg-slate-50">
            <tr class="divide-x divide-slate-200">
              <th class="px-3 py-1.5 text-left text-[11px] font-medium text-slate-500">{{ $t('invoice') }}</th>
              <th class="px-3 py-1.5 text-left text-[11px] font-medium text-slate-500">{{ $t('common.due_date') }}</th>
              <th class="px-3 py-1.5 text-left text-[11px] font-medium text-slate-500">{{ $t('common.amount') }}</th>
              <th class="px-3 py-1.5 text-left text-[11px] font-medium text-slate-500">{{ $t('common.status') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-200">
            <tr v-for="claimPayment in contractData.claim_payments" :key="claimPayment.id"
              class="divide-x divide-slate-200 text-xs" :class="{
              'bg-emerald-50': isClaimPaymentPaid(claimPayment),
              'text-gray-400 line-through': claimPayment.is_excluded,
              'text-slate-800': !claimPayment.is_excluded,
            }">
              <td class="px-3 py-1.5 whitespace-nowrap">{{ claimPayment.payment?.invoice_serie_final || '-' }}</td>
              <td class="px-3 py-1.5 whitespace-nowrap">
                {{ claimPayment.payment?.due_date ? formatDate(claimPayment.payment.due_date) : '-' }}
              </td>
              <td class="px-3 py-1.5 whitespace-nowrap">
                {{ formatMoneyWithCurrency(claimPayment.payment?.amount ?? 0) }}
              </td>
              <td class="px-3 py-1.5 whitespace-nowrap">
                <AtomsColorBadge :color="claimPayment.payment?.status?.color || 'gray'"
                  :value="claimPayment.payment?.status?.name || '-'" />
              </td>
            </tr>
          </tbody>
        </table>
        </div>

        <!-- Ordres i baixes d'aquest contracte generades per la gestió (mateix format que la capçalera) -->
        <dl v-if="contractCutOrders.length || contractRemoveOrders.length || contractTerminations.length"
          class="claim-header mt-3">
          <template v-if="contractCutOrders.length">
            <dt>{{ $t('order_block.cut_orders') }}</dt>
            <dd>{{ contractCutOrders.map(o => o.token).join(', ') }}</dd>
          </template>
          <template v-if="contractRemoveOrders.length">
            <dt>{{ $t('order_block.remove_orders') }}</dt>
            <dd>{{ contractRemoveOrders.map(o => o.token).join(', ') }}</dd>
          </template>
          <template v-if="contractTerminations.length">
            <dt>{{ $t('common.contract_terminations') }}</dt>
            <dd class="flex flex-wrap items-center gap-2">
              <span v-for="termination in contractTerminations" :key="termination.id"
                class="inline-flex items-center gap-1">
                <span>{{ termination.token }}</span>
                <AtomsColorBadge v-if="termination.status" :value="termination.status.name"
                  :color="termination.status.color" />
              </span>
            </dd>
          </template>
        </dl>
      </div>
    </div>
  </div>
</template>

<style scoped>
.claim-header {
  display: grid;
  /* Amplada fixa de l'etiqueta perquè totes les llistes de la regió quedin alineades */
  grid-template-columns: 10rem minmax(0, 1fr);
  column-gap: 1.5rem;
  row-gap: 0.25rem;
  align-items: center;
}

.claim-header dt {
  color: rgb(71 85 105);
}

/* Resum: tres parelles etiqueta / valor per fila. Les columnes d'etiqueta s'ajusten a
   l'etiqueta més llarga de la columna i les de valor es reparteixen l'espai restant,
   així els tres blocs queden repartits per tota l'amplada i alineats entre files */
.claim-summary {
  display: grid;
  grid-template-columns: repeat(3, max-content minmax(0, 1fr));
  column-gap: 1rem;
  row-gap: 0.25rem;
  align-items: center;
}

.claim-summary dt {
  color: rgb(71 85 105);
}

.claim-summary dd {
  padding-right: 1rem;
}

/* Força que la parella comenci una fila nova */
.claim-summary .row-start {
  grid-column-start: 1;
}

/* Valor que ocupa tres columnes (el nom del pas), perquè la parella següent quedi a la tercera columna */
.claim-summary .span-3 {
  grid-column: span 3;
}

/* Valor que ocupa la resta de la fila */
.claim-summary .row-rest {
  grid-column: span 5;
}

/* Caixa de resum: fons blau de les caixes de la fitxa del contracte, amb les vores arrodonides
   i el títol sobre la vora com les seccions de la gestió (ClaimRequestManage) */
.claim-box {
  min-width: 0;
  border: 1px solid rgb(226 232 240);
  border-radius: 0.75rem;
  background-color: rgb(240 249 255);
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  padding: 0.25rem 1rem 0.75rem;
}

/* Títol dins d'un requadre blanc arrodonit perquè el text no quedi sobre el fons blau */
.claim-box legend {
  padding: 0.125rem 0.625rem;
  font-weight: 500;
  background-color: #fff;
  border: 1px solid rgb(226 232 240);
  border-radius: 0.5rem;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
}

.claim-box-list {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  column-gap: 1rem;
  row-gap: 0.25rem;
}

.claim-box-list dt {
  color: rgb(71 85 105);
}
</style>
