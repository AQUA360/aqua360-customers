<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { AdjustmentConditionOperationChoices, AdjustmentConditionQuantityDefaultChoices } from '~/utils/adjustment-condition';

const { t } = useI18n()
const props = defineProps({
  item: Object,
  allowEdit: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['edit','delete']);
const columnClass = ref(props.allowEdit ? 'grid-cols-[35px,1fr,1fr,50px]' : 'grid-cols-[1fr,2fr] px-2');

</script>
<template>
  <div v-if="item" :class="columnClass" class="grid gap-2 bg-white rounded items-center border">
    <button v-if="allowEdit" class="px-2 py-2">
      <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500 block-inline mr-1" />
      <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500" />
    </button>
    <button v-if="allowEdit" @click="$emit('edit', item)" class="font-medium flex gap-2 items-center py-2 text-sky-500 underline">{{ item.name }}</button>
    <span v-else class="font-medium flex gap-2 items-center py-2">{{ item.name }}</span>
    <span class="flex gap-2 items-center py-2 pr-2 italic">
      <span>{{ item.quantity?.label }}</span>
      <span>{{ t(AdjustmentConditionOperationChoices[item.operation]) || null }}</span>
      <span>{{ item.formula? item.formula : '' }}</span>
    </span>
    <button v-if="allowEdit" @click="$emit('delete', item)"><Icon name="fa-solid:trash" class="text-slate-600 hover:opacity-50"></Icon></button>
  </div>
</template>
