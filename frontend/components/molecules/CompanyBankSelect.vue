<script setup>
// path: components/molecules/PersonBankSelect.vue
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';

import InputIban from '~/components/atoms/InputIban.vue';
import H1 from '~/components/atoms/H1.vue';
import BankDetail from '~/components/molecules/BankDetail.vue';
import AddBank from '~/components/molecules/AddBank.vue';
import AddCompanyBanks from './AddCompanyBanks.vue';
import { se } from 'date-fns/locale';


const { $PersonBankApiService } = useNuxtApp();

const { t } = useI18n();

// Definició d'esdeveniments que aquest component pot emetre
const emit = defineEmits(['selected-item']);

// Definició de les propietats que aquest component rep
const props = defineProps({
  title: String,
  company: Object,
  itemSelectedId: Number,
  halfRegion: Boolean
});

// Estats reactivs
const showRegion = ref(false); // Controla la visibilitat de la regió (sidebar)
const isSubRegionOpen = ref(false); // Controla l'amplada de la regió (sidebar)
const selectedPersonBank = ref(null); // Persona seleccionada per afegir un banc

/**
 * Funció per obrir la regió d'afegir banc
 * @param {Object} person - La persona seleccionada
 */
const openAddBankRegion = (person) => {
  selectedPersonBank.value = person; // Assigna la persona seleccionada
  showRegion.value = true; // Mostra la regió
};

/**
 * Funció per tancar o obrir la regió
 * @param {Boolean} value - Valor per mostrar o amagar la regió
 */
const toggleRegion = (value) => {
  showRegion.value = value;
};

/**
 * Funció per manejar el nou banc creat
 * @param {Object} newBank - El nou banc creat
 */
const onNewBank = (newBank) => {
  console.log('onNewBank', newBank);
  if (selectedPersonBank.value) {
    // Assegura't que la persona seleccionada té una llista de bancs
    if (!Array.isArray(selectedPersonBank.value.banks)) {
      selectedPersonBank.value.banks = [];
    }

    // guardem el registre a la base de dades
    newBank['person'] = selectedPersonBank.value.id;
    $PersonBankApiService.save(newBank).then((bankSaved) => {
      console.log('PersonBankApiService.response', bankSaved);
      emit('selected-item', bankSaved);
      // Afegeix el nou banc a la llista de bancs de la persona
      selectedPersonBank.value.banks.push(bankSaved);
    });
  }

  // Tanca la regió
  showRegion.value = false;
};


onMounted(() => {
  // Inicialitzacions si escau
});
</script>

<template>
  <div class="wrapper text-base">
    <!-- Títol del Component -->
    <div v-if="title" class="flex justify-between items-center mb-2">
      <H1>{{ title }}</H1>
    </div>

    <!-- Llista de Persones i Bàncs -->
    <div class="row">
      <fieldset v-if="company" class="border border-gray-300 rounded p-4 bg-white">
        <legend class="text-base font-semibold px-3">{{ company.name }}</legend>

        <!-- Llista de Comptes Bancaris de la Persona -->
        <button
          class="item__bank border bg-gray-100 hover:bg-yellow-100 border-gray-200 w-full p-4 block text-left mb-2"
          v-for="bank in company.company_banks" :key="bank.id" @click="() => emit('selected-item', bank)">
          <BankDetail :item="bank" :company="company" />
        </button>

        <!-- Botó per Afegir Comptes Bancaris -->
        <AtomsButtonSeleccio @click="openAddBankRegion(person)" class="py-3">
          <Icon name="fa6-solid:plus" class="mr-2" />
          {{ $t('common.add') }} {{ $t('common.account_bank') }}
        </AtomsButtonSeleccio>
      </fieldset>
    </div><!-- end row -->

    <!-- Regió lateral per Formularis d'Afegir Banc -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-1/2': halfRegion,
        'w-[95%]': !halfRegion
      }">

      <!-- Botó per Tancar la Regió -->
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded active:bg-slate-300" aria-label="Tancar formulari">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>

      <!-- Component AddBank -->
      <div class="px-10">
        <AddBank v-if="showRegion && selectedPersonBank" @new-bank="onNewBank" :defaultPerson="selectedPersonBank" />
        <AddCompanyBanks v-if="addingBank" :company_id="company_id" :vat="vat" :isSubRegionOpen="isSubRegionOpen"
          :bank="selectedBank" @new-bank="newBank" />
      </div>
    </div><!-- /end Regió lateral per formularis -->
  </div><!-- /end #wrapper -->
</template>

<style scoped>
/* Els teus estils aquí */
</style>
