<script setup>
// path: components/molecules/PersonBankSelect.vue
import { ref, onMounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import _ from 'lodash';

import H1 from '~/components/atoms/H1.vue';
import BankDetail from '~/components/molecules/BankDetail.vue';
import AddBank from '~/components/molecules/AddBank.vue';
import { se } from 'date-fns/locale';


const { $PersonBankApiService } = useNuxtApp();

const { t } = useI18n();
const toast = useToast();

// Definició d'esdeveniments que aquest component pot emetre
const emit = defineEmits(['selected-item']);

// Definició de les propietats que aquest component rep
const props = defineProps({
  title: String,
  persons: Array,
  itemSelectedId: Number,
  halfRegion: Boolean
});

// Estats reactivs
const showRegion = ref(false); // Controla la visibilitat de la regió (sidebar)
const isSubRegionOpen = ref(false); // Controla l'amplada de la regió (sidebar)
const selectedPersonBank = ref(null); // Persona seleccionada per afegir un banc
const selectedBankToEdit = ref(null); // Banc seleccionat per editar
const wrapperRef = ref(null);

const scrollAddBankRegionToTop = async () => {
  await nextTick();

  // Cerquem el contenidor desplaçable més proper des del wrapper del component
  let node = wrapperRef.value;
  while (node) {
    const style = window.getComputedStyle(node);
    const canScrollY = (style.overflowY === 'auto' || style.overflowY === 'scroll') && node.scrollHeight > node.clientHeight;
    if (canScrollY) {
      node.scrollTop = 0;
      return;
    }
    node = node.parentElement;
  }

  // Fallback: desplaçar la finestra sencera
  window.scrollTo({ top: 0, behavior: 'auto' });
};

/**
 * Funció per obrir la regió d'afegir banc
 * @param {Object} person - La persona seleccionada
 */
const openAddBankRegion = (person) => {
  selectedPersonBank.value = person; // Assigna la persona seleccionada
  selectedBankToEdit.value = null; // Reseteja el banc a editar
  showRegion.value = true; // Mostra la regió
  scrollAddBankRegionToTop();
};

/**
 * Funció per obrir la regió d'editar banc
 * @param {Object} person - La persona seleccionada
 * @param {Object} bank - El banc que es vol editar
 */
const openEditBankRegion = (person, bank) => {
  selectedPersonBank.value = person; // Assigna la persona seleccionada
  selectedBankToEdit.value = bank; // Assigna el banc a editar
  showRegion.value = true; // Mostra la regió
  scrollAddBankRegionToTop();
};

/**
 * Funció per tancar o obrir la regió
 * @param {Boolean} value - Valor per mostrar o amagar la regió
 */
const toggleRegion = (value) => {
  showRegion.value = value;
};

/**
 * Camps del titular que l'usuari escriu al formulari (country/bank són selects amb forma variable).
 * El SWIFT no hi és: si l'IBAN no canvia, el backend sí que l'aplica al compte (`swift_updated`).
 */
const HOLDER_FIELDS = ['name', 'dni', 'role', 'account_number'];

/** True si l'usuari ha tocat alguna dada del titular respecte del compte que editava. */
const hasHolderChanges = (originalBank, formBank) => {
  if (!originalBank) return false;
  return HOLDER_FIELDS.some(field => (originalBank[field] ?? '') !== (formBank[field] ?? ''));
};

/**
 * Desa el compte editat o afegit i el selecciona.
 *
 * Aquest selector sempre s'obre des d'un contracte, una factura o un compromís,
 * mai des de la fitxa de la persona. Un PersonBank penja de la PERSONA i el
 * poden compartir diversos contractes (Contract.payment -> GeneralPayment.IBAN),
 * així que editar-lo en lloc canviaria l'IBAN de tots alhora. Per això aquí mai
 * s'hi fa PUT: el backend resol el compte i, si l'IBAN ja existeix en aquesta
 * persona, reaprofita el compte existent (només n'actualitza el SWIFT/BIC, que és
 * del mateix compte); si no, en crea un de nou i deixa l'original intacte.
 *
 * Per corregir de debò les dades d'un compte cal anar a la fitxa de la persona.
 *
 * @param {Object} newBank - Dades del formulari
 */
const onNewBank = async (newBank) => {
  if (!selectedPersonBank.value) {
    showRegion.value = false;
    return;
  }

  if (!Array.isArray(selectedPersonBank.value.banks)) {
    selectedPersonBank.value.banks = [];
  }

  const editedBank = selectedBankToEdit.value;
  const payload = { ...newBank, person: selectedPersonBank.value.id };
  // `current_id` només serveix perquè, si l'IBAN no ha canviat, es reaprofiti
  // aquest mateix compte i no un altre duplicat de la persona.
  payload.current_id = editedBank?.id ?? null;
  delete payload.id;
  delete payload.is_default;

  try {
    const bankSaved = await $PersonBankApiService.resolve(payload);
    if (!bankSaved) return;

    const isSameAccount = !!editedBank && bankSaved.id === editedBank.id;
    if (bankSaved.swift_updated) {
      toast.success(t('informative_block.person_bank_swift_updated'));
    }
    if (bankSaved.reused && isSameAccount) {
      // L'IBAN no ha canviat: només s'hi aplica el SWIFT. Si l'usuari havia
      // tocat altres dades del titular, cal dir-li que no s'han desat.
      if (hasHolderChanges(editedBank, newBank)) {
        toast.info(t('informative_block.person_bank_edit_not_applied'));
      }
    } else if (bankSaved.reused) {
      toast.info(t('informative_block.person_bank_reused'));
    } else if (editedBank) {
      toast.info(t('informative_block.person_bank_copied_on_edit'));
    }

    emit('selected-item', bankSaved);
    const index = selectedPersonBank.value.banks.findIndex(b => b.id === bankSaved.id);
    if (index !== -1) {
      selectedPersonBank.value.banks[index] = bankSaved;
    } else {
      selectedPersonBank.value.banks.push(bankSaved);
    }
    showRegion.value = false;
  } catch (error) {
    // $apiManager ja mostra el toast amb el `detail` retornat pel backend.
    // Es deixa el formulari obert perquè l'usuari pugui reintentar-ho.
    console.error('Error saving person bank:', error);
  }
};

const deactivateBank = async (bankId) => {
  if (!confirm(t('confirmation_text_block.confirm_deactivate'))) {
    return;
  }
  let bank = props.persons.find(person => person.banks.find(bank => bank.id === bankId));
  bank.banks.find(bank => bank.id === bankId).is_active = false;
  let saveObject = {
    id: bankId,
    is_active: false
  };
  try {
    await $PersonBankApiService.save(saveObject);
  } catch (error) {
    console.error('Error deactivation:', error);
  }
};

onMounted(() => {
  //console.log(props.persons)
  // Inicialitzacions si escau
});
</script>

<template>
  <div class="wrapper text-base" ref="wrapperRef">
    <!-- Títol del Component -->
    <div v-if="title" class="flex justify-between items-center mb-2">
      <H1>{{ title }}</H1>
    </div>

    <!-- Llista de Persones i Bàncs -->
    <div class="row">
      <div v-for="person in persons">
        <fieldset v-if="person" class="border border-gray-300 rounded p-4 bg-white">
          <legend class="text-base font-semibold px-3">{{ person.full_name }}</legend>

          <!-- Llista de Comptes Bancaris de la Persona -->
          <div v-for="bank in person.banks" :key="bank.id"
            class="item__bank border bg-gray-100 hover:bg-yellow-100 border-gray-200 w-full p-4 block text-left mb-2 group relative"
            :class="{ 'opacity-50 cursor-not-allowed pointer-events-none': !bank.is_active }"
            role="button" :aria-disabled="!bank.is_active" :tabindex="bank.is_active ? 0 : -1"
            @click="bank.is_active && emit('selected-item', bank)"
            @keydown.enter.prevent="bank.is_active && emit('selected-item', bank)">
            <BankDetail :item="bank" :person="person" />
            <button v-if="bank.is_active"
              class="absolute right-9 top-2 h-6 w-6 items-center justify-center rounded-md bg-white hover:bg-sky-50 transition-all duration-200 opacity-0 group-hover:opacity-100 hover:shadow-md"
              @click.stop="openEditBankRegion(person, bank)">
              <Icon name="fa6-solid:pencil" class="text-sky-500 group-hover:text-sky-600 text-sm m-auto" />
            </button>
            <button v-if="bank.is_active"
              class="absolute right-2 top-2 h-6 w-6 items-center justify-center rounded-md bg-white hover:bg-red-50 transition-all duration-200 opacity-0 group-hover:opacity-100 hover:shadow-md"
              @click.stop="deactivateBank(bank.id)">
              <Icon name="fa6-solid:xmark" class="text-red-500 group-hover:text-red-600 text-sm m-auto" />
            </button>
          </div>

          <!-- Botó per Afegir Comptes Bancaris -->
          <AtomsButtonSeleccio @click="openAddBankRegion(person)" class="py-3">
            <Icon name="fa6-solid:plus" class="mr-2" />
            {{ $t('common.add') }} {{ $t('common.account_bank') }}
          </AtomsButtonSeleccio>
        </fieldset>
      </div><!-- endfor person -->
    </div><!-- end row -->

    <!-- Regió lateral per Formularis d'Afegir Banc -->
    <div role="region" id="person_bank_select_right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10 overflow-y-auto overflow-x-hidden"
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
        <AddBank v-if="showRegion && selectedPersonBank"
          :key="selectedPersonBank.id + '-' + (selectedBankToEdit ? selectedBankToEdit.id : 'new')"
          @new-bank="onNewBank" :defaultPerson="selectedPersonBank" :selectedBank="selectedBankToEdit" />
      </div>
    </div><!-- /end Regió lateral per formularis -->
  </div><!-- /end #wrapper -->
</template>