<script setup>
import { formatDate } from '~/utils/date';
import DurationDays from '../atoms/DurationDays.vue';

const { t } = useI18n();
const { $ClaimRequestApiService } = useNuxtApp();
const props = defineProps({
  item: Object,
  id: {
    type: Number,
    default: null
  },
  current: {
    type: Boolean,
    default: false
  }
});

const localData = ref(props.item);

const getDetail = async () => {
  try {
    if (props.id) {
      let fetchData = await $ClaimRequestApiService.getClaimStepDetail(props.id);
      localData.value = fetchData;
    }
  } catch (error) {
    console.error('Error loading contracts:', error);
  }
};

watch(() => props.id, (newVal) => {
  getDetail();
});

onMounted(async () => {
  if (props.id) {
    getDetail();
  }
});

</script>

<template>
  <div v-if="localData" class="flex justify-between gap-5 p-2 px-4 rounded-lg w-[75%] mb-2" :class="{
    'bg-slate-100': !current,
    'customers-shadow': current
  }">

    <!-- <Icon v-show="current" name="fa6-solid:angles-right" class="text-slate-500 items-center" /> -->
    <div>

      <div class="flex justify-between items-center mb-2">
        <h4 class="text-[14px] text-gray-800 truncate" :class="{
          'font-semibold': current
        }">
        <span class="rounded-full border border-slate-800 px-[6px]">
          {{ localData.position }} 
        </span>
        <span class="px-2">
          {{ localData.name }}
        </span>
        </h4>
      </div>
      <div v-if="localData.description">
        <span class="text-sm text-slate-500 italic">
          {{ localData.description }}
        </span>
      </div>
    </div>

    <div class="min-w-[400px]">



      <div v-if="localData.document_type" class="flex justify-between mt-1">
        <span class="font-medium">{{ t('billing_block.send_doc') }}:</span>
        <span :class="{
          'font-semibold': current,
        }">{{ localData.document_type.name }}</span>
      </div>
      <div v-if="localData.order_type" class="flex justify-between mt-1">
        <span class="font-medium">{{ t('order_block.order_to_emit') }}:</span>
        <span :class="{
          'font-semibold': current,
        }">{{ localData.order_type.name }}</span>
      </div>
      <div class="mt-1 flex justify-between items-center text-sm text-slate-700">
        <span class="font-medium">{{ t('common.duration') }}:</span>
        <span class="">
          <DurationDays v-if="localData.duration && localData.duration_type" :value="{
            duration: localData.duration,
            duration_type: localData.duration_type
          }" />
          <span v-else>-</span>
        </span>
      </div>
      
      <div v-if="localData.next_step" class="text-sm text-slate-700">
        <div class="flex justify-between">
          <span class="font-medium">
            {{ t('billing_block.next_step') }}:
          </span>
          <span :class="{
            'font-semibold': current,
          }">{{ localData.next_step_name }}</span>
        </div>
      </div>
      <div v-else class="text-sm text-slate-700">
        <div class="flex justify-between">
          <span></span>
          <span class="font-medium italic">{{ t('billing_block.last_step') }}</span>
        </div>
      </div>
    </div>


  </div>
</template>
