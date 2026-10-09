<script setup>
// path: components/molecules/PersonContactSelect.vue
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';

import H1 from '~/components/atoms/H1.vue';
import PersonContactDetail from '~/components/molecules/PersonContactDetail.vue';
import AddContact from '~/components/molecules/AddContact.vue';

const { $PersonContactApiService } = useNuxtApp();

const { t } = useI18n();

const emit = defineEmits(['selected-item']);

const props = defineProps({
  title: String,
  persons: Array,
  itemSelectedId: Number,
  onlyEmail: {
    type: Boolean,
    default: false
  },
  onlyPhone: {
    type: Boolean,
    default: false
  }
});

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const selectedPersonContact = ref(null);
const editingContact = ref(null);

const openAddContactRegion = (person) => {
  selectedPersonContact.value = person;
  editingContact.value = null;
  showRegion.value = true;
};

const openEditContact = (person, contact) => {
  selectedPersonContact.value = person;
  editingContact.value = contact;
  showRegion.value = true;
};

const deletePersonContact = (person, contact) => {
  if (!confirm(t('confirmation_text_block.confirm_delete'))) {
    return;
  }
  $PersonContactApiService.remove(contact.id).then(() => {
    const idx = person.contacts.findIndex(c => c.id === contact.id);
    if (idx > -1) {
      person.contacts.splice(idx, 1);
    }
  }).catch((err) => {
    console.error(err);
  });
};

const toggleRegion = (value) => {
  showRegion.value = value;
  if (!value) {
    editingContact.value = null;
  }
};

const onNewContact = (newContact) => {
  if (selectedPersonContact.value) {
    if (!Array.isArray(selectedPersonContact.value.contacts)) {
      selectedPersonContact.value.contacts = [];
    }

    newContact['person'] = selectedPersonContact.value.id;

    // Capturem l'id ABANS de disparar la petició asíncrona,
    // ja que editingContact.value es reseteja tot seguit.
    const wasEditingId = editingContact.value?.id || null;

    $PersonContactApiService.save(newContact).then((contactSaved) => {
      emit('selected-item', contactSaved);

      if (wasEditingId) {
        const idx = selectedPersonContact.value.contacts.findIndex(c => c.id === wasEditingId);
        if (idx > -1) {
          selectedPersonContact.value.contacts.splice(idx, 1, contactSaved);
        } else {
          selectedPersonContact.value.contacts.push(contactSaved);
        }
      } else {
        selectedPersonContact.value.contacts.push(contactSaved);
      }
    });
  }

  editingContact.value = null;
  showRegion.value = false;
};

const onRemoveContact = (contact) => {
  if (!contact || !contact.id || !selectedPersonContact.value) return;
  deletePersonContact(selectedPersonContact.value, contact);
  editingContact.value = null;
  showRegion.value = false;
};

const getPersonDisplayName = (person) => {
  if (!person) return '';
  if (person.full_name) return person.full_name;
  const name = person.is_juridic
    ? person.name
    : [person.name, person.surname].filter(Boolean).join(' ').trim();
  return name || person.token || String(person.id ?? '');
};

const close = () => {
  showRegion.value = false;
  editingContact.value = null;
};

defineExpose({ close });

onMounted(() => {
});
</script>

<template>
  <div class="wrapper text-base">
    <div v-if="title" class="flex justify-between items-center mb-2">
      <H1>{{ title }}</H1>
    </div>

    <div class="row">
      <div v-for="person in persons">
        <fieldset v-if="person" class="border border-gray-300 rounded p-4 bg-white">
          <legend class="text-base font-semibold px-3">{{ getPersonDisplayName(person) }}</legend>

          <template v-for="contact in person.contacts" :key="contact.id">
            <div
              v-if="(!onlyEmail && !onlyPhone) || (onlyEmail && contact.email) || (onlyPhone && contact.phone)"
              class="relative group border bg-gray-100 hover:bg-yellow-100 border-gray-200 w-full mb-2">
              <button type="button" class="cursor-pointer w-full p-4 block text-left"
                @click="() => emit('selected-item', contact)">
                <PersonContactDetail :item="contact" :person="person" :showPersonName="false" :allowClick="false"
                  :onlyEmail="onlyEmail" :onlyPhone="onlyPhone" />
              </button>

              <button type="button" @click.stop="openEditContact(person, contact)"
                class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                <Icon name="fa6-solid:pencil" />
              </button>
            </div>
          </template>

          <AtomsButtonSeleccio @click="openAddContactRegion(person)" class="py-3">
            <Icon name="fa6-solid:plus" class="mr-2" />
            {{ $t('common.add') }} {{ $t('common.contact') }}
          </AtomsButtonSeleccio>
        </fieldset>
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
        'w-[95%]': true
      }">

      <div id="region_nav" class="mb-3 px-3 flex justify-start">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded" aria-label="Tancar formulari">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>

      <div class="px-10">
        <AddContact v-if="showRegion && selectedPersonContact" :selectedContact="editingContact"
          @new-contact="onNewContact" @remove-contact="onRemoveContact" />
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>