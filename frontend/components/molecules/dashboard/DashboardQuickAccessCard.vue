<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import DashboardCardFrame from './DashboardCardFrame.vue';

// Accessos ràpids que hi havia a la pàgina d'inici abans del dashboard personalitzable.
defineProps({
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
});
const emit = defineEmits(['configure', 'remove']);

const { t } = useI18n();

const activeSupplyPointToken = ref(localStorage.getItem('config_supply_point_status_activate_token'));
const pendingContractTerminationToken = ref(1);

/** Navigate to a configured shortcut with its optional query values. */
const showPage = (path, variables, advance_filters, search) => {
  navigateTo({
    path: path,
    query: {
      action: 'filterPage',
      variables: variables,
      advance_filters: advance_filters,
      search: search
    }
  })
}

const linkClass = 'flex text-left w-full gap-3 text-sm items-center font-medium py-1.5 px-1 leading-[14px] hover:bg-slate-200 rounded my-1';
</script>

<template>
  <DashboardCardFrame :card-key="item.key" :editing="editing" :refreshable="false"
    @configure="emit('configure')" @remove="emit('remove')">
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      <div>
        <span class="text-sm font-semibold text-slate-500 flex gap-3 mb-2">{{ t('service') }}</span>
        <NuxtLink to="/service/meters/add" :class="linkClass">{{ t('service_block.new_meter') }}</NuxtLink>
        <NuxtLink to="/service/connection-requests/add" :class="linkClass">{{ t('service_block.new_connection_request') }}</NuxtLink>
        <button :class="linkClass" @click="showPage('service/supplypoints', [activeSupplyPointToken], null, null)">
          {{ t('dashboard.active_supply_points') }}
        </button>
        <button :class="linkClass">{{ t('dashboard.active_supply_cuts') }}</button>
      </div>
      <div>
        <span class="text-sm font-semibold text-slate-500 flex gap-3 mb-2">{{ t('contracting') }}</span>
        <NuxtLink to="/contract/contract-requests/add" :class="linkClass">{{ t('contract_block.new_contract') }}</NuxtLink>
        <button :class="linkClass" @click="showPage('contract/contract-terminations', [pendingContractTerminationToken], null, null)">
          {{ t('dashboard.pending_contract_terminations') }}
        </button>
        <button :class="linkClass" @click="showPage('contract/contracts', [1], ['variable_type'], null)">
          <Icon name="fa-regular:star" size="14px" />
          {{ t('dashboard.relevant_first') }}
        </button>
      </div>
      <div>
        <span class="text-sm font-semibold text-slate-500 flex gap-3 mb-2">{{ t('billing') }}</span>
        <button :class="linkClass">{{ t('dashboard.start_current_batch') }}</button>
        <button :class="linkClass">{{ t('dashboard.unreturned_bails') }}</button>
      </div>
      <div>
        <span class="text-sm font-semibold text-slate-500 flex gap-3 mb-2">{{ t('work_orders') }}</span>
        <button :class="linkClass">{{ t('order_block.new_order') }}</button>
        <button :class="linkClass">{{ t('dashboard.pending_orders') }}</button>
      </div>
    </div>
  </DashboardCardFrame>
</template>
