<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import TimeRelative from '~/components/atoms/TimeRelative.vue';

const { t } = useI18n();
const { $PersonApiService } = useNuxtApp();

const props = defineProps({
  person_id: {
    type: Number,
    required: true
  },
  person_token: {
    type: String
  },
  canChange: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['update:count']);

const logs = ref([]);
const loading = ref(true);
const error = ref(null);

const fetchLogs = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await $PersonApiService.getLogs(props.person_id);
    logs.value = response || [];
    emit('update:count', logs.value.length);
  } catch (err) {
    error.value = err;
  } finally {
    loading.value = false;
  }
};

const modify = () => {
  return navigateTo('/contract/persons/edit/' + props.person_id);
};

onMounted(() => {
  fetchLogs();
});
</script>

<template>
  <div>
    <div v-if="canChange" class="flex justify-end mt-2 mb-4">
      <button @click="modify" class="button-primary !px-2.5 !py-1 text-xs">
        <Icon name="fa6-solid:address-card" /> <span class="ml-1">{{ t('common.modify') }}</span>
      </button>
    </div>

    <div v-if="loading" class="flex justify-center items-center py-4">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
      <span class="ml-2">{{ t('common.loading') }}...</span>
    </div>

    <div v-else-if="error" class="footering text-red-500 p-2">
      {{ t('common.error_load_history') }}
    </div>

    <div v-else>
      <div v-if="!logs?.length">
        <div class="footering text-slate-500 p-2">
          {{ t('common.no_changes') }}
        </div>
      </div>
      <article v-for="log in logs" :key="log.id"
        class="relative p-2 text-base bg-white group hover:bg-slate-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-slate-400">
        <span class="absolute left-[-5px] top-0 text-[10px]">
          <Icon name="fa6-solid:circle" class="text-slate-400" />
        </span>
        <footer class="flex justify-between items-center pt-1">
          <div class="flex items-center mb-1 gap-3">
            <p class="text-sm text-gray-700">{{ log.user?.username || t('common.admin') }}</p>
            <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
              <TimeRelative :datetime="log.created_at" />
            </p>
          </div>
          <span class="text-xs text-slate-400 uppercase tracking-wide">{{ log.operation_token }}</span>
        </footer>
        <p class="text-sm flex items-center gap-2 mt-1">
          <span class="font-medium text-slate-600">{{ log.field_name }}</span>
          <span class="text-slate-400">{{ log.old_value || t('common.no_value') }}</span>
          <Icon name="fa6-solid:arrow-right" class="text-slate-400 text-xs" />
          <span class="text-slate-900 font-medium">{{ log.new_value || t('common.no_value') }}</span>
        </p>
      </article>
    </div>
  </div>
</template>