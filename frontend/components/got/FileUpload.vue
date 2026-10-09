<script setup>
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
const { t } = useI18n();


const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  label: {
    type: String,
    default: ''
  },
  required: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  helperText: {
    type: String,
    default: ''
  },
  accept: {
    type: String,
    default: '*'
  },
  multiple: {
    type: Boolean,
    default: true
  },
  maxFiles: {
    type: Number,
    default: null
  },
  maxFileSize: {
    type: Number,
    default: 10 * 1024 * 1024 // 10MB default
  },
  showCamera: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['update:modelValue', 'file-added', 'file-removed', 'retry-file']);

const cameraInput = ref(null);
const fileInput = ref(null);
const files = ref([]);
const errorMessage = ref('');

// Check if device has camera (mobile detection)
const hasCamera = computed(() => {
  return 'mediaDevices' in navigator && 'getUserMedia' in navigator.mediaDevices;
});

const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files || []);
  errorMessage.value = '';

  // Check max files limit
  if (props.maxFiles && files.value.length + selectedFiles.length > props.maxFiles) {
    errorMessage.value = `Maximum ${props.maxFiles} files allowed`;
    event.target.value = ''; // Reset input
    return;
  }

  selectedFiles.forEach(file => {
    // Validate file size
    if (file.size > props.maxFileSize) {
      errorMessage.value = `File ${file.name} exceeds ${formatFileSize(props.maxFileSize)} limit`;
      return;
    }

    // Validate file type
    if (props.accept !== '*' && !file.type.match(new RegExp(props.accept.replace('*', '.*')))) {
      errorMessage.value = `File ${file.name} is not an accepted type`;
      return;
    }

    const fileObj = {
      id: `${Date.now()}-${Math.random()}`,
      file: file,
      preview: null,
      uploading: false,
      uploaded: false,
      error: null
    };

    // Add to files list
    files.value.push(fileObj);

    // Create preview for images
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const index = files.value.findIndex(f => f.id === fileObj.id);
        if (index !== -1) {
          files.value[index].preview = e.target.result;
        }
      };
      reader.readAsDataURL(file);
    }

    
    emit('file-added', fileObj);
  });

  // Update model value
  updateModelValue();

  // Reset input
  event.target.value = '';
};

const removeFile = (index) => {
  const removedFile = files.value[index];
  files.value.splice(index, 1);
  updateModelValue();
  emit('file-removed', removedFile);
};

const retryFile = (file) => {
  // Reset error state
  file.error = null;
  file.uploaded = false;
  // Emit retry event so parent can handle the retry logic
  emit('retry-file', file);
};

const updateModelValue = () => {
  emit('update:modelValue', files.value);
};

// Format file size
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

// Public method to mark file as uploading
const markFileUploading = (fileId, uploading = true) => {
  const file = files.value.find(f => f.id === fileId);
  if (file) {
    file.uploading = uploading;
  }
};

// Public method to mark file as uploaded
const markFileUploaded = (fileId, uploaded = true, error = null) => {
  const file = files.value.find(f => f.id === fileId);
  if (file) {
    file.uploading = false;
    file.uploaded = uploaded;
    file.error = error;
  }
};

// Public method to validate
const validate = () => {
  if (props.required && files.value.length === 0) {
    errorMessage.value = 'At least one file is required';
    return false;
  }
  errorMessage.value = '';
  return true;
};

// Expose methods
defineExpose({
  validate,
  markFileUploading,
  markFileUploaded,
  clearFiles: () => {
    files.value = [];
    updateModelValue();
  }
});

// Watch for external changes
watch(() => props.modelValue, (newVal) => {
  if (newVal !== files.value) {
    files.value = newVal;
  }
});
</script>

