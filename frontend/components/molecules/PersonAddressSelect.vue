<!-- components/molecules/PersonAddressSelect.vue -->
<script setup>
import { ref } from 'vue';
import H1 from '~/components/atoms/H1.vue';
import AddAddress from '~/components/molecules/AddAddress.vue';

const { $PersonAddressApiService } = useNuxtApp();

const emit = defineEmits(['selected-item']);

const props = defineProps({
  title: { type: String, default: '' },
  persons: { type: Array, default: () => [] },
  isBilling: { type: Boolean, required: false },
  linkExtra: { type: Object, default: () => ({}) }
});

const showRegion = ref(false);
const selectedPerson = ref(null);

const openAddAddressRegion = (person) => {
  selectedPerson.value = person;
  showRegion.value = true;
};

const toggleRegion = (value) => { showRegion.value = value; };

const onNewAddress = async (address) => {
  if (!selectedPerson.value) {
    showRegion.value = false;
    return;
  }

  const payload = {
    person: selectedPerson.value?.id ?? selectedPerson.value,
    address: address.id,
    ...(props.isBilling !== undefined ? { is_billing: props.isBilling } : {}),
    ...(props.linkExtra || {})
  };

  const personAddress = await $PersonAddressApiService.save(payload);

  if (!Array.isArray(selectedPerson.value.addresses)) {
    selectedPerson.value.addresses = [];
  }
  selectedPerson.value.addresses.push(personAddress);

  // Emet perquè el pare pugui agafar el seleccionat
  emit('selected-item', personAddress);

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
</script>

<template>
  <div class="wrapper text-base">
    <div v-if="title" class="flex justify-between items-center mb-2">
      <H1>{{ title }}</H1>
    </div>

    <div class="row">
      <div v-for="person in persons.filter(Boolean)" :key="person?.id || person?.full_name">
        <fieldset v-if="person" class="border border-gray-300 rounded p-4 bg-white">
          <legend class="text-base font-semibold px-3">
            {{ getPersonDisplayName(person) || '—' }}
          </legend>

          <!-- Llista d’adreces existents de la persona -->
          <div v-if="person.addresses?.length > 0">
            <button
              v-for="pa in person.addresses"
              :key="pa.id"
              class="cursor-pointer border bg-gray-100 hover:bg-yellow-100 border-gray-200 w-full p-3 block text-left mb-2 rounded"
              @click="() => emit('selected-item', pa)"
            >
              <div class="font-medium">{{ pa.address_complete }}</div>
            </button>
          </div>

          <!-- Estat sense adreces -->
          <div v-else class="text-slate-500 text-sm mb-2">
            ({{ $t('address_block.no_address') }})
          </div>

          <!-- Botó per afegir una adreça a aquesta persona -->
          <AtomsButtonSeleccio @click="openAddAddressRegion(person)" class="py-3">
            <Icon name="fa6-solid:plus" class="mr-2" />
            {{ $t('common.add') }} {{ $t('common.address') }}
          </AtomsButtonSeleccio>
        </fieldset>
      </div>
    </div>

    <!-- Regió lateral per AddAddress -->
    <div
      role="region"
      id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
        'w-[95%]': true
      }"
    >
      <div id="region_nav" class="mb-3 px-3 flex justify-start">
        <button
          @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded"
          aria-label="Tancar formulari"
        >
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>

      <div class="px-10">
        <AddAddress
          v-if="showRegion && selectedPerson"
          @new-address="onNewAddress"
        />
      </div>
    </div>
  </div>
</template>