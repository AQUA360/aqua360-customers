<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  order: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['show-detail']);

const showDetail = (component, id) => {
  emit('show-detail', component, id);
}

onMounted(() => {
});

</script>

<template>
  <div>
    <div v-if="data" class="flex items-center justify-between mt-1">
      <div class="flex items-center gap-2">
        <Icon name="fa6-solid:screwdriver-wrench" class="text-slate-600" />
        <button v-if="order" @click="showDetail('OrderRegion', order.id)" 
        class="text-sky-500 underline hover:text-sky-600 hover:no-underline">
          <span class="font-semibold">{{ data.name }}</span>
        </button>
        <span v-else class="font-semibold">{{ data.name }}</span>
      </div>
      <div v-if="order" class="">
        <AtomsColorBadge :value="order.status?.name" :color="order.status?.color" />
      </div>
    </div>
    <div v-if="order">
      <div class="flex items-center gap-2">
        <FieldDetail :label="$t('common.creation_date')" :value="formatDate(order.created_at)" />
        <FieldDetail class="truncate" :label="$t('common.operators')" :value="order.operators?.length > 0 ? order.operators.map(operator => operator.name).join(', ') : t('common.no_records')" />
      </div>
    </div>
  </div>
</template>
