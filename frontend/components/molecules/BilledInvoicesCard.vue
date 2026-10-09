<script setup>
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const { $InvoiceApiService } = useNuxtApp();

const props = defineProps({
  billing_id: [String, Number],
  is_finished: Boolean,
  update_cards: Boolean
});

const loadingBilledInvoices = ref(false);
const billedInvoices = ref({});

const emit = defineEmits(['open-billed-invoices']);

const loadBilledInvoices = async () => {
  if (!props.billing_id) return;
  loadingBilledInvoices.value = true;
  try {
    const res = await $InvoiceApiService.getBilledInvoices(props.billing_id)
    billedInvoices.value = res;
  } catch (err) {
    console.error(err);
  } finally {
    loadingBilledInvoices.value = false;
  }
}

onMounted(() => {
  loadBilledInvoices();
});

watch(() => props.billing_id, () => {
  loadBilledInvoices();
});

watch(() => props.update_cards, () => {
  loadBilledInvoices();
});
</script>

<template>
  <div class="footering border border-gray-300 rounded-md bg-white max-w-md h-fit">
    <AtomsAppLoading v-if="loadingBilledInvoices" />
    <div v-else>
      <ul class="divide-y divide-gray-200">
        <li class="flex justify-between items-center p-4 relative group">
          <span class="font-bold">{{ t('billing_block.billed_outside_billing') }}</span>
          <span class="inline-flex items-center bg-orange-300 text-slate-700 text-sm rounded-full px-2 py-1 ml-2 mr-5">
            {{ billedInvoices.total_billed }}</span>
          <div
            class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full rounded-t-md absolute top-0 right-0 flex items-center justify-center"
            @click="emit('open-billed-invoices', 'all_billed')" :title="t('common.refresh')">
            <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
          </div>
          <!-- <div
            class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 h-full rounded-t-md absolute top-0 right-0 flex items-center justify-center"
            @click="loadBilledInvoices" :title="t('common.refresh')">
            <Icon name="fa6-solid:rotate-right" class="w-4 h-4 text-slate-500" />
          </div> -->
        </li>
      </ul>
      <ul class="p-2 space-y-1 border-t border-slate-200">
        <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-1 relative group">
          <span class="text-sm font-medium text-slate-700">{{ t('billing_block.confirmed_invoices') }}</span>
          <span
            class="inline-flex items-center justify-center rounded-full bg-slate-200 py-1 px-2 text-xs font-semibold text-slate-700 mr-5">
            {{ billedInvoices.total_invoices }}
          </span>
          <div @click="emit('open-billed-invoices', 'confirmed_invoices')"
            class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 absolute -top-2 -bottom-0.5 -right-2 flex items-center justify-center">
            <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
          </div>
        </li>
        <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 relative group">
          <span class="text-sm font-medium text-slate-700">{{ t('billing_block.pending_budgets') }}</span>
          <span
            class="inline-flex items-center justify-center rounded-full bg-slate-200 py-1 px-2 text-xs font-semibold text-slate-700 mr-5">
            {{ billedInvoices.total_budgets }}
          </span>
          <div @click="emit('open-billed-invoices', 'pending_budgets')"
            class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 absolute -top-0.5 -bottom-2 -right-2 rounded-br-md flex items-center justify-center">
            <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
          </div>
        </li>
        <li class="flex items-center justify-between rounded-lg bg-slate-50/70 px-3 py-2 relative group">
          <span class="text-sm font-medium text-slate-700">{{ t('billing_block.found_match_invoice') }}</span>
          <span
            class="inline-flex items-center justify-center rounded-full bg-amber-200 py-1 px-2 text-xs font-semibold text-amber-700 mr-5">
            {{ billedInvoices.total_found_match }}
          </span>
          <div @click="emit('open-billed-invoices', 'found_match')"
            class="w-10 cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-150 bg-gradient-to-r from-transparent to-slate-300 absolute -top-0.5 -bottom-2 -right-2 rounded-br-md flex items-center justify-center">
            <Icon name="fa6-solid:eye" class="w-4 h-4 text-slate-500" />
          </div>
        </li>
        <hr>
        <li class="flex items-center justify-between rounded-lg px-3 py-2 relative group italic">
          <span class="text-sm font-medium text-slate-700">{{ t('billing_block.other_managements') }}</span>
          <span
            class="inline-flex items-center justify-center rounded-full bg-slate-200 py-1 px-2 text-xs font-semibold text-slate-700 mr-5">
            {{ billedInvoices.total_other_mngs }}
          </span>

        </li>
      </ul>
    </div>
  </div>
</template>
