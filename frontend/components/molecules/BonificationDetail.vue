<script setup>
import { formatDate } from '~/utils/date';
import VariableDetail from '~/components/molecules/VariableDetail.vue';

const { t } = useI18n();


const props = defineProps({
  item: Object,
  deleteButton: {
    type: Boolean,
    default: true
  },
  is_expired: {
    type: Boolean,
    default: false
  }
});

const { $BonificationApiService } = useNuxtApp();

const emit = defineEmits(['delete']);

const onDelete = () => {
  const item = props.item;
  console.log('onDelete');
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    $BonificationApiService.doDelete(item).then(() => {
      emit('delete', item)
    });
  }
}
</script>

<template>
  <div class="p-4 rounded relative max-w-xl group">
    <p class="font-semibold mb-2 flex items-center gap-2" :class="{'text-slate-500 line-through italic': is_expired}">
      {{ item.bonification_type.name }}
      <span v-if="item.is_aca_bonification"
        class="text-xs font-normal px-3 py-1 rounded-full whitespace-nowrap"
        :class="item.sent_to_aca ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'">
        {{ item.sent_to_aca ? $t('common.sent_to_aca') : $t('common.pending_to_send_aca') }}
      </span>
    </p>
    <ul v-if="item.documentation_files" class="mb-2">
      <li v-for="document in item.documentation_files" :key="document.id">
        <Icon name="fa6-solid:check" class="mr-2" />
        <a v-if="document.file" :href="document.file" target="_blank" class="text-blue-500 underline">{{ document.name
          }}</a>
        <span v-else>{{ document.name }}</span>
      </li>
    </ul>
    <ul v-if="item.variables">
      <li v-for="variable in item.variables" :key="variable.id" >
        <VariableDetail :item="variable" v-if="variable" :deleteButton=false :editButton="false" :is_expired="is_expired" />
      </li>
    </ul>

    <button @click="onDelete" v-if="deleteButton"
      class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
      <Icon name="fa6-solid:trash" />
    </button>
  </div>

</template>