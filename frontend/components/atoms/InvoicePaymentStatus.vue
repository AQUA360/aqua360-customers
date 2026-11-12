<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { returnedLabel } from '~/utils/invoice-payment-summary';

// Payment status column of the invoice lists: status of the current payment and
// bank returns, which stay visible even if the invoice was paid again later.
const props = defineProps({
  summary: {
    type: Object,
    default: null,
  },
});

const { t } = useI18n();

const returned = computed(() => returnedLabel(t, props.summary));
</script>

<template>
  <div class="min-w-0">
    <AtomsColorBadge
      v-if="summary?.payment_status"
      :value="summary.payment_status.name"
      :color="summary.payment_status.color"
    />
    <span v-else>-</span>
    <p v-if="returned" class="text-xs text-red-600 mt-1 flex items-center gap-1" :title="returned">
      <Icon name="fa6-solid:rotate-left" class="shrink-0" />
      <span class="truncate">{{ returned }}</span>
    </p>
  </div>
</template>
