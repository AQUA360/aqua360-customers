<script setup>
import { ref, onMounted, watch } from 'vue';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDateTime } from '~/utils/date';
import { useI18n } from 'vue-i18n';

const props = defineProps({
  id: {
    type: Number,
    required: true
  }
});

const { t } = useI18n();
const { $OvLogsApiService } = useNuxtApp();

const pending = ref(true);
const error = ref(null);
const data = ref(null);

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $OvLogsApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    console.error(err);
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const getJsonDetails = (detailObj) => {
  if (!detailObj) return [];
  return Object.entries(detailObj).map(([key, value]) => ({
    key,
    value: typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value)
  }));
};

onMounted(() => {
  if (props.id) {
    getData();
  }
});

watch(() => props.id, (newId) => {
  if (newId) {
    getData();
  }
});
</script>

<template>
  <div class="h-full relative font-inter bg-white">
    <div v-if="pending" class="flex justify-center items-center h-[200px]">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error" class="p-4 bg-red-50 text-red-600 rounded">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">
        {{ $t('common.load_again') }}</button></p>
    </div>
    <div v-else-if="data" class="h-full flex flex-col">
      <H1Region class="mb-3 shrink-0">{{ $t('common.ov_logs') }}</H1Region>
      
      <div id="item_data" class="space-y-4 flex-1 overflow-y-auto pb-10">
        <section class="bg-gray-50 p-3 rounded">
          <FieldDetail :label="$t('common.identificator')" :value="data.id" />
          <FieldDetail :label="$t('common.date')" :value="formatDateTime(data.timestamp)" />
          <FieldDetail :label="$t('common.type')" :value="$t('ov_logs_block.types.' + data.type) !== 'ov_logs_block.types.' + data.type ? $t('ov_logs_block.types.' + data.type) : data.type" />
          <FieldDetail :label="$t('common.app')" :value="data.app ? ($t('ov_logs_block.apps.' + data.app) !== 'ov_logs_block.apps.' + data.app ? $t('ov_logs_block.apps.' + data.app) : data.app) : '-'" />
          <FieldDetail :label="$t('user')" :value="data.user_name || 'System'" />
        </section>

        <section v-if="data.detail">
          <h3 class="text-sm font-bold text-slate-600 mb-2 uppercase">{{ $t('common.details') }}</h3>
          <div class="grid grid-cols-1 gap-2 border border-gray-200 rounded p-3 bg-white">
            <div v-for="entry in getJsonDetails(data.detail)" :key="entry.key" class="grid grid-cols-[140px,1fr] text-sm py-1 border-b last:border-0 border-gray-100">
                <span class="text-slate-400 font-medium">{{ $t('ov_logs_block.fields.' + entry.key) !== 'ov_logs_block.fields.' + entry.key ? $t('ov_logs_block.fields.' + entry.key) : entry.key }}:</span>
               <span class="text-slate-800 break-all">{{ entry.value }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
