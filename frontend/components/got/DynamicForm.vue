<script setup>
/**
 * Dynamic Form Component
 * Renders form fields based on the form structure from the API
 */
import { ref, computed, watch, defineAsyncComponent } from 'vue';
import { useI18n } from 'vue-i18n';

// Explicitly import field components for dynamic usage
import FormFieldText from '~/components/got/form-fields/FormFieldText.vue';
import FormFieldNumeric from '~/components/got/form-fields/FormFieldNumeric.vue';
import FormFieldPhoto from '~/components/got/form-fields/FormFieldPhoto.vue';

const props = defineProps({
  form: {
    type: Object,
    required: true
  },
  orderId: {
    type: [String, Number],
    required: true
  },
  disabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:values', 'validation-change']);

const { t } = useI18n();
const { $gotApi } = useNuxtApp();

// Store form values: { [token]: value }
const formValues = ref({});

// Store field errors: { [token]: errorMessage }
const fieldErrors = ref({});

// Store upload states: { [token]: boolean }
const uploadingFields = ref({});

// Field type to component mapping (extensible for future types)
const FIELD_COMPONENTS = {
  text: FormFieldText,
  numeric: FormFieldNumeric,
  photo: FormFieldPhoto
};

// Get component for a field type
const getFieldComponent = (type) => {
  return FIELD_COMPONENTS[type] || null;
};

// Check if field type is supported
const isFieldSupported = (type) => {
  return type in FIELD_COMPONENTS;
};

// Initialize form values
const initializeFormValues = () => {
  if (!props.form?.structure) return;
  
  const values = {};
  props.form.structure.forEach(field => {
    values[field.token] = null;
  });
  formValues.value = values;
};

// Handle field value update
const updateFieldValue = (token, value) => {
  formValues.value[token] = value;
  
  // Clear error when value changes
  if (fieldErrors.value[token]) {
    fieldErrors.value[token] = '';
  }
  
  emit('update:values', formValues.value);
};

// Upload all photos to server (called on form submit)
const uploadAllPhotos = async () => {
  if (!props.form?.structure) return { success: true, uploadedIds: [] };
  
  const photoFields = props.form.structure.filter(f => f.type === 'photo');
  const uploadedIds = [];
  let hasError = false;
  
  for (const field of photoFields) {
    const value = formValues.value[field.token];
    
    // Skip if no file or already uploaded
    if (!value?.file || value?.uploaded) {
      if (value?.document_id) {
        uploadedIds.push(value.document_id);
      }
      continue;
    }
    
    // Upload this photo
    uploadingFields.value[field.token] = true;
    
    try {
      const response = await $gotApi.uploadFormPhoto(props.orderId, value.file, field.token);
      
      if (response.success) {
        // Update value with document_id
        formValues.value[field.token] = {
          file: value.file,
          uploaded: true,
          document_id: response.document_id,
          url: response.url || null
        };
        uploadedIds.push(response.document_id);
      } else {
        fieldErrors.value[field.token] = t('GOT.form_field_photo_upload_failed');
        hasError = true;
      }
    } catch (error) {
      console.error('Error uploading photo:', error);
      fieldErrors.value[field.token] = t('GOT.form_field_photo_upload_failed');
      hasError = true;
    } finally {
      uploadingFields.value[field.token] = false;
    }
    
    // Stop on first error
    if (hasError) break;
  }
  
  return { success: !hasError, uploadedIds };
};

// Delete uploaded photos (called on error to cleanup)
const deleteUploadedPhotos = async (documentIds) => {
  for (const docId of documentIds) {
    try {
      await $gotApi.removeFormPhoto(props.orderId, docId);
    } catch (error) {
      console.error('Error deleting photo:', docId, error);
    }
  }
};

// Validate all fields
const validate = () => {
  let isValid = true;
  fieldErrors.value = {};
  
  if (!props.form?.structure) return true;
  
  props.form.structure.forEach(field => {
    const value = formValues.value[field.token];
    
    if (field.required) {
      if (field.type === 'photo') {
        // Photo must have a file (either local or already uploaded)
        if (!value?.file && !value?.document_id) {
          fieldErrors.value[field.token] = t('GOT.form_field_required');
          isValid = false;
        }
      } else if (field.type === 'numeric') {
        if (value === null || value === '' || value === undefined) {
          fieldErrors.value[field.token] = t('GOT.form_field_required');
          isValid = false;
        }
      } else {
        // Text and other types
        if (!value || (typeof value === 'string' && !value.trim())) {
          fieldErrors.value[field.token] = t('GOT.form_field_required');
          isValid = false;
        }
      }
    }
  });
  
  emit('validation-change', isValid);
  return isValid;
};

// Get filled form data for submission
const getFilledForm = () => {
  if (!props.form?.structure) return [];
  
  return props.form.structure.map(field => {
    const value = formValues.value[field.token];
    
    let response;
    if (field.type === 'photo') {
      response = value?.document_id || null;
    } else {
      response = value;
    }
    
    return {
      token: field.token,
      response
    };
  });
};

// Check if any photo is currently uploading
const isAnyUploading = computed(() => {
  return Object.values(uploadingFields.value).some(v => v);
});

// Check if all required photos are uploaded
const allPhotosUploaded = computed(() => {
  if (!props.form?.structure) return true;
  
  return props.form.structure
    .filter(f => f.type === 'photo' && f.required)
    .every(f => formValues.value[f.token]?.uploaded);
});

// Initialize on mount
watch(() => props.form, () => {
  initializeFormValues();
}, { immediate: true });

// Expose methods for parent component
defineExpose({
  validate,
  getFilledForm,
  isAnyUploading,
  allPhotosUploaded,
  uploadAllPhotos,
  deleteUploadedPhotos
});
</script>

<template>
  <div class="space-y-6">
    <!-- Form Header -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-gray-200/60 bg-gray-50/50 -mx-4 -mt-4">
      <Icon name="fa6-solid:clipboard-list" class="text-gray-600 text-sm" />
      <div>
        <h2 class="text-base font-semibold text-gray-900">{{ form.name }}</h2>
        <p class="text-xs text-gray-500">{{ $t('GOT.dynamic_form_description') }}</p>
      </div>
    </div>

    <!-- Form Fields -->
    <div class="space-y-6">
      <template v-for="field in form.structure" :key="field.token">
        <!-- Supported Field Types -->
        <component
          v-if="isFieldSupported(field.type)"
          :is="getFieldComponent(field.type)"
          :field="field"
          :model-value="formValues[field.token]"
          :error="fieldErrors[field.token]"
          :disabled="disabled"
          :uploading="uploadingFields[field.token]"
          @update:model-value="(val) => updateFieldValue(field.token, val)"
        />

        <!-- Unsupported Field Type Warning -->
        <div 
          v-else 
          class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg"
        >
          <div class="flex items-center gap-2 text-yellow-800">
            <Icon name="fa6-solid:triangle-exclamation" class="text-sm" />
            <span class="text-sm font-medium">
              {{ $t('GOT.form_field_unsupported', { type: field.type }) }}
            </span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
