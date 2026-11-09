<script setup>
// Desplegable d'un diccionari amb alta inline: el botó "+" substitueix el selector per un
// camp de text amb confirmar/cancel·lar. En confirmar es crea el valor (onCreate) i se selecciona.
import { ref, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
  modelValue: { type: [Object, null], default: null },
  options: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  createDisabled: { type: Boolean, default: false },
  createDisabledHint: { type: String, default: '' },
  // async (name) => { label, code }. Si llança, es manté el camp obert amb el text.
  onCreate: { type: Function, required: true },
  maxlength: { type: Number, default: 255 },
});

const emit = defineEmits(['update:modelValue']);
const { t } = useI18n();

const creating = ref(false);
const saving = ref(false);
const newName = ref('');
const showEmptyError = ref(false);
const input = ref(null);

const startCreate = async () => {
  if (props.disabled || props.createDisabled) return;
  creating.value = true;
  newName.value = '';
  showEmptyError.value = false;
  await nextTick();
  input.value?.focus();
};

const cancelCreate = () => {
  creating.value = false;
  newName.value = '';
  showEmptyError.value = false;
};

const confirmCreate = async () => {
  if (saving.value) return;
  const name = newName.value.trim();
  if (!name) {
    showEmptyError.value = true;
    return;
  }
  saving.value = true;
  try {
    const option = await props.onCreate(name);
    emit('update:modelValue', option);
    cancelCreate();
  } catch (error) {
    console.error('Error creating dictionary value:', error);
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <div>
    <div v-if="!creating" class="flex items-center gap-1">
      <v-select :model-value="modelValue" class="block w-full" :options="options" :disabled="disabled"
        @update:modelValue="emit('update:modelValue', $event)">
        <template #no-options>
          {{ t('common.no_records') }}
        </template>
      </v-select>
      <button type="button"
        class="px-2 py-1 rounded border border-slate-200 hover:bg-slate-200 active:bg-slate-300 disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="disabled || createDisabled"
        :title="createDisabled && createDisabledHint ? createDisabledHint : t('service_block.add_new_value')"
        :aria-label="t('service_block.add_new_value')" @click="startCreate">
        <Icon name="fa6-solid:plus" class="text-slate-500" />
      </button>
    </div>
    <div v-else>
      <div class="flex items-center gap-1">
        <input ref="input" v-model="newName" type="text" class="input flex-1" :class="{ 'invalid': showEmptyError }"
          :maxlength="maxlength" :disabled="saving" :placeholder="t('common.name')"
          @input="showEmptyError = false" @keydown.enter.prevent="confirmCreate" @keydown.esc.prevent="cancelCreate" />
        <button type="button" class="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-30" :disabled="saving"
          :title="t('common.save')" :aria-label="t('common.save')" @click="confirmCreate">
          <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:check'"
            :class="saving ? 'animate-spin text-slate-500' : 'text-green-600'" />
        </button>
        <button type="button" class="px-2 py-1 rounded hover:bg-slate-200" :disabled="saving"
          :title="t('common.cancel')" :aria-label="t('common.cancel')" @click="cancelCreate">
          <Icon name="fa6-solid:xmark" class="text-slate-500" />
        </button>
      </div>
    </div>
  </div>
</template>
