<script setup>
// Selector de carrer compartit per AddAddress.vue i AddPartialAddress.vue: cerca de carrers
// existents amb desplegable (teclat ↑/↓/Enter/Esc) i creació d'un carrer nou a partir del
// text cercat, amb avís de carrers semblants per evitar duplicats.
//
// v-model: { street, creating, name, type }
//   - street: carrer existent seleccionat ({ id, name, type: { id, abbreviation } }) o null
//   - creating: true quan s'està creant un carrer nou (llavors `name`/`type` són el carrer nou)
//   - name: nom del carrer (el seleccionat o el que s'està creant)
//   - type: opció de `streetTypes` ({ code, label, ... }), o text lliure si `typeTaggable`
import { ref, computed, watch, nextTick, useId } from 'vue';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';

const { t } = useI18n();
const { $StreetApiService } = useNuxtApp();

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({ street: null, creating: false, name: '', type: null })
  },
  streetTypes: {
    type: Array,
    default: () => []
  },
  loadingStreetTypes: {
    type: Boolean,
    default: false
  },
  // Municipi on cercar els carrers (id). Sense municipi es cerca a tots.
  cityId: {
    type: [Number, String],
    default: null
  },
  disable: {
    type: Boolean,
    default: false
  },
  attemptedSave: {
    type: Boolean,
    default: false
  },
  // false quan no hi ha carrers per cercar (p. ex. adreces estrangeres): només es pot crear
  canSearch: {
    type: Boolean,
    default: true
  },
  canCadastre: {
    type: Boolean,
    default: true
  },
  typeTaggable: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue', 'street-selected', 'cadastre']);

const inputId = `street_select_${useId()}`;
const createInputId = `street_create_name_${useId()}`;
const listboxId = `street_select_listbox_${useId()}`;

const query = ref(props.modelValue?.street?.name || props.modelValue?.name || '');
const results = ref([]);
const searching = ref(false);
const dropdownOpen = ref(false);
const highlightedIndex = ref(-1);
const similarStreets = ref([]);

const street = computed(() => props.modelValue?.street || null);
const creating = computed(() => !!props.modelValue?.creating || !props.canSearch);
const name = computed(() => props.modelValue?.name || '');
const type = computed(() => props.modelValue?.type || null);

const update = (patch) => {
  emit('update:modelValue', { ...props.modelValue, ...patch });
};

// Si el pare canvia el carrer (càrrega de dades, cadastre...) se sincronitza el text de cerca
watch(() => props.modelValue?.street?.id, () => {
  if (street.value) {
    query.value = street.value.name || '';
  }
});

const normalize = (value) => (value || '').toString().trim().toLowerCase();

const toTypeOption = (streetType) => {
  if (!streetType) return type.value;
  const found = props.streetTypes.find(option => option.code === streetType.id);
  if (found) return found;
  return {
    code: streetType.id,
    label: streetType.abbreviation,
    abbreviation: streetType.abbreviation,
    name: streetType.name
  };
};

const typeAbbreviation = (value) => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  return value.abbreviation || value.label || '';
};

// ---------------------------------------------------------------- cerca

const search = debounce(async () => {
  const text = query.value?.trim();
  if (!text) {
    results.value = [];
    searching.value = false;
    return;
  }
  try {
    const data = await $StreetApiService.getAll(text, [], 1, null, false, props.cityId);
    // Es descarta la resposta si mentrestant l'usuari ha continuat escrivint
    if (text === query.value?.trim()) {
      results.value = data.results || [];
      highlightedIndex.value = results.value.length > 0 ? 0 : -1;
    }
  } catch (error) {
    console.error('Error searching streets:', error);
    results.value = [];
  } finally {
    searching.value = false;
  }
}, 300);

const onQueryInput = () => {
  // Qualsevol canvi al text desfà la selecció anterior
  if (street.value) {
    update({ street: null, creating: false, name: query.value });
  }
  dropdownOpen.value = true;
  searching.value = !!query.value?.trim();
  search();
};

// L'opció de crear sempre és l'última del desplegable, excepte si ja hi ha un carrer amb el mateix nom
const canCreateFromQuery = computed(() => {
  const text = normalize(query.value);
  if (text.length < 2) return false;
  return !results.value.some(result => normalize(result.name) === text);
});

const optionsCount = computed(() => results.value.length + (canCreateFromQuery.value ? 1 : 0));

const openDropdown = () => {
  if (props.disable || street.value) return;
  dropdownOpen.value = true;
  if (query.value?.trim() && results.value.length === 0) {
    searching.value = true;
    search();
  }
};

