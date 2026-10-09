<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

definePageMeta({
  layout: 'got'
});

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const toast = useToast();
const { $gotApi } = useNuxtApp();


// Loading states
const loading = ref(true);
const submitting = ref(false);
const uploadingFiles = ref(false);

// Order data
const order = ref(null);

// Dynamic form data
const hasForm = ref(false);
const formData = ref(null);
const dynamicFormRef = ref(null);

// Base form fields
const startTime = ref('');
const endTime = ref('');
const observation = ref('');

// Legacy file upload (only used when no dynamic form)
const files = ref([]);
const fileUploadRef = ref(null);

// Report creation state
const reportCreated = ref(false);
const reportId = ref(null);

// Form errors
const formErrors = ref({
  startTime: '',
  endTime: '',
  observation: ''
});

// Computed


// Calculate duration
const duration = computed(() => {
  if (!startTime.value || !endTime.value) return '';
  
  const [startH, startM] = startTime.value.split(':').map(Number);
  const [endH, endM] = endTime.value.split(':').map(Number);
  
  const startMinutes = startH * 60 + startM;
  const endMinutes = endH * 60 + endM;
  const diff = endMinutes - startMinutes;
  
  if (diff < 0) return '';
  
  const hours = Math.floor(diff / 60);
  const minutes = diff % 60;
  
  if (hours === 0) return `${minutes}min`;
  if (minutes === 0) return `${hours}h`;
  return `${hours}h ${minutes}min`;
});

// Check if any upload is in progress
const isUploading = computed(() => {
  if (hasForm.value) {
    return dynamicFormRef.value?.isAnyUploading ?? false;
  }
  return uploadingFiles.value;
});

// Check if submit button should be disabled
const isSubmitDisabled = computed(() => {
  return submitting.value || isUploading.value;
});

// Data Fetching

const fetchOrder = async () => {
  try {
    const response = await $gotApi.getOrderDetail(route.params.id);
    if (response.success) {
      order.value = response.order;
    } else {
      toast.error(t('common.error_load'));
      router.push('/got/orders');
    }
  } catch (error) {
    console.error('Error loading order:', error);
    toast.error(t('common.error_load'));
    router.push('/got/orders');
  }
};

const fetchOrderForm = async () => {
  try {
    const response = await $gotApi.getOrderForm(route.params.id);
    if (response.success) {
      hasForm.value = response.has_form;
      formData.value = response.form;
    }
  } catch (error) {
    console.error('Error loading order form:', error);
    // Fallback to legacy mode if form fetch fails
    hasForm.value = false;
    formData.value = null;
  }
};

const loadData = async () => {
  loading.value = true;
  try {
    await Promise.all([fetchOrder(), fetchOrderForm()]);
  } finally {
    loading.value = false;
  }
};

// Validation

const validateBaseForm = () => {
  let isValid = true;
  formErrors.value = {
    startTime: '',
    endTime: '',
    observation: ''
  };

  // Times are optional, but if one is filled, both are required
  const hasStartTime = !!startTime.value;
  const hasEndTime = !!endTime.value;

  if (hasStartTime && !hasEndTime) {
    formErrors.value.endTime = t('GOT.end_time_required_if_start');
    isValid = false;
  }

  if (hasEndTime && !hasStartTime) {
    formErrors.value.startTime = t('GOT.start_time_required_if_end');
    isValid = false;
  }

  // Validate time range only if both are filled
  if (hasStartTime && hasEndTime && startTime.value >= endTime.value) {
    formErrors.value.endTime = t('GOT.end_time_must_be_after_start');
    isValid = false;
  }

  // Validate observation (only required when no dynamic form)
  if (!hasForm.value && !observation.value.trim()) {
    formErrors.value.observation = t('GOT.observation_required');
    isValid = false;
  }

  return isValid;
};

// Form Submission

