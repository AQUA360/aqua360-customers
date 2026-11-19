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

      <!-- Capçalera -->
      <dl class="claim-header mb-4">
        <dt>{{ $t('common.status') }}</dt>
        <dd><AtomsColorBadge :value="data.status_name" :color="data.status_color" /></dd>
        <dt>{{ $t('billing_block.step') }}</dt>
        <dd>{{ data.current_step_name || '-' }}</dd>
        <dt>{{ $t('billing_block.due_step') }}</dt>
        <dd>{{ data.current_step_due_date ? formatDate(data.current_step_due_date) : '-' }}</dd>
        <template v-if="data.description">
          <dt>{{ $t('common.description') }}</dt>
          <dd>{{ data.description }}</dd>
        </template>
      </dl>

      <!-- Blocs de resum (mateixos comptadors que a la pàgina de la gestió) -->
      <div class="flex flex-wrap gap-3">
        <div class="flex flex-col border border-gray-200 rounded">
          <div class="flex items-center bg-white px-2">
            {{ $t('billing_block.pending_payments') }}:
            <span class="px-2 py-1 font-bold">{{ data.pending_payments_count }}</span>
          </div>
          <div class="flex items-center bg-white px-2">
            {{ $t('reports_block.paid_payments') }}:
            <span class="px-2 py-1 font-bold">{{ data.paid_payments_count }}</span>
          </div>
          <div class="flex items-center bg-white px-2">
            {{ $t('common.amount') }}:
            <span class="px-2 py-1 font-bold">{{ formatMoneyWithCurrency(data.amount) }}</span>
          </div>
        </div>

        <div class="flex flex-col border border-gray-200 rounded">
          <div class="flex items-center bg-white px-2">
            {{ $t('contract_block.affected_contracts') }}:
            <span class="px-2 py-1 font-bold">{{ data.total_contracts - data.excluded_payments_count }}</span>
          </div>
          <div class="flex items-center bg-white px-2">
            {{ $t('contract_block.excluded_contracts') }}:
            <span class="px-2 py-1 font-bold">{{ data.excluded_payments_count }}</span>
          </div>
          <div v-if="data.contract_termination_requests?.length" class="flex items-center bg-white px-2">
            {{ $t('common.contract_terminations') }}:
            <span class="px-2 py-1 font-bold">{{ data.contract_termination_requests.length }}</span>
          </div>
        </div>

        <div v-if="data.vulnerable_requests_count > 0" class="flex flex-col border border-gray-200 rounded">
          <div class="flex items-center bg-white px-2">
            {{ $t('common.vulnerable_reqs') }}:
            <span class="px-2 py-1 font-bold">{{ data.vulnerable_requests_count }}</span>
          </div>
          <div class="flex items-center bg-white px-2">
            {{ $t('common.accepted_requests') }}:
            <span class="px-2 py-1 font-bold">{{ data.vulnerable_accepted_requests_count }}</span>
          </div>
          <div class="flex items-center bg-white px-2">
            {{ $t('common.pending_requests') }}:
            <span class="px-2 py-1 font-bold">{{ data.vulnerable_pending_requests_count }}</span>
          </div>
        </div>

        <div class="flex flex-col border border-gray-200 rounded">
          <div class="flex items-center bg-white px-2">
            {{ $t('order_block.cut_orders') }}:
            <span class="px-2 py-1 font-bold">{{ data.cut_suply_orders?.length || 0 }}</span>
          </div>
          <div class="flex items-center bg-white px-2">
            {{ $t('order_block.remove_orders') }}:
            <span class="px-2 py-1 font-bold">{{ data.remove_meter_orders?.length || 0 }}</span>
          </div>
        </div>
      </div>

      <!-- Factures d'aquest contracte dins la gestió -->
      <div v-if="contractData" class="mt-6">
        <div class="flex flex-wrap items-center gap-2 mb-2">
          <span class="text-slate-500 font-bold">{{ $t('contract') }} {{ contractData.token }}</span>
          <span class="text-sm text-slate-500">
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

        <table class="min-w-full divide-y divide-gray-200 border border-gray-200 rounded">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('invoice') }}</th>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.due_date') }}</th>
              <th class="px-3 py-1 text-right text-xs font-medium text-gray-500 uppercase">{{ $t('common.amount') }}</th>
              <th class="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">{{ $t('common.status') }}</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="claimPayment in contractData.claim_payments" :key="claimPayment.id" class="text-sm" :class="{
              'bg-emerald-50': isClaimPaymentPaid(claimPayment),
              'text-gray-400 line-through': claimPayment.is_excluded,
            }">
              <td class="px-3 py-1 whitespace-nowrap">{{ claimPayment.payment?.invoice_serie_final || '-' }}</td>
              <td class="px-3 py-1 whitespace-nowrap">
                {{ claimPayment.payment?.due_date ? formatDate(claimPayment.payment.due_date) : '-' }}
              </td>
              <td class="px-3 py-1 whitespace-nowrap text-right">
                {{ formatMoneyWithCurrency(claimPayment.payment?.amount ?? 0) }}
              </td>
              <td class="px-3 py-1 whitespace-nowrap">
                <AtomsColorBadge :color="claimPayment.payment?.status?.color || 'gray'"
                  :value="claimPayment.payment?.status?.name || '-'" />
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Ordres i baixes d'aquest contracte generades per la gestió -->
        <dl v-if="contractCutOrders.length || contractRemoveOrders.length || contractTerminations.length"
          class="claim-header mt-3 text-sm">
          <template v-if="contractCutOrders.length">
            <dt>{{ $t('order_block.cut_orders') }}</dt>
            <dd class="font-medium">{{ contractCutOrders.map(o => o.token).join(', ') }}</dd>
          </template>
          <template v-if="contractRemoveOrders.length">
            <dt>{{ $t('order_block.remove_orders') }}</dt>
            <dd class="font-medium">{{ contractRemoveOrders.map(o => o.token).join(', ') }}</dd>
          </template>
          <template v-if="contractTerminations.length">
            <dt>{{ $t('common.contract_terminations') }}</dt>
            <dd class="flex flex-wrap items-center gap-2">
              <span v-for="termination in contractTerminations" :key="termination.id"
                class="inline-flex items-center gap-1">
                <span class="font-medium">{{ termination.token }}</span>
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
  grid-template-columns: auto minmax(0, 1fr);
  column-gap: 1.5rem;
  row-gap: 0.25rem;
  align-items: center;
}

.claim-header dt {
  color: rgb(71 85 105);
}
</style>
