<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import DashboardCardFrame from './DashboardCardFrame.vue';
import DailyActivitySummary from '~/components/molecules/DailyActivitySummary.vue';

defineProps({
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
});
const emit = defineEmits(['configure', 'remove']);

const { t } = useI18n();
const refreshKey = ref(0);
</script>

<template>
  <DashboardCardFrame :card-key="item.key" :editing="editing"
    @refresh="refreshKey++" @configure="emit('configure')" @remove="emit('remove')">
    <template #actions>
      <NuxtLink v-if="!editing" to="/billing/reports/daily-activity-summary" class="text-xs text-sky-600 hover:underline mr-1">
        {{ t('daily_activity_block.see_full_report') }}
      </NuxtLink>
    </template>
    <DailyActivitySummary :key="refreshKey" embedded />
  </DashboardCardFrame>
</template>
