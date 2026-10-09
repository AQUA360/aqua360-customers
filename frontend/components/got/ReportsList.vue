<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue';

const props = defineProps({
  reports: {
    type: Array,
    default: () => []
  },
  expanded: {
    type: Boolean,
    default: false
  }
});

const { $gotApi } = useNuxtApp();

const isExpanded = ref(props.expanded);
const showPreview = ref(false);
const previewUrl = ref(null);
const previewName = ref(null);
const loadingPreview = ref(false);
const documentPreviews = ref(new Map());
const formPhotoPreviews = ref(new Map());

const reversedReports = computed(() => {
  return props.reports.slice().reverse();
});

const formatDate = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleDateString();
};

const isImage = (filename) => {
  if (!filename) return true; // Assume photos are images
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'];
  const ext = filename.split('.').pop().toLowerCase();
  return imageExtensions.includes(ext);
};

// Check if a form field has a valid photo response
const hasPhotoResponse = (field) => {
  return field.type === 'photo' && field.response && field.response_url;
};

// Get non-photo fields from filled_form
const getNonPhotoFields = (filledForm) => {
  if (!filledForm) return [];
  return filledForm.filter(f => f.type !== 'photo');
};

// Get photo fields from filled_form
const getPhotoFields = (filledForm) => {
  if (!filledForm) return [];
  return filledForm.filter(f => f.type === 'photo');
};

const previewDocument = async (doc) => {
  if (!isImage(doc.file.document_name)) return;
  
  previewName.value = doc.file.document_name;
  showPreview.value = true;
  loadingPreview.value = true;
  previewUrl.value = null;

  try {
    const file = await $gotApi.viewDocument(doc.file.id);
    const fileUrl = URL.createObjectURL(file);
    previewUrl.value = fileUrl;
  } catch (error) {
    console.error('Error loading preview:', error);
  } finally {
    loadingPreview.value = false;
  }
};

const closePreview = () => {
  showPreview.value = false;
  if (previewUrl.value && previewUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(previewUrl.value);
  }
  previewUrl.value = null;
  previewName.value = null;
};

const downloadDocument = async (doc) => {
  try {
    const file = await $gotApi.viewDocument(doc.file.id);

    const link = document.createElement('a');
    const fileUrl = URL.createObjectURL(file);
    link.href = fileUrl;
    link.download = doc.file.document_name;
    link.click();

    setTimeout(() => {
      URL.revokeObjectURL(fileUrl);
    }, 250);
  } catch (error) {
    console.error('Error downloading document:', error);
  }
};

// Preview form photo using document ID from response
const previewFormPhoto = async (documentId, fieldName) => {
  if (!documentId) return;

  previewName.value = fieldName;
  showPreview.value = true;
  loadingPreview.value = true;
  previewUrl.value = null;

  try {
    const file = await $gotApi.viewDocument(documentId);
    const fileUrl = URL.createObjectURL(file);
    previewUrl.value = fileUrl;
  } catch (error) {
    console.error('Error loading form photo preview:', error);
  } finally {
    loadingPreview.value = false;
  }
};

// Load form photo previews using the response (document ID)
const loadFormPhotoPreviews = async () => {
  for (const report of props.reports) {
    if (report.filled_form && report.filled_form.length > 0) {
      for (const field of report.filled_form) {
        // field.response is the document ID for photo types
        if (field.type === 'photo' && field.response && !formPhotoPreviews.value.has(field.response)) {
          try {
            const file = await $gotApi.viewDocument(field.response);
            const fileUrl = URL.createObjectURL(file);
            formPhotoPreviews.value.set(field.response, fileUrl);
          } catch (error) {
            console.error('Error loading form photo thumbnail:', error);
          }
        }
      }
    }
  }
};