const handleSubmit = async () => {
  // Validate base form
  if (!validateBaseForm()) {
    return;
  }

  // Validate dynamic form if present
  if (hasForm.value && dynamicFormRef.value) {
    const isDynamicFormValid = dynamicFormRef.value.validate();
    if (!isDynamicFormValid) {
      toast.error(t('GOT.form_validation_error'));
      return;
    }
  }

  submitting.value = true;

  try {
    if (hasForm.value) {
      await submitWithDynamicForm();
    } else {
      await submitWithLegacyUpload();
    }
  } catch (error) {
    console.error('Error submitting report:', error);
    toast.error(t('common.error_save'));
    submitting.value = false;
  }
};

// Submit with dynamic form (upload photos first, then create report)
const submitWithDynamicForm = async () => {
  // Step 1: Upload all photos
  const uploadResult = await dynamicFormRef.value?.uploadAllPhotos();
  
  if (!uploadResult?.success) {
    toast.error(t('GOT.photo_upload_failed'));
    
    // Delete any photos that were uploaded before the failure
    if (uploadResult?.uploadedIds?.length > 0) {
      await dynamicFormRef.value?.deleteUploadedPhotos(uploadResult.uploadedIds);
    }
    
    submitting.value = false;
    return;
  }
  
  // Step 2: Get filled form data (now with document_ids)
  const filledForm = dynamicFormRef.value?.getFilledForm() || [];
  
  const reportData = {
    start_at: startTime.value,
    end_at: endTime.value,
    observation: observation.value || '',
    filled_form: filledForm
  };

  // Step 3: Create report
  const reportResponse = await $gotApi.addReport(route.params.id, reportData);

  if (reportResponse.success) {
    toast.success(t('GOT.report_created'));
    setTimeout(() => {
      router.push(`/got/orders/${route.params.id}`);
    }, 1000);
  } else {
    toast.error(t('common.error_save'));
    
    // Delete uploaded photos since report creation failed
    if (uploadResult?.uploadedIds?.length > 0) {
      await dynamicFormRef.value?.deleteUploadedPhotos(uploadResult.uploadedIds);
      toast.info(t('GOT.photos_cleaned_up'));
    }
    
    submitting.value = false;
  }
};

// Submit with legacy file upload (no dynamic form)
const submitWithLegacyUpload = async () => {
  // Step 1: Create report (only if not already created)
  if (!reportCreated.value) {
    const reportResponse = await $gotApi.addReport(route.params.id, {
      start_at: startTime.value,
      end_at: endTime.value,
      observation: observation.value
    });

    if (!reportResponse.success) {
      toast.error(t('common.error_save'));
      submitting.value = false;
      return;
    }

    reportId.value = reportResponse.report.id;
    reportCreated.value = true;
    toast.success(t('GOT.report_created'));
  }

  // Step 2: Upload files if any
  if (files.value.length > 0) {
    uploadingFiles.value = true;
    let uploadedCount = 0;
    let failedCount = 0;

    for (const fileObj of files.value) {
      // Skip already uploaded files
      if (fileObj.uploaded) {
        uploadedCount++;
        continue;
      }

      try {
        fileUploadRef.value?.markFileUploading(fileObj.id, true);

        const uploadResponse = await $gotApi.addReportDocument(
          route.params.id,
          reportId.value,
          fileObj.file
        );

        if (uploadResponse.success) {
          fileUploadRef.value?.markFileUploaded(fileObj.id, true);
          uploadedCount++;
        } else {
          fileUploadRef.value?.markFileUploaded(fileObj.id, false, t('GOT.upload_failed'));
          failedCount++;
        }
      } catch (error) {
        console.error('Error uploading file:', error);
        fileUploadRef.value?.markFileUploaded(fileObj.id, false, t('GOT.upload_error'));
        failedCount++;
      }
    }

    uploadingFiles.value = false;

    // Handle results
    if (failedCount === 0) {
      toast.success(t('GOT.all_files_uploaded', { count: uploadedCount }));
      setTimeout(() => {
        router.push(`/got/orders/${route.params.id}`);
      }, 1000);
    } else if (uploadedCount > 0) {
      toast.warning(t('GOT.some_files_failed', { uploaded: uploadedCount, failed: failedCount }));
      submitting.value = false;
    } else {
      toast.error(t('GOT.all_files_failed'));
      submitting.value = false;
    }
  } else {
    // No files to upload, navigate back
    setTimeout(() => {
      router.push(`/got/orders/${route.params.id}`);
    }, 1000);
  }
};

