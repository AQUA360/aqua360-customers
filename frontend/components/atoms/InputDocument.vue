<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import AtomsInputFile from '~/components/atoms/InputFile.vue';

const { t } = useI18n();

const props = defineProps({
  doc_type: {
    type: Object,
    required: true
  },
  is_checked: {
    type: Boolean,
    default: false
  },
});



const emit = defineEmits([
  'document-checked',
  'document-update',
  'document-delete'
]);

// Canviem el nom de la referència local per evitar conflicte
const local_checked = ref(false);

// Funció per manejar el canvi del checkbox
const handleDocumentCheck = (event) => {
  local_checked.value = event.target.checked;
  emit('document-checked', {
    type: props.doc_type.token,
    checked: local_checked.value
  });
};

// Funció per manejar l'actualització del fitxer
const handleDocumentUpdate = (file) => {
  emit('document-update', {
    type: props.doc_type.token,
    file: file
  });
};

// Funció per manejar l'eliminació del fitxer
const handleDocumentDelete = () => {
  emit('document-delete', {
    type: props.doc_type.token,
  });
};

onMounted(() => {
  local_checked.value = props.is_checked;
});

watch(() => props.is_checked, (value) => {
  local_checked.value = value;
});

</script>

<template>
  <fieldset class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded">
    <legend class="px-3 font-semibold bg-white shadow">
      <Icon name="fa6-regular:file" class="mr-2" />
      <span>{{ doc_type.name }}</span>
      <span v-if="doc_type.is_mandatory" class="text-red-500 ml-1">*</span>
    </legend>
    <span class="flex gap-3 pl-1 pt-1">
      <label class="text-slate-800 text-base flex items-center gap-1">
        <input @change="handleDocumentCheck" type="checkbox" class="mr-2" :checked="local_checked" />
        {{ t('common.checked') }}
      </label>
      <AtomsInputFile 
        :disabled="!local_checked" 
        @update="handleDocumentUpdate" 
        @delete="handleDocumentDelete" 
        :name="doc_type.token + 'File'" 
        :uploaded="null" 
        fullWidth 
        class="w-full" 
      />
    </span>
  </fieldset>
</template>