<template>
  <div class="space-y-3">
    <label v-if="label" class="block text-sm font-medium text-gray-700">
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>

    <!-- Upload Buttons -->
    <div class="flex flex-wrap gap-2">
      <!-- Camera Button (Mobile Only) -->
      <label
        v-if="showCamera"
        class="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-50 text-blue-700 border border-blue-200/60 rounded-lg hover:bg-blue-100 transition-all duration-150 cursor-pointer text-sm font-medium"
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
          :disabled="disabled || (maxFiles && files.length >= maxFiles)"
        />
      </label>

      <!-- Gallery/File Button -->
      <label
        class="inline-flex items-center gap-2 px-4 py-2.5 bg-white text-gray-700 border border-gray-200/60 rounded-lg hover:bg-gray-50 transition-all duration-150 cursor-pointer text-sm font-medium"
        :class="{ 'opacity-50 cursor-not-allowed': disabled || (maxFiles && files.length >= maxFiles) }"
      >
        <Icon name="fa6-solid:image" class="text-base" />
        <span>{{ $t('GOT.choose_file') }}</span>
        <input
          ref="fileInput"
          type="file"
          :accept="accept"
          :multiple="multiple"
          @change="handleFileSelect"
          class="hidden"
          :disabled="disabled || (maxFiles && files.length >= maxFiles)"
        />
      </label>
    </div>

    <!-- Helper Text -->
    <p v-if="helperText" class="text-xs text-gray-500">
      {{ helperText }}
    </p>

    <!-- Error Message -->
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-100 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-1"
    >
      <p v-if="errorMessage" class="text-sm text-red-600 flex items-center gap-1.5">
        <Icon name="fa6-solid:circle-exclamation" class="text-xs" />
        {{ errorMessage }}
      </p>
    </Transition>

    <!-- File Previews -->
    <TransitionGroup
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
      class="space-y-2"
      tag="div"
    >
      <div
        v-for="(file, index) in files"
        :key="file.id"
        class="flex items-center gap-3 p-3 bg-gray-50 border border-gray-200/60 rounded-lg group hover:bg-gray-100 transition-all duration-150"
      >
        <!-- Image Preview -->
        <div class="relative w-12 h-12 flex-shrink-0 rounded-lg overflow-hidden bg-gray-200">
          <img
            v-if="file.preview"
            :src="file.preview"
            :alt="file.file.name"
            class="w-full h-full object-cover"
          />
          <div v-else class="w-full h-full flex items-center justify-center">
            <Icon name="fa6-solid:file" class="text-gray-400 text-lg" />
          </div>
          
          <!-- Loading Overlay -->
          <div
            v-if="file.uploading"
            class="absolute inset-0 bg-black/50 flex items-center justify-center"
          >
            <Icon name="fa6-solid:spinner" class="text-white text-sm animate-spin" />
          </div>
          
          <!-- Success Check -->
          <div
            v-if="file.uploaded"
            class="absolute inset-0 bg-green-500/80 flex items-center justify-center"
          >
            <Icon name="fa6-solid:check" class="text-white text-sm" />
          </div>
        </div>

        <!-- File Info -->
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-900 truncate">
            {{ file.file.name }}
          </p>
          <p class="text-xs text-gray-500">
            {{ formatFileSize(file.file.size) }}
            <span v-if="file.uploading" class="text-blue-600">• Uploading...</span>
            <span v-else-if="file.uploaded" class="text-green-600">• Uploaded</span>
            <span v-else-if="file.error" class="text-red-600">• {{ file.error }}</span>
          </p>
        </div>

        <!-- Retry Button (only show for failed uploads) -->
        <button
          v-if="file.error && !file.uploading"
          @click="retryFile(file)"
          type="button"
          class="p-2 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-all duration-150"
          :disabled="disabled"
          title="Retry upload"
        >
          <Icon name="fa6-solid:rotate-right" class="text-sm" />
        </button>

        <!-- Remove Button -->
        <button
          v-if="!file.uploading"
          @click="removeFile(index)"
          type="button"
          class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all duration-150"
          :disabled="disabled"
        >
          <Icon name="fa6-solid:xmark" class="text-sm" />
        </button>
      </div>
    </TransitionGroup>

    <!-- Max Files Warning -->
    <p v-if="maxFiles && files.length >= maxFiles" class="text-xs text-orange-600">
      Maximum {{ maxFiles }} files allowed
    </p>
  </div>
</template>