// Legacy File Upload Handlers


const handleRetryFile = async (fileObj) => {
  if (!reportId.value) {
    toast.error(t('GOT.report_not_created_yet'));
    return;
  }

  try {
    fileUploadRef.value?.markFileUploading(fileObj.id, true);

    const uploadResponse = await $gotApi.addReportDocument(
      route.params.id,
      reportId.value,
      fileObj.file
    );

    if (uploadResponse.success) {
      fileUploadRef.value?.markFileUploaded(fileObj.id, true);
      toast.success(t('GOT.file_uploaded_success'));
    } else {
      fileUploadRef.value?.markFileUploaded(fileObj.id, false, t('GOT.upload_failed'));
      toast.error(t('GOT.upload_failed'));
    }
  } catch (error) {
    console.error('Error retrying file upload:', error);
    fileUploadRef.value?.markFileUploaded(fileObj.id, false, t('GOT.upload_error'));
    toast.error(t('GOT.upload_error'));
  }
};

// Lifecycle

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="space-y-6 pb-24">
    <!-- Back Button & Header -->
    <div class="space-y-4">
      <button
        @click="router.push(`/got/orders/${route.params.id}`)"
        class="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-all duration-150"
      >
        <Icon name="fa6-solid:arrow-left" class="text-sm" />
        {{ $t('GOT.back_to_order') }}
      </button>
      
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-black flex items-center justify-center flex-shrink-0">
          <Icon name="fa6-solid:file-circle-plus" class="text-white text-lg" />
        </div>
        <div>
          <h1 class="text-3xl font-bold text-gray-900">
            {{ $t('GOT.create_report') }}
          </h1>
          <p v-if="order" class="text-sm text-gray-500 mt-0.5">
            {{ $t('GOT.order') }} #{{ order.token }}
          </p>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <Icon name="fa6-solid:spinner" class="animate-spin text-3xl text-gray-300" />
    </div>

    <!-- Form -->
    <form v-else @submit.prevent="handleSubmit" class="space-y-6">
      <!-- Time Section -->
      <div class="bg-white rounded-lg border border-gray-200/60 overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-200/60 bg-gray-50/50">
          <div class="flex items-center gap-2">
            <Icon name="fa6-solid:clock" class="text-gray-600 text-sm" />
            <h2 class="text-base font-semibold text-gray-900">{{ $t('GOT.work_time') }}</h2>
            <span class="text-xs text-gray-400">({{ $t('common.optional') }})</span>
          </div>
        </div>
        
        <div class="px-4 py-4 space-y-3">
          <!-- Start Time -->
          <GotTimePicker
            v-model="startTime"
            :label="$t('GOT.start_time')"
            :error="formErrors.startTime"
            :max-time="endTime"
          />

          <!-- End Time -->
          <GotTimePicker
            v-model="endTime"
            :label="$t('GOT.end_time')"
            :error="formErrors.endTime"
            :min-time="startTime"
          />

          <!-- Duration Display -->
          <div v-if="duration" class="flex items-center gap-2 px-3 py-2 bg-blue-50 rounded-lg ml-[92px]">
            <Icon name="fa6-solid:hourglass-half" class="text-blue-600 text-sm" />
            <span class="text-sm font-medium text-blue-900">
              {{ $t('GOT.duration') }}: {{ duration }}
            </span>
          </div>
        </div>
      </div>

      <!-- Observation Section  -->
      <div class="bg-white rounded-lg border border-gray-200/60 overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-200/60 bg-gray-50/50">
          <div class="flex items-center gap-2">
            <Icon name="fa6-solid:pen-to-square" class="text-gray-600 text-sm" />
            <h2 class="text-base font-semibold text-gray-900">{{ $t('GOT.observation') }}</h2>
          </div>
        </div>
        
        <div class="px-4 py-4">
          <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">
              {{ $t('GOT.work_description') }}
              <span v-if="!hasForm" class="text-red-500">*</span>
              <span v-else class="text-gray-400 text-xs ml-1">({{ $t('common.optional') }})</span>
            </label>
            <textarea
              v-model="observation"
              :placeholder="$t('GOT.describe_work_performed')"
              rows="4"
              class="w-full px-3 py-2.5 border rounded-lg text-base resize-none transition-all duration-150"
              :class="formErrors.observation 
                ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' 
                : 'border-gray-200/60 focus:border-blue-500 focus:ring-blue-500/20'"
            ></textarea>
            <Transition
              enter-active-class="transition-all duration-150 ease-out"
              enter-from-class="opacity-0 -translate-y-1"
              enter-to-class="opacity-100 translate-y-0"
              leave-active-class="transition-all duration-100 ease-in"
              leave-from-class="opacity-100 translate-y-0"
              leave-to-class="opacity-0 -translate-y-1"
            >
              <p v-if="formErrors.observation" class="text-sm text-red-600 flex items-center gap-1.5">
                <Icon name="fa6-solid:circle-exclamation" class="text-xs" />
                {{ formErrors.observation }}
              </p>
            </Transition>
            <p v-if="!formErrors.observation" class="text-xs text-gray-500">
              {{ $t('GOT.observation_helper') }}
            </p>
          </div>
        </div>
      </div>

      <!-- Dynamic Form Section (if order has a form) -->
      <div v-if="hasForm && formData" class="bg-white rounded-lg border border-gray-200/60 overflow-hidden">
        <div class="px-4 py-4">
          <GotDynamicForm
            ref="dynamicFormRef"
            :form="formData"
            :order-id="route.params.id"
            :disabled="submitting"
          />
        </div>
      </div>

      <!-- Legacy Documents Section  -->
      <div v-else class="bg-white rounded-lg border border-gray-200/60 overflow-hidden">
        <div class="px-4 py-3 border-b border-gray-200/60 bg-gray-50/50">
          <div class="flex items-center gap-2">
            <Icon name="fa6-solid:images" class="text-gray-600 text-sm" />
            <h2 class="text-base font-semibold text-gray-900">{{ $t('GOT.documents') }}</h2>
          </div>
        </div>
        
        <div class="px-4 py-4">
          <GotFileUpload
            ref="fileUploadRef"
            v-model="files"
            :label="$t('GOT.attach_photos')"
            :helper-text="$t('GOT.photos_helper')"
            accept="*"
            :max-files="4"
            :max-file-size="100 * 1024 * 1024"
            :show-camera="true"
            multiple
            @retry-file="handleRetryFile"
          />
        </div>
      </div>

      <!-- Submit Button -->
      <div class="fixed bottom-0 left-0 right-0 lg:relative lg:bottom-auto lg:left-auto lg:right-auto bg-white border-t border-gray-200/60 lg:border-0 lg:bg-transparent p-4 pb-5 lg:p-0 z-40">
        <div class="max-w-7xl mx-auto lg:pl-60">
          <button
            type="submit"
            :disabled="isSubmitDisabled"
            class="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed font-semibold text-base shadow-lg hover:shadow-xl active:scale-98 transition-all duration-150"
          >
            <Icon 
              :name="isSubmitDisabled ? 'fa6-solid:spinner' : (reportCreated ? 'fa6-solid:rotate-right' : 'fa6-solid:paper-plane')" 
              class="text-lg"
              :class="{ 'animate-spin': isSubmitDisabled }"
            />
            <span v-if="!isSubmitDisabled && !reportCreated">{{ $t('GOT.submit_report') }}</span>
            <span v-else-if="!isSubmitDisabled && reportCreated">{{ $t('GOT.retry_upload') }}</span>
            <span v-else>{{ $t('GOT.submitting') }}</span>
          </button>
        </div>
      </div>
    </form>
  </div>
</template>

<style scoped>
.active\:scale-98:active {
  transform: scale(0.98);
}
</style>
