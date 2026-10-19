<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import DashboardCardFrame from './DashboardCardFrame.vue';
import CalendarTable from '~/components/molecules/CalendarTable.vue';

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
      <NuxtLink v-if="!editing" to="/calendar" class="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100"
        :title="t('calendar_tasks.open_calendar')">
        <Icon name="fa6-solid:up-right-from-square" />
      </NuxtLink>
    </template>
    <CalendarTable :key="refreshKey" />
  </DashboardCardFrame>
</template>
