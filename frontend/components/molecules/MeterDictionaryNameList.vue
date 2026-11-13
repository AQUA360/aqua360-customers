<script setup>
// Llista editable (només nom) d'un diccionari de comptadors: alta, canvi de nom i esborrat.
// Els errors del backend (duplicats, valor en ús...) ja els mostra $apiManager com a toast.
import { ref, watch, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
  title: { type: String, default: '' },
  service: { type: Object, required: true }, // { list, create, update, remove }
  listParams: { type: Object, default: () => ({}) }, // filtres de la llista (p. ex. { manufacturer: id })
  createPayload: { type: Object, default: () => ({}) }, // camps extra en crear (p. ex. { manufacturer: id })
  selectable: { type: Boolean, default: false },
  selectedId: { type: Number, default: null },
  disabled: { type: Boolean, default: false }, // no es pot carregar ni crear (p. ex. sense fabricant)
  disabledHint: { type: String, default: '' },
});

const emit = defineEmits(['select', 'changed']);
const { t } = useI18n();

const MAX_LENGTH = 255;
const items = ref([]);
const loading = ref(false);
const saving = ref(false);

const adding = ref(false);
const newName = ref('');
const newInput = ref(null);

const editingId = ref(null);
const editingName = ref('');

const load = async () => {
  if (props.disabled) {
    items.value = [];
    return;
  }
  loading.value = true;
  try {
    items.value = await props.service.list(props.listParams);
  } catch (error) {
    console.error('Error loading meter dictionary values:', error);
    items.value = [];
  } finally {
    loading.value = false;
  }
};

const startAdd = async () => {
  adding.value = true;
  newName.value = '';
  await nextTick();
  newInput.value?.focus();
};

const cancelAdd = () => {
  adding.value = false;
  newName.value = '';
};

const confirmAdd = async () => {
  const name = newName.value.trim();
  if (!name || saving.value) return;
  saving.value = true;
  try {
    const created = await props.service.create({ name, ...props.createPayload });
    cancelAdd();
    await load();
    emit('changed');
    if (props.selectable) emit('select', created);
  } catch (error) {
    // Es manté el formulari obert amb el text perquè l'usuari el pugui corregir
  } finally {
    saving.value = false;
  }
};

const startEdit = (item) => {
  editingId.value = item.id;
  editingName.value = item.name;
};

const cancelEdit = () => {
  editingId.value = null;
  editingName.value = '';
};

const confirmEdit = async (item) => {
  const name = editingName.value.trim();
  if (!name || saving.value) return;
  if (name === item.name) {
    cancelEdit();
    return;
  }
  saving.value = true;
  try {
    const updated = await props.service.update(item.id, { name });
    cancelEdit();
    await load();
    emit('changed');
    if (props.selectable && props.selectedId === item.id) emit('select', updated);
  } catch (error) {
    // Es manté l'edició oberta
  } finally {
    saving.value = false;
  }
};

const onDelete = async (item) => {
  if (!confirm(t('confirmation_text_block.confirm_delete'))) return;
  try {
    await props.service.remove(item.id);
    await load();
    emit('changed');
    if (props.selectable && props.selectedId === item.id) emit('select', null);
  } catch (error) {
    // En ús per algun comptador: el backend respon 400 i es mostra el missatge
  }
};

watch(() => [props.disabled, JSON.stringify(props.listParams)], () => {
  cancelAdd();
  cancelEdit();
  load();
}, { immediate: true });

defineExpose({ load });
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-1">
      <span class="text-sm font-medium text-slate-500">{{ title }}</span>
      <span class="text-sm text-slate-400">{{ t('common.total') }}: {{ items.length }}</span>
    </div>

    <p v-if="disabled" class="text-sm text-slate-400 italic p-2 border">{{ disabledHint }}</p>

    <div v-else class="border">
      <div v-if="loading" class="p-2 text-slate-500">
        <Icon name="fa6-solid:spinner" class="animate-spin mr-1" /> {{ t('common.loading') }}...
      </div>
      <p v-else-if="items.length === 0" class="p-2 text-slate-400">{{ t('common.no_records') }}</p>

      <div v-for="item in items" :key="item.id"
        class="flex items-center gap-1 border-b last:border-b-0 px-2 py-1 bg-white"
        :class="{ 'bg-sky-50': selectable && selectedId === item.id }">
        <template v-if="editingId === item.id">
          <input v-model="editingName" class="input flex-1" :maxlength="MAX_LENGTH" :disabled="saving"
            @keydown.enter.prevent="confirmEdit(item)" @keydown.esc.prevent="cancelEdit" />
          <button type="button" class="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-30"
            :disabled="saving || !editingName.trim()" :title="t('common.save')" @click="confirmEdit(item)">
            <Icon name="fa6-solid:check" class="text-green-600" />
          </button>
          <button type="button" class="px-2 py-1 rounded hover:bg-slate-200" :title="t('common.cancel')"
            @click="cancelEdit">
            <Icon name="fa6-solid:xmark" class="text-slate-500" />
          </button>
        </template>
        <template v-else>
          <button v-if="selectable" type="button" class="flex-1 text-left font-semibold hover:underline"
            @click="emit('select', item)">{{ item.name }}</button>
          <span v-else class="flex-1 font-semibold">{{ item.name }}</span>
          <button type="button" class="px-2 py-1 rounded hover:bg-slate-200" :title="t('common.edit')"
            @click="startEdit(item)">
            <Icon name="fa6-solid:pen" class="text-slate-500" />
          </button>
          <button type="button" class="px-2 py-1 rounded hover:bg-slate-200" :title="t('common.delete')"
            @click="onDelete(item)">
            <Icon name="fa6-solid:trash-can" class="text-slate-500" />
          </button>
        </template>
      </div>

      <div v-if="adding" class="flex items-center gap-1 px-2 py-1 bg-white border-t">
        <input ref="newInput" v-model="newName" class="input flex-1" :maxlength="MAX_LENGTH" :disabled="saving"
          :placeholder="t('common.name')" @keydown.enter.prevent="confirmAdd" @keydown.esc.prevent="cancelAdd" />
        <button type="button" class="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-30"
          :disabled="saving || !newName.trim()" :title="t('common.save')" @click="confirmAdd">
          <Icon name="fa6-solid:check" class="text-green-600" />
        </button>
        <button type="button" class="px-2 py-1 rounded hover:bg-slate-200" :title="t('common.cancel')"
          @click="cancelAdd">
          <Icon name="fa6-solid:xmark" class="text-slate-500" />
        </button>
      </div>
      <button v-else type="button"
        class="block w-full px-2 py-1 text-base text-slate-400 border-t hover:bg-slate-200 text-left active:bg-slate-300"
        @click="startAdd">
        <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ t('common.new_register') }}
      </button>
    </div>
  </div>
</template>
