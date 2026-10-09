<script setup>
import { ref } from 'vue';
const { t } = useI18n();

const props = defineProps({
  name: String,
  uploaded: String,
  fullWidth: Boolean,
  disabled: Boolean
});

// emits
const emit = defineEmits(['update', 'delete']);
const uploadedFile = ref(props.uploaded);

const getBasename = (url) => {
  if (url && (typeof url === 'string' || url instanceof String))
    return url.split('/').pop();
  else if (url && (typeof url === 'object' || url instanceof Object))
    return url.name;
};

const modifyUploaded = (is_delete = false) => {
  uploadedFile.value = null;
  if (is_delete && confirm(t('confirmation_text_block.confirm_delete_doc'))) {
    emit('delete', null);
  } else {
    setTimeout(() => { // hem d'esperar que faci el canvi i es mostri el input
      if (props.name && props.name != '') {
        var input = document.getElementById(props.name);
        if (input) {
          input.click();
        }
      }
    }, 200);
  }
};

const handleFileInputChange = (event) => {
  const file = event.target.files[0];
  emit('update', file);
};

// watch uploaded
watch(() => props.uploaded, (newVal) => {
  uploadedFile.value = newVal;
});

</script>

<template>
  <div v-if="uploadedFile" class="p-3 px-2 bg-blue-50 leading-6">
    <div class="relative" :class="{ 'w-full': fullWidth, 'max-w-xl': !fullWidth }">
      <span class="flex gap-2">
        <a :href="uploadedFile" target="_blank" class="text-sky-600">
          <Icon name="fa6-regular:file" class="text-slate-500" />
        </a>
        <a :href="uploadedFile" target="_blank" class="text-sky-600 underline hover:no-underline">{{
          getBasename(uploadedFile) }}</a>
      </span>
      <div class="absolute top-[-5px] right-3 flex gap-2">
        <button @click="modifyUploaded(false)"
          class="cursor-pointer shadow-md hover:shadow-none border text-sm w-8 h-8 bg-white top-[-5px] rounded-md text-slate-600">
          <Icon name="fa6-solid:pencil" />
        </button>
        <button @click="modifyUploaded(true)"
          class="cursor-pointer shadow-md hover:shadow-none border text-sm w-8 h-8 bg-white top-[-5px] rounded-md text-slate-600">
          <Icon name="fa6-solid:trash" />
        </button>
      </div>
    </div>
  </div>
  <div v-else class="relative" :class="{ 'opacity-50': disabled }">
    <input :disabled="disabled" @change="handleFileInputChange" type="file" :id="name" :name="name"
      class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
    <div class="absolute inset-y-0 right-0 flex items-center px-2 pointer-events-none">
      <svg class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
      </svg>
    </div>
  </div>
</template>
