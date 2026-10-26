<script setup>
import { formatDate } from '~/utils/date';
const { t } = useI18n();

const props = defineProps({
  item: Object,
  deleteButton: {
    type: Boolean,
    default: true
  },
  // Opt-in: el llapis només s'ha de veure on el pare escolta `@edit` i obre un
  // formulari. Per defecte amagat, perquè un llapis que no fa res confon.
  editButton: {
    type: Boolean,
    default: false
  },
  is_expired: {
    type: Boolean,
    default: false
  },
  showValue: {
    type: Boolean,
    default: true
  }
});

const { $VariableApiService, $BonificationApiService } = useNuxtApp();

const emit = defineEmits(['delete', 'edit']);

// Bonificació de la qual s'està eliminant l'última variable: obre el modal perquè
// l'usuari decideixi si també l'elimina.
const lastVariableBonification = ref(null);

const onDelete = async () => {
  const item = props.item;
  if (item.bonification) {
    const bonification = await $BonificationApiService.getDetail(item.bonification);
    if (!bonification.variables?.some(variable => variable.id !== item.id)) {
      lastVariableBonification.value = bonification;
      return;
    }
  }
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    await deleteVariable();
  }
}

const deleteVariable = async (deleteBonification = false) => {
  const item = props.item;
  const bonification = lastVariableBonification.value;
  lastVariableBonification.value = null;
  await $VariableApiService.doDelete(item);
  if (deleteBonification) {
    await $BonificationApiService.doDelete(bonification);
  }
  emit('delete', item);
}

const edit = () => {
  const item = props.item;
  emit('edit', item)
}

onMounted(() => {
})

</script>

<template>
  <div class="py-1 rounded relative max-w-xl group">
    <div class="flex gap-2">
      <Icon name="fa6-solid:gear" class="mt-1" :class="{'text-slate-500': is_expired}" />
      <span class="">
        <span class="block w-full flex items-center">
          <abbr :title="item.token" class="font-semibold" :class="{'text-slate-500 line-through': is_expired}">
            {{ item.name }}</abbr><span v-if="item.value">: </span>
            <span v-if="showValue && item.value !== 'True'" class="bg-white px-2 py-1 border rounded">{{ item.value
            }}</span>
            <Icon v-if="showValue && item.value === 'True' && !is_expired" name="fa6-solid:circle-check" class="text-green-500" />
        </span>
        <span v-if="(item.start_at || item.end_at) && !is_expired">
          {{ item.start_at ? `${t('common.from')} ${formatDate(item.start_at)}` : '' }}
          {{ item.start_at && item.end_at ? ` ${t('common.to')}  ` : '' }}
          {{ item.end_at ? formatDate(item.end_at) : '' }}
        </span>
        <span v-if="item.start_at && item.end_at && is_expired":class="{'italic text-slate-600': is_expired}">
          {{  item.end_at ? t("common.expired") + ': ' + formatDate(item.end_at) : '' }}
        </span>
      </span>
    </div>

    <button v-if="deleteButton" @click="onDelete"
      class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-0 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
      <Icon name="fa6-solid:trash" />
    </button>
    <button  v-if="editButton" @click="edit"
      class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white top-0 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100"
      :class="deleteButton ? 'right-12' : 'right-3'">
      <Icon name="fa6-solid:pencil" />
    </button>

    <Teleport to="body">
      <div v-if="lastVariableBonification">
        <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="lastVariableBonification = null" />
        <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
          aria-modal="true" @click="lastVariableBonification = null">
          <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full relative" @click.stop>
            <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
              :aria-label="t('common.cancel')" @click="lastVariableBonification = null">
              <Icon name="fa6-solid:xmark" class="text-xl" />
            </button>
            <p class="leading-relaxed text-slate-600 font-medium pr-6">
              {{ t('confirmation_text_block.confirm_delete_last_bonification_variable', {
                name: lastVariableBonification.bonification_type?.name || lastVariableBonification.token }) }}
            </p>
            <div class="flex flex-wrap justify-end gap-2 mt-6">
              <button type="button" class="button-default" @click="deleteVariable(true)">
                {{ t('confirmation_text_block.delete_variable_and_bonification') }}
              </button>
              <button type="button" class="button-default" @click="deleteVariable(false)">
                {{ t('confirmation_text_block.delete_only_variable') }}
              </button>
              <button type="button" class="button-primary" @click="lastVariableBonification = null">
                {{ t('common.cancel') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>