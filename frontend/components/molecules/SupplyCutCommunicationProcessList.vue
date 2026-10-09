<script setup>
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';

// Processes launched from this supply cut. Each row expands to show the phase
// timeline the backend logged for it, so the user can see how far it got.
const props = defineProps({
  id: Number
});

const emit = defineEmits(['update:count']);

const { t } = useI18n();
const { $CommunicationProcessApiService, $ConfigProjectApiService, $LoggerApiService } = useNuxtApp();

const pending = ref(true);
// Only the processing status polls task progress; the rest are plain badges.
const processingStatusToken = ref(null);
const error = ref(null);
const items = ref([]);

// One row open at a time; null means the list is collapsed.
const expandedId = ref(null);
const processCount = ref(0);

const getData = async () => {
  if (!props.id) return;
  pending.value = true;
  error.value = null;
  try {
    processingStatusToken.value = await $ConfigProjectApiService.get('communication_process_status_processing_token');
    const result = await $CommunicationProcessApiService.getAll('', [], 1, 'created_at', true, [], props.id);
    items.value = result.results || [];
    processCount.value = items.value.length;
    emit('update:count', processCount.value);
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const toggleProcess = (id) => {
  expandedId.value = expandedId.value === id ? null : id;
};

watch(() => props.id, getData);
onMounted(getData);
</script>

<template>
  <div>
    <div v-if="pending" class="flex items-center justify-center py-4">
      <Icon name="fa6-solid:spinner" class="animate-spin text-xl text-slate-500" />
      <span class="ml-2 text-sm text-slate-500">{{ t('common.loading') }}...</span>
    </div>

    <div v-else-if="error" class="py-3">
      <p class="text-sm text-red-600">{{ t('common.error') }}: {{ error.message }}</p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ t('common.load_again') }}</button>
    </div>

    <div v-else-if="!items.length" class="footering text-slate-500 p-2">
      {{ t('common.no_records') }}
    </div>

    <div v-else class="mb-4 rounded-md border border-gray-300 bg-white divide-y">
      <div class="group grid grid-cols-[110px,1fr,150px,150px,30px] divide-x text-sm leading-4">
        <span class="p-2 pl-3 text-slate-600">{{ t('common.date') }}</span>
        <span class="p-2 pl-3 text-slate-600">{{ t('common.identification') }}</span>
        <span class="p-2 pl-3 text-slate-600">{{ t('common.status') }}</span>
        <span class="p-2 pl-3 text-slate-600">{{ t('user') }}</span>
        <span class="p-2 text-slate-600"></span>
      </div>

      <div v-for="item in items" :key="item.id" class="text-sm leading-4">
        <div class="group grid grid-cols-[110px,1fr,150px,150px,30px] divide-x transition-all duration-100 cursor-pointer"
          :class="{ 'bg-yellow-50': expandedId === item.id }" @click="toggleProcess(item.id)">
          <div class="relative footering text-slate-500 p-2">
            {{ formatDate(item.created_at) }}
          </div>
          <div class="relative footering text-slate-500 p-2 truncate" :title="item.description">
            {{ item.description || item.token }}
          </div>
          <div class="relative footering p-2">
            <AtomsProcessColorBadge v-if="item.status_token == processingStatusToken" :value="item.status_name"
              :color="item.status_color" :taskId="item.task_id" @refresh="getData" />
            <AtomsColorBadge v-else :color="item.status_color" :value="item.status_name" />
          </div>
          <div class="relative footering text-slate-500 p-2 truncate">{{ item.user_username }}</div>
          <div class="relative footering p-2 text-center">
            <Icon :name="expandedId === item.id ? 'fa6-solid:chevron-up' : 'fa6-solid:chevron-down'"
              class="text-slate-500" />
          </div>
        </div>

        <MoleculesLogList v-if="expandedId === item.id" entity="communication-process-status" parent_entity="communication_process"
          :id="item.id" :service="$LoggerApiService" />
      </div>
    </div>
  </div>
</template>