const closeDropdown = () => {
  // Es deixa temps perquè el clic sobre una opció arribi abans de tancar
  setTimeout(() => { dropdownOpen.value = false; }, 150);
};

const onKeydown = (event) => {
  if (!dropdownOpen.value && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
    openDropdown();
    return;
  }
  const total = optionsCount.value;
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    if (total > 0) highlightedIndex.value = (highlightedIndex.value + 1) % total;
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    if (total > 0) highlightedIndex.value = (highlightedIndex.value - 1 + total) % total;
  } else if (event.key === 'Enter') {
    event.preventDefault();
    if (highlightedIndex.value < 0 || highlightedIndex.value >= total) return;
    if (highlightedIndex.value < results.value.length) {
      selectStreet(results.value[highlightedIndex.value]);
    } else {
      startCreating();
    }
  } else if (event.key === 'Escape') {
    if (dropdownOpen.value) event.preventDefault();
    dropdownOpen.value = false;
  }
};

// ---------------------------------------------------------------- accions

const selectStreet = (selected) => {
  query.value = selected.name;
  results.value = [];
  similarStreets.value = [];
  dropdownOpen.value = false;
  update({ street: selected, creating: false, name: selected.name, type: toTypeOption(selected.type) });
  emit('street-selected', selected);
};

const clear = () => {
  query.value = '';
  results.value = [];
  similarStreets.value = [];
  update({ street: null, creating: false, name: '' });
  nextTick(() => document.getElementById(inputId)?.focus());
};

const searchSimilar = debounce(async () => {
  const text = name.value?.trim();
  if (!props.canSearch || !creating.value || !text || text.length < 2) {
    similarStreets.value = [];
    return;
  }
  try {
    const data = await $StreetApiService.getAll(text, [], 1, null, false, props.cityId);
    similarStreets.value = (data.results || []).slice(0, 5);
  } catch (error) {
    similarStreets.value = [];
  }
}, 300);

const startCreating = () => {
  dropdownOpen.value = false;
  update({
    street: null,
    creating: true,
    name: query.value?.trim() || name.value || '',
    type: type.value || props.streetTypes[0] || null
  });
  nextTick(() => {
    searchSimilar();
    document.getElementById(createInputId)?.focus();
  });
};

const backToSearch = () => {
  query.value = name.value || '';
  similarStreets.value = [];
  update({ street: null, creating: false });
  nextTick(() => {
    document.getElementById(inputId)?.focus();
    openDropdown();
  });
};

const onNameInput = (event) => {
  update({ name: event.target.value });
  nextTick(searchSimilar);
};

const onTypeChange = (value) => {
  update({ type: value });
};

// Quan s'entra en mode creació des de fora (p. ex. el cadastre), es busquen carrers semblants
watch(creating, (value) => {
  if (value) nextTick(searchSimilar);
  else similarStreets.value = [];
});

const requestCadastre = () => {
  emit('cadastre', (creating.value ? name.value : query.value)?.trim() || '');
};
</script>

