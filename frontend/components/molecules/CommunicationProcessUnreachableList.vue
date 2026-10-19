<script setup>
import { exclusionReasonLabel } from '~/utils/communication-exclusion';

// Persones que no rebran la comunicació i per què ({id, token, full_name,
// contracts, reasons}). Es fa servir als passos 2 i 6 del wizard.
defineProps({
  persons: {
    type: Array,
    default: () => []
  },
});

const emit = defineEmits(['show-person']);
const { t } = useI18n();
</script>

<template>
  <div class="flex-1">
    <p class="text-sm text-gray-500 mb-4">{{ $t('customer_service_block.unreachable_info') }}</p>
    <div v-if="persons.length === 0" class="text-slate-500 p-2">
      {{ $t('customer_service_block.no_unreachable') }}
    </div>
    <template v-else>
      <div class="grid grid-cols-[80px,250px,180px,1fr] px-2 gap-2 w-full font-semibold">
        <span class="col-span-2">{{ $t('customer_service_block.recipient') }}</span>
        <span>{{ $t('contracts') }}</span>
        <span>{{ $t('customer_service_block.exclusion_reason') }}</span>
      </div>
      <div class="divide-y divide-gray-200 h-[55vh] overflow-auto">
        <div v-for="(person, index) in persons" :key="`unreachable-${person.id}-${index}`"
          class="grid grid-cols-[80px,250px,180px,1fr] gap-2 px-2 py-3 items-center"
          :class="index % 2 === 0 ? 'bg-sky-50' : 'bg-white'">
          <button @click="emit('show-person', person.id)"
            class="text-sky-500 hover:text-sky-700 underline text-left"
            :title="`${$t('common.show')} ${$t('common.details')}`">
            {{ person.token }}
          </button>
          <span class="truncate">{{ person.full_name }}</span>
          <span class="truncate text-sm" :title="(person.contracts || []).map(c => c.supply_address).filter(Boolean).join('\n')">
            {{ (person.contracts || []).map(c => c.token).join(', ') }}
          </span>
          <span class="flex flex-wrap gap-1">
            <span v-for="reason in person.reasons" :key="reason"
              class="px-2 py-0.5 text-xs rounded-full bg-red-50 text-red-700 border border-red-200">
              {{ exclusionReasonLabel(t, reason) }}
            </span>
          </span>
        </div>
      </div>
    </template>
  </div>
</template>
