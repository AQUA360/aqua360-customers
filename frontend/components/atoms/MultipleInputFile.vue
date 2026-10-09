<script setup>
import { ref } from 'vue';
const { t } = useI18n();

const props = defineProps({
  name: String,
  uploaded: Array,
});

// emits
const emit = defineEmits(['update', 'delete']);
const uploadedFile = ref(props.uploaded);

const files = ref([]);
const fileInput = ref(null)

const getBasename = (url) => {
  return url.split('/').pop();
};

const deleteFile = (file) => {
  uploadedFile.value = null;

  if (confirm(t('confirmation_text_block.confirm_delete_doc'))) {
    let index = files.value.indexOf(file);
    if (index != -1) {
      emit('delete', file.id);
    }
  }

};

const handleFileInputChange = (event) => {
  const file = event.target.files[0];
  emit('update', file);
};


const onSelectFile = () => {
  const input = fileInput.value
  const uploadedFiles = input.files
  if (uploadedFiles && uploadedFiles[0]) {
    const reader = new FileReader()
    reader.readAsDataURL(uploadedFiles[0])

    files.value.push(uploadedFiles[0])

    emit('update', uploadedFiles[0])
  }
}

const chooseFile = () => {
  fileInput.value.click()
}

const setFiles = () => {
  if (props.uploaded.length == 0) return;
  files.value = []
  props.uploaded.forEach(element => {
    files.value.push({
      id: element.id,
      url: element.file,
      name: element.file.split('/').pop().replace('_', ' ')
    });
  });
}

// watch uploaded
watch(() => props.uploaded, (newVal) => {
  setFiles()
});

onMounted(() => {
  setFiles()
});

</script>

<template>
  <div class="w-full h-64 bg-slate-100 border border-gray-300 rounded-md overflow-scroll flex flex-wrap">
    <div v-for="(file, index) in files" :key="index"
      class="p-3 bg-blue-50 leading-6 w-32 h-32 border border-gray-300 rounded-md m-3 group">
      <div class="relative max-w-xl">
        <span class="gap-2 flex flex-col items-center">
          <div class="text-4xl mt-5">
            <Icon name="fa6-regular:file" class="" />
          </div>
          <div class="text-center w-full">
            <a target="_blank" :href="file.url" class="text-sky-600 underline cursor-pointer hover:text-sky-400 block truncate-2-lines"> {{ file.name }}</a>
          </div>
        </span>
        <div class="absolute top-[-5px] right-[-5px] flex gap-2 opacity-0 transition-all duration-300 group-hover:opacity-100">
          <button @click="deleteFile(file)"
            class="cursor-pointer shadow-md border text-sm w-8 h-8 bg-white top-[-5px] rounded-md text-slate-600">
            <Icon name="fa6-solid:trash" />
            </button>
        </div>
      </div>
    </div>
    <div @click="chooseFile" class="relative group cursor-pointer border bg-blue-50 leading-6 w-32 h-32 border-gray-300 rounded-md m-3">
      <span
        class="flex w-full h-full justify-center items-center bg-slate-100 hover:bg-slate-200 text-slate-400 text-lg rounded-md transition-all duration-200">
        <Icon name="fa6-regular:hand-pointer" class="text-slate-500" /> {{ t('common.new_doc') }}
      </span>
      <input
        class="file-input"
        ref="fileInput"
        type="file"
        @input="onSelectFile"
      >
    </div>
  </div>

</template>

<style scoped>

.file-input {
  display: none
}

.truncate-2-lines {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
}
</style>
