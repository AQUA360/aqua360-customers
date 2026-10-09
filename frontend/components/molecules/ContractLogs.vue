<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { format } from 'date-fns';
import TimeRelative from '~/components/atoms/TimeRelative.vue';

const { t } = useI18n();
const { $ContractApiService } = useNuxtApp();

const props = defineProps({
  contract_id: {
    type: Number,
    required: true
  },
  contract_token: {
    type: String
  }
});

const logs = ref([]);
const loading = ref(true);
const error = ref(null);

const fetchLogs = async () => {
  loading.value = true;
  try {
    const response = await $ContractApiService.getLogs(props.contract_id);
    logs.value = response;
  } catch (err) {
    error.value = err;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchLogs();
});
</script>

<template>
  <div class="h-full">
    <div class="p-4 h-20">
      <h2 class="text-xl font-semibold mb-4">{{ t('contract_block.contract_change_history') + ' ' + contract_token }}</h2>
    </div>
    
    <div v-if="loading" class="flex justify-center items-center py-4">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
      <span class="ml-2">{{ t('common.loading') }}...</span>
    </div>

    <div v-else-if="error" class="text-red-500 p-4">
      {{ t('common.error_load_history') }}
    </div>

    <div v-else-if="logs.length === 0" class="text-gray-500 text-center py-4">
      {{ t('common.no_records') }}
    </div>

    <div v-else class="px-4 h-[calc(100vh-10rem)] overflow-y-auto">
      <div class="space-y-4">
        <div v-for="(log, index) in logs" :key="index" class="border-b pb-4">
          <div class="flex justify-between items-start mb-2">
            <div class="text-sm font-medium text-slate-600">
              {{ t('common.operation') + ': ' + log.operation_token }}
            </div>
            <TimeRelative :datetime=log.created_at></TimeRelative>
          </div>
          
          <div class="flex items-center gap-2 text-sm">
            <span class="font-medium text-slate-700">{{ log.field_name }}:</span>
            <span class="text-slate-600">{{ log.old_value || t('common.no_value') }}</span>
            <Icon name="fa6-solid:arrow-right" class="text-slate-400" />
            <span class="text-slate-800 font-bold">{{ log.new_value || t('common.no_value') }}</span>
          </div>

          <div class="text-sm text-slate-800 mt-1">
            {{ t('common.per') }}: <span class="font-bold">{{ log.user?.username || t('common.unknown') }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template> 