<template>
  <div>
    <!-- Carrer seleccionat (existent) -->
    <div v-if="!creating && street"
      class="flex items-center justify-between gap-2 px-3 py-2 border border-green-300 bg-green-50 rounded-md">
      <div class="flex items-center gap-2 min-w-0">
        <Icon name="fa6-solid:circle-check" class="text-green-600 shrink-0" />
        <span class="font-medium text-slate-800 truncate">
          {{ street.type?.abbreviation || typeAbbreviation(type) }} {{ street.name }}
        </span>
      </div>
      <button v-if="!disable" type="button" class="button-default text-sm shrink-0" @click="clear">
        <Icon name="fa6-solid:pen" class="mr-1" /> {{ t('address_block.change_street') }}
      </button>
    </div>

    <!-- Cerca de carrer existent -->
    <div v-else-if="!creating" class="relative">
      <div class="relative">
        <Icon name="fa6-solid:magnifying-glass" class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        <input :id="inputId" type="text" v-model="query" @input="onQueryInput"
          @focus="openDropdown" @blur="closeDropdown" @keydown="onKeydown"
          autocomplete="off" :disabled="disable" role="combobox" :aria-expanded="dropdownOpen"
          aria-autocomplete="list" :aria-controls="listboxId"
          :class="{ 'invalid': attemptedSave && !street }"
          class="block w-full py-2 pl-9 pr-9 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400"
          :placeholder="t('search_block.search_street')" />
        <Icon v-if="searching" name="fa6-solid:spinner" class="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-slate-400" />
      </div>

      <ul v-if="dropdownOpen && query?.trim()" :id="listboxId" role="listbox"
        class="absolute z-20 mt-1 w-full max-h-72 overflow-y-auto bg-white border border-gray-300 rounded-md shadow-lg divide-y divide-gray-100 text-sm">
        <li v-if="searching && results.length === 0" class="px-4 py-2 text-slate-500">
          {{ t('common.loading') }}...
        </li>
        <li v-for="(result, index) in results" :key="result.id" role="option"
          :aria-selected="highlightedIndex === index"
          @mousedown.prevent="selectStreet(result)" @mouseenter="highlightedIndex = index"
          class="px-4 py-2 cursor-pointer flex items-center gap-2"
          :class="highlightedIndex === index ? 'bg-sky-50 text-sky-800' : 'hover:bg-gray-50'">
          <span class="text-slate-500 w-10 shrink-0">{{ result.type?.abbreviation }}</span>
          <span class="text-slate-800">{{ result.name }}</span>
        </li>
        <li v-if="!searching && results.length === 0" class="px-4 py-2 text-slate-500 italic">
          {{ t('address_block.no_streets_found') }}
        </li>
        <li v-if="canCreateFromQuery" role="option" :aria-selected="highlightedIndex === results.length"
          @mousedown.prevent="startCreating" @mouseenter="highlightedIndex = results.length"
          class="px-4 py-2 cursor-pointer flex items-center gap-2 font-medium text-sky-700"
          :class="highlightedIndex === results.length ? 'bg-sky-50' : 'hover:bg-gray-50'">
          <Icon name="fa6-solid:plus" />
          {{ t('address_block.create_street_named', { name: query.trim() }) }}
        </li>
      </ul>

      <div v-if="!disable" class="flex items-center gap-3 mt-1 text-sm">
        <a href="#" class="text-sky-600 hover:underline" @click.prevent="startCreating">
          <Icon name="fa6-solid:plus" class="mr-0.5" /> {{ t('address_block.create_street') }}
        </a>
        <a v-if="canCadastre" href="#" class="text-sky-600 hover:underline" @click.prevent="requestCadastre">
          {{ t('search_block.search_cadastre') }}
        </a>
      </div>
    </div>

    <!-- Creació de carrer nou -->
    <div v-else>
      <div class="flex">
        <v-select class="street-picker-type block w-40 required"
          :disabled="loadingStreetTypes || (streetTypes.length == 0 && !typeTaggable) || disable"
          :model-value="type" @update:modelValue="onTypeChange"
          :options="streetTypes" :taggable="typeTaggable"
          :placeholder="t('common.type')"
          :class="{ 'invalid': attemptedSave && !type }"
          label="label"></v-select>
        <input :id="createInputId" type="text" :value="name" class="input street-picker-name w-full"
          :disabled="disable" @input="onNameInput"
          :placeholder="t('address_block.street_name_placeholder')"
          :class="{ 'invalid': attemptedSave && !name?.trim() }" />
      </div>
      <div class="flex flex-wrap items-center justify-between gap-2 mt-1 text-sm">
        <span class="flex items-center gap-1.5 text-amber-700">
          <Icon name="fa6-solid:circle-info" />
          {{ t('address_block.street_new_badge') }}
        </span>
        <span v-if="!disable" class="flex items-center gap-3">
          <a v-if="canCadastre" href="#" class="text-sky-600 hover:underline" @click.prevent="requestCadastre">
            {{ t('search_block.search_cadastre') }}
          </a>
          <a v-if="canSearch" href="#" class="text-sky-600 hover:underline" @click.prevent="backToSearch">
            <Icon name="fa6-solid:magnifying-glass" class="mr-0.5" /> {{ t('address_block.back_to_street_search') }}
          </a>
        </span>
      </div>
      <div v-if="similarStreets.length > 0" class="mt-2 px-3 py-2 border border-amber-200 bg-amber-50 rounded-md text-sm">
        <p class="text-amber-800 mb-1">{{ t('address_block.similar_streets') }}</p>
        <ul class="flex flex-wrap gap-2">
          <li v-for="similar in similarStreets" :key="similar.id">
            <button type="button" class="px-2 py-0.5 rounded border border-amber-300 bg-white hover:bg-amber-100 text-slate-700"
              :disabled="disable" @click="selectStreet(similar)">
              {{ similar.type?.abbreviation }} {{ similar.name }}
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style>
.street-picker-type.v-select .vs__dropdown-toggle {
  border-radius: 0.375rem 0 0 0.375rem;
  padding-bottom: 0;
}

.street-picker-name {
  border-radius: 0 0.375rem 0.375rem 0;
}
</style>
