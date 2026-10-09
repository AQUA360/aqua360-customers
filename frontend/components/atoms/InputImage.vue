<script setup>
import { ref } from 'vue'

const props = defineProps({
  uploaded: String,
  parentId: Number,
  width: {
    type: String,
    default: '100%' // w-48 is 12rem
  },
  height: {
    type: String,
    default: '12rem' // w-48 is 12rem
  }
});


const { t } = useI18n();
const imageData = ref(props.uploaded || null)
const fileInput = ref(null)
const emit = defineEmits(['update', 'delete']);

const chooseImage = () => {
  fileInput.value.click()
}
const deleteImage = ($event) => {
  $event.stopPropagation()
  imageData.value = null;
  resetInput();

  emit('delete');
}

// Buidem el valor de l'input perquè tornar a escollir el mateix fitxer
// (per exemple després d'esborrar-lo) torni a disparar l'event `change`.
const resetInput = () => {
  if (fileInput.value) {
    fileInput.value.value = '';
  }
}

const onSelectFile = () => {
  const input = fileInput.value
  const files = input.files
  if (files && files[0]) {
    const file = files[0]
    const reader = new FileReader()
    reader.onload = e => {
      imageData.value = e.target.result
    }
    reader.readAsDataURL(file)

    emit('update', file)
  }
  resetInput();
}

watch(() => props.uploaded, (newVal) => {
  imageData.value = newVal;
});
watch(() => props.parentId, (newVal) => {
  imageData.value = null;
  resetInput();
});

</script>

<template>
  <div class="block rounded-md relative group w-60 cursor-pointer bg-cover bg-center mt-3 border"
    :style="{ 'background-image': imageData ? `url(${imageData})` : 'none', 'width': props.width, 'height': props.height }"
    @click="chooseImage" >
    <span
      v-if="!imageData"
      class="flex w-full h-full justify-center items-center bg-slate-100 hover:bg-slate-200 text-slate-400 text-lg rounded-md transition-all duration-200">
      {{t('common.select_img')}}
    </span>
    <span
      v-if="imageData"
      class="opacity-0 flex w-full h-full justify-center items-center bg-white text-black text-lg rounded-md transition-all duration-200 hover:opacity-75">
      {{t('common.change_img')}}
    </span>
    <input
      class="file-input"
      accept="image/png, image/gif, image/jpeg"
      ref="fileInput"
      type="file"
      @click.stop
      @change="onSelectFile"
    >
    <button
      v-if="imageData"
      type="button"
      class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
      @click="deleteImage">
      <Icon name="fa6-solid:trash" />
    </button>
  </div>
</template>

<style scoped>
.placeholder:hover {
  background: #E0E0E0
}

.file-input {
  display: none
}
</style>
