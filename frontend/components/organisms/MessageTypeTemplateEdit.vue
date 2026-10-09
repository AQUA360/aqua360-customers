<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import CommunicationMessageVariables from '~/components/molecules/CommunicationMessageVariables.vue';
import CommunicationMessageFormatTags from '~/components/molecules/CommunicationMessageFormatTags.vue';
import { applyMessageFormatTagToTextarea } from '~/utils/messages';

const { t } = useI18n();
const { $MessageTemplateApiService, $ConfiglistApiService } = useNuxtApp();

const props = defineProps({
  template: Object,
  item: Object,
  isSubRegionOpen: Boolean,
});

const emit = defineEmits(['saved']);
const SubRegion = ref(false);

const item_instance = ref(props.item);

const saving = ref(false);
const attemptedSave = ref(false);

const template_id = ref(props.template?.id || null);
const subject = ref(props.template?.subject || '');
const body = ref(props.template?.body || '');
const selectedMessageType = ref(null);
const attachedFile = ref(null);
const existingDocument = ref(null);
const deleteFile = ref(false);

const messageTypes = ref([]);

const save = async () => {
  attemptedSave.value = true;
  if (!isValid()) return;
  saving.value = true;
  try {
    const formData = new FormData();
    if (item_instance?.value?.id) formData.append('id', item_instance.value.id);
    formData.append('type', selectedMessageType.value.code);
    formData.append('subject', subject.value);
    formData.append('body', body.value);
    if (attachedFile.value) formData.append('document', attachedFile.value);
    if (deleteFile.value) formData.append('delete_file', 'true');
    item_instance.value = await $MessageTemplateApiService.saveTypeTemplate(formData);
    emit('saved', item_instance.value);
    resetForm();
  } catch (error) {
    console.error('Error saving MESSAGE TYPE TEMPLATE:', error);
  } finally {
    saving.value = false;
    attemptedSave.value = false;
  }
};

const getMessageTypes = async () => {
  try {
    const result = await $ConfiglistApiService.getAll('communication/message-type');
    result.results.forEach(messageType => {
      messageTypes.value.push({
        code: messageType.id,
        label: messageType.name,
      });
    });
  } catch (error) {
    console.error('Error getting message types:', error);
  }
}


const isValid = () => {
  if (!selectedMessageType.value) return false;
  if (!subject.value || subject.value == '') return false;
  if (!body.value || body.value == '') return false;
  return true;
};

const resetForm = () => {
};

const insertPlaceholder = (value) => {
  const textarea = document.getElementById('messageTextarea');

  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;

  body.value = body.value.substring(0, start) + value + body.value.substring(end);

  textarea.value = body.value;

  textarea.selectionStart = textarea.selectionEnd = start + value.length;
  textarea.focus();
};

const applyFormatTag = (token) => {
  applyMessageFormatTagToTextarea(body, token);
};


watch(() => props.item, async (newItem) => {
  await getMessageTypes();
  if (newItem && newItem.id) { // is editing
    item_instance.value = newItem;
    subject.value = newItem.subject;
    body.value = newItem.body;
    existingDocument.value = newItem.document || null;
    selectedMessageType.value = messageTypes.value.find(type => type.code === newItem.type.id);
  } else { // is creating
    resetForm();
  }
}, { immediate: true });

watch(() => props.template, async (newTemplate) => {
  if (newTemplate && newTemplate.id) {
    template_id.value = newTemplate.id;
  }
}, { immediate: true });

</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion }">
    <div class="flex justify-between">
      <H1Region v-if="item?.id" class="mb-3">{{ t('common.modify') }} {{ t('common.message') }}</H1Region>
      <H1Region v-if="!item?.id" class="mb-3">{{ t('common.new_message') }}</H1Region>
    </div>
    <form @submit.prevent="save">
      <div v-if="!template_id && !item?.id" class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.message') }}</label>
        <v-select :model-value="selectedMessageType" :options="messageTypes" class="block w-full required"
          @update:modelValue="updateMessageType($event)" />
      </div>
      <div v-else class="mb-5">
        <label class="border-l-4 bg-slate-100 border-slate-400 px-2 inline-block text-slate-500 text-sm">
          {{ selectedMessageType ? selectedMessageType.label : '' }}</label>
      </div>

      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('customer_service_block.subject') }}</label>
        <input type="text" v-model="subject" class="input" :class="{ 'invalid': attemptedSave && subject == '' }" />
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('customer_service_block.body') }}</label>
        <textarea id="messageTextarea" v-model="body" class="input h-[30vh]"
          :class="{ 'invalid': attemptedSave && body == '' }" />
      </div>

      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">
          <Icon name="fa6-solid:paperclip" class="mr-1" />
          {{ t('common.attach_doc_to_comms') }}
        </label>
        <div v-if="existingDocument && !attachedFile"
          class="flex items-center gap-2 mb-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
          <Icon name="fa6-solid:file" class="text-slate-500" />
          <span class="text-slate-700 truncate">{{ existingDocument.document_name }}</span>
          <button type="button" @click="existingDocument = null; deleteFile = true" class="ml-auto text-slate-400 hover:text-red-500">
            <Icon name="fa6-solid:xmark" />
          </button>
        </div>
        <input type="file" @change="attachedFile = $event.target.files[0]" class="input" />
      </div>

      <CommunicationMessageVariables @insert="insertPlaceholder" :open="false" />
      <CommunicationMessageFormatTags @apply="applyFormatTag" />

      <hr class="mb-2 col-span-3" />
      <div class="col-span-3 flex flex-row-reverse mt-4">
        <button type="submit" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}
        </button>
      </div>
    </form>
  </div>
</template>
