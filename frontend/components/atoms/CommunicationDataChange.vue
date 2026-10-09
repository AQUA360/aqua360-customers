<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

import { formatDate, formatDateTime } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import TimeRelative from '~/components/atoms/TimeRelative.vue';

const { t } = useI18n()
const props = defineProps({
  id: Number,
});

const { $LoggerApiService } = useNuxtApp();

const emit = defineEmits(['update:count']);

const items = ref([]);

const sameTypes = (item) => {
  const previousTypes = item.previous_types.sort((a, b) => a.id - b.id).map(type => type.id);
  const currentTypes = item.current_types.sort((a, b) => a.id - b.id).map(type => type.id);
  return previousTypes.every(type => currentTypes.includes(type));
}

const getData = async () => {
  try {
    const response = await $LoggerApiService.getAll('communication-change', props.id);
    items.value = response.results;
    emit('update:count', items.value.length);
  } catch (error) {
    console.error(error);
  }
}

onMounted(() => {
  getData();
})

watch(() => props.id, () => {
  getData();
})

</script>
<template>
  <div v-if="items.length > 0" class="border-l ml-4 mt-4">
    <article v-for="item in items" :key="item.id"
      class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
      <span class="absolute left-[-5px] top-0 text-[10px]">
        <Icon name="fa6-solid:circle" class="text-sky-500" />
      </span>
      <footer class="flex justify-between items-center pt-1">
        <div class="flex items-center mb-1">
          <p v-if="item.user" class="text-sm text-gray-700 mr-3">{{ item.user?.username }}</p>
          <p v-else class="text-sm text-gray-700 mr-3">{{ t('common.admin') }}</p>
          <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
            <TimeRelative :datetime=item.timestamp></TimeRelative>
          </p>
        </div>
        <div>
          <span class="text-slate-400 text-sm">{{ formatDateTime(item.timestamp) }}</span>
        </div>
      </footer>
      <p class="text-sm text-gray-800">
      <div v-if="!sameTypes(item)" class="flex gap-3">
        <span class="text-slate-500">{{item.previous_types.length > 0 ? item.previous_types.map(type => type.name).join(', ') : t('common.no_type')}}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{item.current_types.length > 0 ? item.current_types.map(type => type.name).join(', ') : t('common.no_type')}}</span>
      </div>
      <div class="flex gap-3"
        v-if="item?.previous_used_email !== item?.current_used_email">
        <span class="text-slate-500">{{ item.previous_used_email || t('common.no_email') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ item.current_used_email || t('common.no_email') }}</span>
      </div>
      <div class="flex gap-3"
        v-if="item?.previous_used_address !== item?.current_used_address">
        <span class="text-slate-500">{{ item.previous_used_address || t('address_block.no_address') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ item.current_used_address || t('address_block.no_address') }}</span>
      </div>
      <div class="flex gap-3"
        v-if="item?.previous_used_phone !== item?.current_used_phone">
        <span class="text-slate-500">{{ item.previous_used_phone || t('common.no_tlf') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ item.current_used_phone || t('common.no_tlf') }}</span>
      </div>
      </p>
      <p v-if="item.observation" class="text-sm text-gray-800 italic">{{ item.observation }}</p>
    </article>
  </div>
  <div v-else class="mt-2">
    <div class="">
      <span class="footering text-sm text-slate-500">{{ $t('common.no_data_found') }}</span>
    </div>
  </div>
</template>