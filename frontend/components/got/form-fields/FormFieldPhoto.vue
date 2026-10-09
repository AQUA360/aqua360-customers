<script setup>
/**
 * Photo Field Component for Dynamic Forms
 * Handles 'photo' type fields with camera/gallery upload
 */
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
  field: {
    type: Object,
    required: true
  },
  modelValue: {
    type: Object,
    default: null
  },
  error: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  uploading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue', 'upload', 'remove']);

const { t } = useI18n();
const cameraInput = ref(null);
const fileInput = ref(null);
const previewUrl = ref(null);
const localError = ref('');
const localFile = ref(null); // Keep local file reference for preview

// Generate preview URL for selected file
watch(() => props.modelValue, (newVal) => {
  if (newVal?.file) {
    // Keep the file reference and create preview
    if (localFile.value !== newVal.file) {
      localFile.value = newVal.file;
      const reader = new FileReader();
      reader.onload = (e) => {
        previewUrl.value = e.target.result;
      };
      reader.readAsDataURL(newVal.file);
    }
  } else if (newVal?.url) {
    // Use server URL
    previewUrl.value = newVal.url;
    localFile.value = null;
  } else if (!newVal) {
    // Cleared
    previewUrl.value = null;
    localFile.value = null;
  }
}, { immediate: true, deep: true });

const handleFileSelect = (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  localError.value = '';

  // Validate file type
  if (!file.type.startsWith('image/')) {
    localError.value = t('GOT.form_field_photo_invalid_type');
    event.target.value = '';
    return;
  }

  // Validate file size (max 50MB)
  const maxSize = 50 * 1024 * 1024;
  if (file.size > maxSize) {
    localError.value = t('GOT.form_field_photo_too_large');
    event.target.value = '';
    return;
  }

  // Create preview immediately
  localFile.value = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    previewUrl.value = e.target.result;
  };
  reader.readAsDataURL(file);

  // Store file locally (don't upload yet - will be uploaded on form submit)
  emit('update:modelValue', { file, uploaded: false });

  // Reset input
  event.target.value = '';
};

const removePhoto = () => {
  // Just clear local state (photos are not uploaded until form submit)
  previewUrl.value = null;
  localFile.value = null;
  emit('update:modelValue', null);
};

const displayError = computed(() => props.error || localError.value);

const isUploaded = computed(() => props.modelValue?.uploaded === true);
</script>

<template>
  <div class="space-y-3">
    <label class="block text-sm font-medium text-gray-700">
      {{ field.name }}
      <span v-if="field.required" class="text-red-500">*</span>
    </label>

    <!-- Photo Preview or Upload Buttons -->
    <div v-if="previewUrl" class="relative">
      <!-- Preview Image -->
      <div class="relative rounded-lg overflow-hidden border border-gray-200/60 bg-gray-100">
        <img 
          :src="previewUrl" 
          :alt="field.name"
          class="w-full h-48 object-cover"
        />
        
        <!-- Upload Status Overlay -->
        <div 
          v-if="uploading"
          class="absolute inset-0 bg-black/50 flex items-center justify-center"
        >
          <div class="text-center text-white">
            <Icon name="fa6-solid:spinner" class="animate-spin text-2xl mb-2" />
            <p class="text-sm">{{ $t('GOT.form_field_photo_uploading') }}</p>
          </div>
        </div>

        <!-- Ready Badge (photo selected but not yet uploaded) -->
        <div 
          v-else-if="modelValue?.file && !isUploaded"
          class="absolute top-2 right-2 px-2 py-1 bg-blue-500 text-white text-xs font-medium rounded-full flex items-center gap-1"
        >
          <Icon name="fa6-solid:check" class="text-xs" />
          {{ $t('GOT.form_field_photo_ready') }}
        </div>

        <!-- Uploaded Success Badge -->
        <div 
          v-else-if="isUploaded"
          class="absolute top-2 right-2 px-2 py-1 bg-green-500 text-white text-xs font-medium rounded-full flex items-center gap-1"
        >
          <Icon name="fa6-solid:cloud-arrow-up" class="text-xs" />
          {{ $t('GOT.form_field_photo_uploaded') }}
        </div>

        <!-- Remove Button -->
        <button
          v-if="!uploading && !disabled"
          type="button"
          @click="removePhoto"
          class="absolute top-2 left-2 p-2 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors shadow-lg"
        >
          <Icon name="fa6-solid:trash" class="text-sm" />
        </button>
      </div>
    </div>

    <!-- Upload Buttons (when no photo) -->
    <div v-else class="flex flex-wrap gap-2">
      <!-- Camera Button -->
      <label
        class="inline-flex items-center gap-2 px-4 py-3 bg-blue-50 text-blue-700 border border-blue-200/60 rounded-lg hover:bg-blue-100 transition-all duration-150 cursor-pointer text-sm font-medium flex-1 justify-center"
        :class="{ 'opacity-50 cursor-not-allowed': disabled }"
      >
        <Icon name="fa6-solid:camera" class="text-base" />
        <span>{{ $t('GOT.take_photo') }}</span>
        <input
          ref="cameraInput"
          type="file"
          accept="image/*"
          capture="environment"
          @change="handleFileSelect"
          class="hidden"
          :disabled="disabled"
        />
      </label>

      <!-- Gallery Button -->
      <label
        class="inline-flex items-center gap-2 px-4 py-3 bg-white text-gray-700 border border-gray-200/60 rounded-lg hover:bg-gray-50 transition-all duration-150 cursor-pointer text-sm font-medium flex-1 justify-center"
        :class="{ 'opacity-50 cursor-not-allowed': disabled }"
      >
        <Icon name="fa6-solid:image" class="text-base" />
        <span>{{ $t('GOT.choose_file') }}</span>
        <input
          ref="fileInput"
          type="file"
          accept="image/*"
          @change="handleFileSelect"
          class="hidden"
          :disabled="disabled"
        />
      </label>
    </div>

    <!-- Error Message -->
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-1"
    >
      <p v-if="displayError" class="text-sm text-red-600 flex items-center gap-1.5">
        <Icon name="fa6-solid:circle-exclamation" class="text-xs" />
        {{ displayError }}
      </p>
    </Transition>
  </div>
</template>