const loadImagePreviews = async () => {
  for (const report of props.reports) {
    if (report.documents && report.documents.length > 0) {
      for (const doc of report.documents) {
        if (isImage(doc.file.document_name) && !doc.previewUrl) {
          try {
            const file = await $gotApi.viewDocument(doc.file.id);
            const fileUrl = URL.createObjectURL(file);
            doc.previewUrl = fileUrl;
            documentPreviews.value.set(doc.file.id, fileUrl);
          } catch (error) {
            console.error('Error loading thumbnail:', error);
          }
        }
      }
    }
  }
};

// Load image previews when component mounts or reports change
watch(() => props.reports, () => {
  loadImagePreviews();
  loadFormPhotoPreviews();
}, { immediate: true, deep: true });

// Cleanup object URLs on unmount
onBeforeUnmount(() => {
  documentPreviews.value.forEach(url => {
    URL.revokeObjectURL(url);
  });
  documentPreviews.value.clear();
  
  formPhotoPreviews.value.forEach(url => {
    URL.revokeObjectURL(url);
  });
  formPhotoPreviews.value.clear();
});
</script>


<template>
  <div v-if="reports && reports.length > 0">
    <button
      @click="isExpanded = !isExpanded"
      class="w-full px-6 py-4 border-b border-gray-200/60 bg-gray-50/50 flex items-center justify-between hover:bg-gray-50 transition-colors"
    >
      <div class="flex items-center gap-2">
        <Icon name="fa6-solid:file-lines" class="text-gray-600 text-sm" />
        <h2 class="text-base font-semibold text-gray-900">{{ $t('GOT.reports_history') }}</h2>
        <span class="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
          {{ reports.length }}
        </span>
      </div>
      <Icon 
        name="fa6-solid:chevron-down" 
        class="text-gray-400 text-sm transition-transform duration-200"
        :class="{ 'rotate-180': isExpanded }"
      />
    </button>
    
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 max-h-0"
      enter-to-class="opacity-100 max-h-[800px]"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 max-h-[800px]"
      leave-to-class="opacity-0 max-h-0"
    >
      <div v-show="isExpanded" class="overflow-hidden">
        <div class="px-6 py-5 space-y-3 max-h-[700px] overflow-y-auto">
          <details
            v-for="(report, index) in reversedReports" 
            :key="report.id"
            class="group bg-gray-50/70 rounded-lg border border-gray-200/60 overflow-hidden"
          >
            <summary class="px-4 py-3 cursor-pointer list-none flex items-center justify-between hover:bg-gray-100/70 transition-colors">
              <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                  <span class="text-xs font-medium text-blue-600">
                    {{ reports.length - index }}
                  </span>
                </div>
                <div class="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 min-w-0">
                  <div class="flex items-center gap-2">
                    <Icon name="fa6-solid:hashtag" class="text-gray-400 text-xs flex-shrink-0" />
                    <span class="text-xs font-semibold text-gray-700">{{ report.token }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <Icon name="fa6-solid:calendar" class="text-gray-400 text-xs flex-shrink-0" />
                    <span class="text-xs text-gray-500">{{ formatDate(report.report_date) }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <Icon name="fa6-solid:clock" class="text-gray-400 text-xs flex-shrink-0" />
                    <span class="text-xs text-gray-500">{{ report.time_dedicated }} {{ $t('GOT.minutes') }}</span>
                  </div>
                </div>
              </div>
              <Icon 
                name="fa6-solid:chevron-down" 
                class="text-gray-400 text-xs ml-2 flex-shrink-0 transition-transform duration-200 group-open:rotate-180"
              />
            </summary>
            
            <div class="px-4 pb-3 pt-1 space-y-3">
              <!-- Time Range -->
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div class="flex items-center gap-1.5">
                  <Icon name="fa6-solid:play" class="text-green-600 text-xs" />
                  <span class="text-gray-500">{{ $t('GOT.start') }}:</span>
                  <span class="font-medium text-gray-700">{{ report.start_at }}</span>
                </div>
                <div class="flex items-center gap-1.5">
                  <Icon name="fa6-solid:stop" class="text-red-600 text-xs" />
                  <span class="text-gray-500">{{ $t('GOT.end') }}:</span>
                  <span class="font-medium text-gray-700">{{ report.end_at }}</span>
                </div>
              </div>

              <!-- Operator -->
              <div v-if="report.operator_full_name" class="flex items-center gap-1.5 text-xs">
                <Icon name="fa6-solid:user" class="text-blue-500 text-xs" />
                <span class="text-gray-500">{{ $t('GOT.operator') }}:</span>
                <span class="font-medium text-gray-700">{{ report.operator_full_name }}</span>
              </div>

              <!-- Observation -->
              <div v-if="report.observation" class="mt-2">
                <div class="flex items-center gap-1.5 mb-1">
                  <Icon name="fa6-solid:comment" class="text-gray-500 text-xs" />
                  <span class="text-xs font-semibold text-gray-600">{{ $t('GOT.observation') }}:</span>
                </div>
                <p class="text-sm text-gray-700 leading-relaxed pl-5">
                  {{ report.observation }}
                </p>
              </div>

              <!-- Filled Form Fields -->
              <div v-if="report.filled_form && report.filled_form.length > 0" class="mt-3">
                <div class="flex items-center gap-1.5 mb-2">
                  <Icon name="fa6-solid:clipboard-list" class="text-purple-500 text-xs" />
                  <span class="text-xs font-semibold text-gray-600">{{ $t('GOT.form_responses') }}</span>
                </div>
                
                <!-- Text/Numeric Fields Grid -->
                <div v-if="getNonPhotoFields(report.filled_form).length > 0" class="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                  <div
                    v-for="field in getNonPhotoFields(report.filled_form)"
                    :key="field.token"
                    class="bg-white rounded-lg border border-gray-200/60 px-3 py-2.5"
                  >
                    <div class="flex items-center gap-1.5 mb-1">
                      <Icon 
                        :name="field.type === 'numeric' ? 'fa6-solid:hashtag' : 'fa6-solid:font'" 
                        class="text-gray-400 text-xs" 
                      />
                      <span class="text-xs text-gray-500">{{ field.name }}</span>
                      <span v-if="field.required" class="text-red-400 text-xs">*</span>
                    </div>
                    <div class="text-sm font-semibold text-gray-800 pl-4">
                      {{ field.response !== null && field.response !== '' ? field.response : '-' }}
                    </div>
                  </div>
                </div>

                <!-- Photo Fields -->
                <div v-if="getPhotoFields(report.filled_form).length > 0">
                  <div class="flex items-center gap-1.5 mb-2">
                    <Icon name="fa6-solid:images" class="text-blue-500 text-xs" />
                    <span class="text-xs text-gray-500">{{ $t('GOT.form_photos') }}</span>
                  </div>
                  <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div
                      v-for="field in getPhotoFields(report.filled_form)"
                      :key="field.token"
                      class="bg-white rounded-lg border border-gray-200/60 overflow-hidden"
                    >
                      <!-- Photo with response -->
                      <div v-if="field.response" class="relative">
                        <div
                          class="aspect-square bg-gray-100 cursor-pointer overflow-hidden"
                          @click="previewFormPhoto(field.response, field.name)"
                        >
                          <img
                            v-if="formPhotoPreviews.get(field.response)"
                            :src="formPhotoPreviews.get(field.response)"
                            :alt="field.name"
                            class="w-full h-full object-cover hover:scale-105 transition-transform duration-200"
                          />
                          <div v-else class="w-full h-full flex items-center justify-center">
                            <Icon name="fa6-solid:spinner" class="animate-spin text-gray-400 text-lg" />
                          </div>
                        </div>
                        <!-- Zoom icon overlay -->
                        <div class="absolute bottom-2 right-2 w-7 h-7 bg-black/50 rounded-full flex items-center justify-center">
                          <Icon name="fa6-solid:expand" class="text-white text-xs" />
                        </div>
                      </div>
                      <!-- No photo -->
                      <div v-else class="aspect-square bg-gray-50 flex items-center justify-center">
                        <div class="text-center">
                          <Icon name="fa6-solid:image" class="text-gray-300 text-2xl mb-1" />
                          <p class="text-xs text-gray-400">{{ $t('GOT.no_photo') }}</p>
                        </div>
                      </div>
                      <!-- Field name -->
                      <div class="px-2 py-1.5 bg-gray-50 border-t border-gray-200/60">
                        <p class="text-xs text-gray-600 truncate font-medium" :title="field.name">
                          {{ field.name }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Documents -->
              <div v-if="report.documents && report.documents.length > 0" class="mt-3">
                <div class="flex items-center gap-1.5 mb-2">
                  <Icon name="fa6-solid:paperclip" class="text-gray-500 text-xs" />
                  <span class="text-xs font-semibold text-gray-600">{{ $t('GOT.documents') }} ({{ report.active_documents }})</span>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2 pl-5">
                  <div
                    v-for="doc in report.documents"
                    :key="doc.id"
                    class="relative group bg-white rounded-lg border border-gray-200/60 overflow-hidden hover:shadow-sm transition-all duration-150"
                  >
                    <!-- Image Preview -->
                    <div
                      v-if="isImage(doc.file.document_name)"
                      class="aspect-square bg-gray-100 flex items-center justify-center cursor-pointer overflow-hidden relative"
                      @click="previewDocument(doc)"
                    >
                      <img
                        v-if="doc.previewUrl"
                        :src="doc.previewUrl"
                        :alt="doc.file.document_name"
                        class="w-full h-full object-cover"
                      />
                      <Icon v-else name="fa6-solid:spinner" class="animate-spin text-gray-400 text-xl" />
                    </div>
                    <!-- File Icon -->
                    <div
                      v-else
                      class="aspect-square bg-gray-100 flex items-center justify-center"
                    >
                      <Icon name="fa6-solid:file" class="text-gray-400 text-2xl" />
                    </div>

                    <!-- File Name & Actions -->
                    <div class="p-2 bg-white border-t border-gray-200/60">
                      <p class="text-xs text-gray-700 truncate mb-1" :title="doc.file.document_name">
                        {{ doc.file.document_name }}
                      </p>
                      <div class="flex items-center gap-1">
                        <!-- Preview Button (images only) -->
                        <button
                          v-if="isImage(doc.file.document_name)"
                          @click="previewDocument(doc)"
                          class="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded transition-colors"
                          :title="$t('GOT.preview')"
                        >
                          <Icon name="fa6-solid:eye" class="text-xs" />
                        </button>
                        <!-- Download Button -->
                        <button
                          @click="downloadDocument(doc)"
                          class="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded transition-colors"
                          :title="$t('GOT.download')"
                        >
                          <Icon name="fa6-solid:download" class="text-xs" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </details>
        </div>
      </div>
    </Transition>

    <!-- Image Preview Modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-opacity duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="showPreview"
          class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
          @click="closePreview"
        >
          <div class="relative max-w-4xl max-h-[90vh] w-full" @click.stop>
            <!-- Close Button -->
            <button
              @click="closePreview"
              class="absolute -top-12 right-0 w-10 h-10 flex items-center justify-center bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors"
            >
              <Icon name="fa6-solid:xmark" class="text-xl" />
            </button>
            
            <!-- Image -->
            <div class="bg-white rounded-lg overflow-hidden shadow-2xl">
              <div v-if="loadingPreview" class="aspect-video flex items-center justify-center">
                <Icon name="fa6-solid:spinner" class="animate-spin text-3xl text-gray-300" />
              </div>
              <img
                v-else-if="previewUrl"
                :src="previewUrl"
                :alt="previewName"
                class="w-full h-auto max-h-[80vh] object-contain"
              />
            </div>

            <!-- File Info -->
            <div v-if="previewName" class="mt-3 bg-white/10 backdrop-blur-sm rounded-lg px-4 py-2">
              <p class="text-sm text-white font-medium">{{ previewName }}</p>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>


