<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import debounce from 'lodash.debounce';

import H1 from '~/components/atoms/H1.vue';

const { t } = useI18n();

const phone = ref('');
const emails = ref(['']);
const role = ref('');

const MAX_EMAILS = 5;
const canAddEmail = computed(() => emails.value.length < MAX_EMAILS);
const canDelete = computed(() => !!props.selectedContact?.id); // només si és un contacte ja existent

const emit = defineEmits(['new-contact', 'remove-contact']);

const props = defineProps({
  selectedContact: Object
});

// set-up

const resetValues = () => {
  phone.value = '';
  emails.value = [''];
  role.value = '';
}

const assignValues = async () => {
  phone.value = props.selectedContact.phone;
  role.value = props.selectedContact.role;

  const raw = props.selectedContact.email || '';
  const parts = raw.split(';').map(e => e.trim()).filter(e => e.length > 0);
  emails.value = parts.length > 0 ? parts : [''];
}

const addEmail = () => {
  if (canAddEmail.value) {
    emails.value.push('');
  }
}

const removeEmail = (idx) => {
  emails.value.splice(idx, 1);
}

// saving

const save = async () => {
  const emailList = emails.value.map(e => (e || '').trim()).filter(e => e.length > 0);

  let data = {
    ...props.selectedContact,
    phone: phone.value,
    email: emailList.join(';'),
    role: role.value
  };

  emit('new-contact', data);
}

const removeAll = () => {
  emit('remove-contact', props.selectedContact);
}

watch(() => props.selectedContact, () => {
  if (props.selectedContact == null) resetValues();
  else assignValues()
});

onMounted(() => {
  if (props.selectedContact == null) resetValues();
  else assignValues()
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('common.contact_info') }}</H1>
    </div>
    <div class="row grid grid-cols-2 gap-3">
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.tlf') }}</label>
        <input type="text" v-model="phone" class="input" />
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.role') }}</label>
        <input type="text" v-model="role" class="input" />
      </div>
      <div class="mb-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.email_long') }}</label>
        <div class="space-y-2">
          <div v-for="(em, idx) in emails" :key="idx" class="flex items-center gap-2">
            <input type="text" v-model="emails[idx]" class="input flex-1" v-validate-email />
            <button type="button" class="px-2 py-1 text-gray-400 hover:text-red-500" @click="removeEmail(idx)">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>

          <button v-if="canAddEmail" type="button"
            class="flex items-center gap-1 text-sm text-sky-600 hover:text-sky-800" @click="addEmail">
            <Icon name="fa6-solid:plus" class="text-xs" />
            {{ t('common.add_email') }}
          </button>
        </div>
      </div>
    </div>
    <div class="flex flex-row-reverse mt-4 gap-2">
      <button @click="save" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
      </button>
      <button v-if="canDelete" @click="removeAll" type="button"
        class="flex items-center gap-1 px-3 py-2 border border-red-300 text-red-600 rounded hover:bg-red-50">
        <Icon name="fa6-solid:trash" />&nbsp; {{ $t('common.delete') }}
      </button>
    </div>
  </div>
</template>