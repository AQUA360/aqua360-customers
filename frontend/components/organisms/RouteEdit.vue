<script setup>
import { toRaw, ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import Draggable from 'vuedraggable';
import _ from 'lodash';

const props = defineProps({
  route: Object
});

const { t } = useI18n();
const { $RouteApiService } = useNuxtApp();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);
const searching = ref(false);
const error = ref(null);
const loading_zones = ref(true);

const name = ref(null);
const token = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPositions = ref(false);
const editingZone = ref(false);

const zones = ref([])

const selected_positions = ref([])
const selected_positions_to_add = ref(new Set())
const selected_positions_to_remove = ref([])
const selected_zone_id = ref(null)
const selected_zone = ref(null)
const zone = ref(null)
const editingPosition = ref(null)
const insertAfterIndex = ref(null) // null = append at end, -1 = before first, N = after index N

const insertAfterPositionValue = computed(() => {
  if (insertAfterIndex.value === null) return null;
  if (insertAfterIndex.value === -1) return 0;
  return Number(allPositions.value[insertAfterIndex.value]?.position) || 0;
})

// Infinite scroll state
const currentPage = ref(1)
const isLoadingMore = ref(false)
const hasMorePositions = ref(true)
const allPositions = ref([])
const sortBy = ref('position')
const sortDesc = ref(false)
const totalPositionsCount = ref(0)

// Search term (delegated to backend)
const positionSearch = ref('')
const hasPositionSearch = computed(() => !!positionSearch.value)
const filteredPositions = computed(() => allPositions.value)

// Local-only change tracking (not coming from backend)
const changesTab = ref('new') // 'new' | 'edited' | 'removed'
const newPositions = ref([])
const editedPositions = ref([])
const activeChanges = computed(() => {
  if (changesTab.value === 'edited') return editedPositions.value;
  if (changesTab.value === 'removed') return selected_positions_to_remove.value;
  return newPositions.value;
})

const getData = async () => {
  await getZones()

  if (props.route != null && props.route.id > 0) {
    setValues();
    // Initialize positions list with infinite scroll
    currentPage.value = 1;
    hasMorePositions.value = true;
    allPositions.value = [];
    await getPositions(1, false);
    // Setup scroll listener after DOM is ready
    setTimeout(setupScrollListener, 100);
  }
  else {
    token.value = _.random(100000, 999999);
  }

  loading.value = false;
}

const save = async () => {

  attemptedSave.value = true;
  if (isValid()) {
    saving.value = true;

    const selectedOptions = {
      name: name.value,
      token: token.value,
      route_zone_id: selected_zone_id.value,
      // position_ids: selected_positions.value.map(p => p.id),
      position_ids_to_add: Array.from(selected_positions_to_add.value).map(p => ({id: p.id, position: p.position})),
      position_ids_to_remove: selected_positions_to_remove.value.map(p => p.id)

    };

    let route = null;

    if (props.route != null && props.route.id > 0) {
      selectedOptions.id = props.route.id;
      route = await $RouteApiService.updateRoute(selectedOptions);
    }
    else {
      route = await $RouteApiService.createRoute(selectedOptions);
    }
    return navigateTo('/service/routes/')
  }
  else {
    saving.value = false;
  }
}
const deleteRoute = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    await $RouteApiService.deleteRoute(props.route.id);
    return navigateTo('/service/routes/')
  }
}

const setValues = () => {

  name.value = props.route.name;
  token.value = props.route.token;

  selected_zone.value = {
    label: props.route.route_zone?.name,
    code: props.route.route_zone?.id
  }
  selected_zone_id.value = props.route.route_zone?.id;

  getPositions();

}

const getPositions = async (page = 1, append = false) => {
  if (isLoadingMore.value) return;
  
  isLoadingMore.value = true;
  
  try {
    const apiSortField = sortBy.value;
    const searchTerm = positionSearch.value || '';
    const data = await $RouteApiService.getAllRoutePositions(searchTerm, page, apiSortField, sortDesc.value, props.route.id);
    
    let results = data.results;
    
    // If sorting by position, sort client-side by the position field
    if (sortBy.value === 'position') {
      results = results.sort((a, b) => {
        const aPos = Number(a.position) || 0;
        const bPos = Number(b.position) || 0;
        return sortDesc.value ? bPos - aPos : aPos - bPos;
      });
    }
    
    if (append) {
      // Avoid duplicates when appending (Task: Control situation where new record is already in the list)
      const currentIds = allPositions.value.map(p => p.id).filter(id => id != null);
      const removedIds = selected_positions_to_remove.value.map(p => p.id).filter(id => id != null);
      const filteredResults = results.filter(p => !currentIds.includes(p.id) && !removedIds.includes(p.id));
      allPositions.value = [...allPositions.value, ...filteredResults];
    } else {
      const removedIds = selected_positions_to_remove.value.map(p => p.id).filter(id => id != null);
      const filteredResults = results.filter(p => !removedIds.includes(p.id));
      allPositions.value = filteredResults;
      selected_positions.value = filteredResults;
    }
    
    // Update pagination state
    hasMorePositions.value = data.next !== null;
    currentPage.value = page;
    totalPositionsCount.value = data.count || results.length;
    
  } catch (error) {
    console.error('Error loading positions:', error);
  } finally {
    isLoadingMore.value = false;
  }
}

const loadMorePositions = async () => {
  if (!hasMorePositions.value || isLoadingMore.value) return;
  
  await getPositions(currentPage.value + 1, true);
}

const findPositionPage = async (id) => {
  searching.value = true;
  try {
    let found = false;
    let page = 1;

    // Clear existing list to avoid confusion while searching
    allPositions.value = [];
    
    while (!found) {
      const searchTerm = positionSearch.value || '';
      const data = await $RouteApiService.getAllRoutePositions(searchTerm, page, sortBy.value, sortDesc.value, props.route.id);
      
      if (data.results && data.results.length > 0) {
        const results = data.results;
        const removedIds = selected_positions_to_remove.value.map(p => p.id).filter(id => id != null);
        const filteredResults = results.filter(p => !removedIds.includes(p.id));

        allPositions.value = [...allPositions.value, ...filteredResults];
        selected_positions.value = [...allPositions.value];
        
        if (results.some(p => p.id === id)) {
          found = true;
          currentPage.value = page;
          hasMorePositions.value = data.next !== null;
          totalPositionsCount.value = data.count;
        } else if (data.next) {
          page++;
        } else {
          // End of list reached and not found
          break;
        }
      } else {
        break;
      }
    }

    // If sorting by position, ensure the loaded items are sorted properly 
    // since backend might not correctly sort alphanumeric/numeric strings directly
    if (sortBy.value === 'position') {
      allPositions.value.sort((a, b) => {
        const aPos = Number(a.position) || 0;
        const bPos = Number(b.position) || 0;
        return sortDesc.value ? bPos - aPos : aPos - bPos;
      });
      selected_positions.value = [...allPositions.value];
    }
  } catch (error) {
    console.error('Error finding position page:', error);
  } finally {
    searching.value = false;
  }
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  // Reset pagination and reload data with new sorting
  currentPage.value = 1;
  hasMorePositions.value = true;
  allPositions.value = [];
  getPositions(1, false);
}

// Refresh positions when search term changes (backend search)
watch(positionSearch, () => {
  currentPage.value = 1;
  hasMorePositions.value = true;
  getPositions(1, false);
});

const isValid = () => {
  if (name.value == '' || name.value == null) return false;
  if (token.value == '' || token.value == null) return false;
  if (selected_zone.value == null) return false;
  
  return true;
}

const getZones = async () => {
  const result = await $RouteApiService.getRouteZones();

  zones.value = [];

  result.forEach(zone => {
    zones.value.push({
      label: zone.name,
      code: zone.id
    })
  });

  loading_zones.value = false;
};

const updateSelectedZone = (e) => {
  selected_zone.value = e;
  selected_zone_id.value = e?.code || null;

};

const openRegion = (region, data = null) => {
  closeAllRegions();

  if (region == 'zone') {
    editingZone.value = true;
  }
  else if (region == 'position') {
    editingPositions.value = true;
    editingPosition.value = data;
  }
  showRegion.value = true;
};

const openPositionInsert = (idx) => {
  openRegion('position');          // closeAllRegions() resets insertAfterIndex first
  insertAfterIndex.value = idx;    // set it after the reset
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}
const createZone = () => {
  selected_zone_id.value = null;
  selected_zone.value = null;
  openRegion('zone');

}
const editZone = () => {
  openRegion('zone');
}

const newZone = async (new_zone) => {
  zone.value = new_zone;
  await getZones();
  selected_zone.value = {
    label: new_zone.name,
    code: new_zone.id
  }
  selected_zone_id.value = new_zone.id;

  closeAllRegions();
};

const reordering = ref(false);

// Arrossegar una posició reordena la llista. La nova posició "objectiu" que
// enviem al backend és la del veí adjacent en l'ordre resultant (el que ja
// no s'ha mogut): l'endpoint /move/ ja s'encarrega de desplaçar en cadena
// (+1/-1) totes les posicions intermèdies fins trobar un espai lliure.
const onDraggableEnd = async (event) => {
  const { oldIndex, newIndex } = event;
  if (oldIndex === newIndex) return;

  const draggedItem = allPositions.value[newIndex];
  if (!draggedItem) return;

  const neighbor = newIndex > oldIndex
    ? allPositions.value[newIndex - 1]
    : allPositions.value[newIndex + 1];

  const targetPosition = Number(neighbor?.position) || 0;

  if (!draggedItem.id) {
    // Posició encara no desada (alta manual pendent): només ajustem l'ordre local
    draggedItem.position = targetPosition;
    draggedItem.is_edited = true;
    if (!selected_positions_to_add.value.has(draggedItem)) {
      selected_positions_to_add.value.add(draggedItem);
    }
    return;
  }

  reordering.value = true;
  try {
    await $RouteApiService.moveRoutePosition(draggedItem.id, targetPosition, props.route.id);
  } catch (error) {
    console.error('Error movent la posició de ruta:', error);
  } finally {
    // Recarreguem des del backend: pot haver desplaçat en cadena altres
    // posicions (i, per a certs clients, actualitzat l'Ident. de les finques).
    currentPage.value = 1;
    hasMorePositions.value = true;
    allPositions.value = [];
    await getPositions(1, false);
    reordering.value = false;
  }
}

const newPosition = async (position) => {
  // Only shift the contiguous occupied block starting at the insertion point.
  // Stop at the first free gap — positions beyond a gap don't need to move.
  const hasConflict = allPositions.value.some(p => Number(p.position) === Number(position.position));
  if (editingPosition.value === null && hasConflict) {
    const threshold = Number(position.position) || 0;
    const positionSet = new Set(allPositions.value.map(p => Number(p.position)));
    // Find the upper bound of the contiguous occupied range starting at threshold
    let limit = threshold;
    while (positionSet.has(limit)) {
      limit++;
    }
    // limit is now the first free slot — only shift positions in [threshold, limit - 1]
    allPositions.value.forEach(p => {
      const pPos = Number(p.position) || 0;
      if (pPos >= threshold && pPos < limit) {
        p.position = pPos + 1;
        p.is_edited = true;
        if (!selected_positions_to_add.value.has(p)) {
          selected_positions_to_add.value.add(p);
        }
        if (!p.is_new) {
          const editIdx = editedPositions.value.findIndex(ep => ep.id === p.id);
          if (editIdx !== -1) {
            editedPositions.value[editIdx] = { ...editedPositions.value[editIdx], position: p.position };
          } else {
            editedPositions.value.push({ ...p });
          }
        }
      }
    });
    insertAfterIndex.value = null;
  }

  if (editingPosition.value != null) {
    // When changing to an already-occupied position, shift that block forward
    const isSameItem = (p) => p.id ? p.id === position.id : p.token === position.token;
    const conflictWithOther = allPositions.value.some(p => !isSameItem(p) && Number(p.position) === Number(position.position));
    if (conflictWithOther) {
      const threshold = Number(position.position) || 0;
      const positionSet = new Set(
        allPositions.value.filter(p => !isSameItem(p)).map(p => Number(p.position))
      );
      let limit = threshold;
      while (positionSet.has(limit)) { limit++; }
      allPositions.value.forEach(p => {
        if (isSameItem(p)) return;
        const pPos = Number(p.position) || 0;
        if (pPos >= threshold && pPos < limit) {
          p.position = pPos + 1;
          p.is_edited = true;
          if (!selected_positions_to_add.value.has(p)) {
            selected_positions_to_add.value.add(p);
          }
          if (!p.is_new) {
            const editIdx = editedPositions.value.findIndex(ep => ep.id === p.id);
            if (editIdx !== -1) {
              editedPositions.value[editIdx] = { ...editedPositions.value[editIdx], position: p.position };
            } else {
              editedPositions.value.push({ ...p });
            }
          }
        }
      });
    }

    // Has been edited
    const editIdx = editedPositions.value.findIndex(p => p.id === position.id);
    if (editIdx !== -1) {
      editedPositions.value[editIdx] = position;
    } else {
      editedPositions.value.push(position);
    }
    
    // Also remove from newPositions if it happened to be there and was edited again
    const newIdx = newPositions.value.findIndex(p => p.id === position.id);
    if (newIdx !== -1) {
      newPositions.value[newIdx] = position;
    }

    const idx = allPositions.value.findIndex(p => (p.id && p.id === position.id) || p.token === position.token);
    
    let minLoaded = Infinity;
    let maxLoaded = -Infinity;
    allPositions.value.forEach(p => {
       const posNum = Number(p.position) || 0;
       if (posNum < minLoaded) minLoaded = posNum;
       if (posNum > maxLoaded) maxLoaded = posNum;
    });

    const newPosNum = Number(position.position) || 0;
    // Only hide if it's ABOVE the loaded range (will appear when scrolling down).
    // If it's BELOW minLoaded it must always be shown at the top.
    const isAboveLoadedRange = allPositions.value.length > 0 && newPosNum > maxLoaded;

    if (isAboveLoadedRange && hasMorePositions.value) {
      if (idx !== -1) {
        allPositions.value.splice(idx, 1);
        selected_positions.value = [...allPositions.value];
      }
    } else {
      if (idx !== -1) {
        allPositions.value[idx] = position;

        // RE-SORT locally if it was already in the list but changed position
        if (sortBy.value === 'position') {
          allPositions.value.sort((a, b) => (Number(a.position) || 0) - (Number(b.position) || 0));
          selected_positions.value = [...allPositions.value];
        }
      }
      // else: position is outside the loaded range — it will appear when user scrolls to it
    }
  } else {
    // New position added
    const newIdx = newPositions.value.findIndex(p => p.id === position.id);
    if (newIdx !== -1) {
      newPositions.value[newIdx] = position;
    } else {
      newPositions.value.push(position);
    }

    // Only skip if position is above the loaded range and there are more pages to load.
    // Positions below the minimum must always be shown at the top.
    const alreadyLoaded = allPositions.value.some(p => p.id === position.id);
    if (!alreadyLoaded && allPositions.value.length > 0) {
      const maxLoaded = Math.max(...allPositions.value.map(p => Number(p.position) || 0));
      const newPosNum = Number(position.position) || 0;
      if (newPosNum <= maxLoaded || !hasMorePositions.value) {
        allPositions.value.push(position);
        allPositions.value.sort((a, b) => (Number(a.position) || 0) - (Number(b.position) || 0));
        selected_positions.value = [...allPositions.value];
      }
    }
  }

  closeAllRegions();

  // Scroll to the position only if it's not already visible in the container
  setTimeout(() => {
    const elementId = `pos-${position.id || position.token}`;
    const element = document.getElementById(elementId);
    if (element) {
      const scrollContainer = document.querySelector('.dragArea');
      const isVisible = scrollContainer
        ? element.offsetTop >= scrollContainer.scrollTop &&
          element.offsetTop + element.offsetHeight <= scrollContainer.scrollTop + scrollContainer.clientHeight
        : false;

      if (!isVisible) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }

      element.style.transition = 'background-color 0.5s ease';
      element.style.backgroundColor = '#fef08a';
      setTimeout(() => {
        element.style.backgroundColor = '';
      }, 3000);
    }
  }, 800);
}

const editPosition = (pos) => {
  openRegion('position', pos);
}

const loadPositions = (positions) => {
  allPositions.value = []
  selected_positions.value = []

  const removedIds = selected_positions_to_remove.value.map(p => p.id).filter(id => id != null);

  positions.forEach((position, index) => {
    if (!removedIds.includes(position.id)) {
      // position.position = index + 1; // Don't overwrite if it comes from edit
      allPositions.value.push(position);
      selected_positions.value.push(position);
    }
  });

  setTimeout(() => {
    closeAllRegions();
  }, 200)
}

const removePosition = (pos) => {
  // Try to remove from visual lists
  const allIdx = allPositions.value.findIndex(sp => sp.token == pos.token);
  if (allIdx !== -1) {
    allPositions.value.splice(allIdx, 1);
  }

  const newIdx = newPositions.value.findIndex(sp => sp.token == pos.token);
  if (newIdx !== -1) {
    newPositions.value.splice(newIdx, 1);
  }

  const editIdx = editedPositions.value.findIndex(sp => sp.token == pos.token);
  if (editIdx !== -1) {
    editedPositions.value.splice(editIdx, 1);
  }

  // Evitar enviar add+remove simultani si la posició s'havia afegit en aquesta sessió
  for (const item of selected_positions_to_add.value) {
    if (item.token == pos.token) {
      selected_positions_to_add.value.delete(item);
      break;
    }
  }

  selected_positions.value = [...allPositions.value];
  selected_positions_to_remove.value.push(pos);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const closeAllRegions = () => {
  // tanquem tots els components
  editingPositions.value = false;
  editingZone.value = false;
  editingPosition.value = null;
  isSubRegionOpen.value = false;
  insertAfterIndex.value = null;

  // tanquem region
  showRegion.value = false;
};

// Infinite scroll handler
const handleScroll = () => {
  const scrollContainer = document.querySelector('.dragArea');
  if (!scrollContainer) return;
  
  const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
  const threshold = 100; // Load more when 100px from bottom
  
  if (scrollHeight - scrollTop <= clientHeight + threshold) {
    loadMorePositions();
  }
};

// Add scroll listener for infinite scroll
const setupScrollListener = () => {
  nextTick(() => {
    const scrollContainer = document.querySelector('.dragArea');
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', handleScroll);
    }
  });
};

// Remove scroll listener when component unmounts
const removeScrollListener = () => {
  const scrollContainer = document.querySelector('.dragArea');
  if (scrollContainer) {
    scrollContainer.removeEventListener('scroll', handleScroll);
  }
};

const scrollToPosition = (positionNum) => {
  const target = allPositions.value.find(p => Number(p.position) === Number(positionNum));
  if (!target) return;

  nextTick(() => {
    const elementId = `pos-${target.id || target.token}`;
    const element = document.getElementById(elementId);
    if (!element) return;

    const scrollContainer = document.querySelector('.dragArea');
    const isVisible = scrollContainer
      ? element.offsetTop >= scrollContainer.scrollTop &&
        element.offsetTop + element.offsetHeight <= scrollContainer.scrollTop + scrollContainer.clientHeight
      : false;

    if (!isVisible) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    element.style.transition = 'outline 0.4s ease';
    element.style.outline = '2px solid #38bdf8';
    setTimeout(() => { element.style.outline = ''; }, 2000);
  });
};

onMounted(() => {
  getData()
});

onUnmounted(() => {
  removeScrollListener();
});

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div v-if="loading">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="border border-gray-300 rounded p-4 bg-white">
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
          <input :disabled="route != null" type="text" v-model="token" class="input"
            :class="{ 'invalid': attemptedSave && (token == '' || attemptedSave && token == null) }" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="name" class="input"
            :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }" />
        </div>

        <div class="mb-2">
          <div class="field">
            <div class="flex">
              <label for="Zone" class="pt-2 text-gray-700 mb-2">{{ $t('service_block.zone') }}</label>
            </div>
          </div>
          <div class="flex">
            <v-select class="block w-full mr-1 required" :disable="loading_zones" :model-value="selected_zone"
              @update:modelValue="updateSelectedZone" :options="zones"
              :class="{ 'invalid': attemptedSave && selected_zone == null }"></v-select>
            <button
              class="w-9 h-9 border-gray-300 mr-1 border rounded text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200 flex items-center justify-center"
              @click="editZone" :disabled="selected_zone == null"><Icon class="text-md"
                name="fa6-solid:pencil" /></button>
            <button
              class="w-9 h-9 border-gray-300 border rounded enabled:hover:bg-slate-200 transition-all duration-200 flex items-center justify-center"
              @click="createZone"><Icon name="fa6-solid:plus" class="text-md text-slate-600" /></button>
          </div>
        </div>
        <hr class="mb-2 col-span-2" />

        <!-- Local changes summary (new vs edited) -->
        <div class="mb-2 row col-span-2 gap-3">
          <div class="flex items-center justify-between">
            <div class="field">
              <div class="flex">
                <label class="pt-2 text-slate-500 mb-2">{{ t('common.modifications') }}</label>
              </div>
            </div>
          </div>

          <AtomsTabs>
            <li class="me-2">
              <a href="#tab_new_positions" @click.prevent="changesTab = 'new'"
                :class="{ 'text-sky-600 border-sky-600': changesTab === 'new', 'hover:text-gray-600 hover:border-gray-300': changesTab !== 'new' }">
                <Icon name="fa6-solid:plus" class="display-inline mr-2" />
                {{ t('common.manually_added') }} ({{ newPositions.length }})
              </a>
            </li>
            <li class="me-2">
              <a href="#tab_edited_positions" @click.prevent="changesTab = 'edited'"
                :class="{ 'text-sky-600 border-sky-600': changesTab === 'edited', 'hover:text-gray-600 hover:border-gray-300': changesTab !== 'edited' }">
                <Icon name="fa6-solid:pen" class="display-inline mr-2" />
                {{ t('common.manually_modified') }} ({{ editedPositions.length }})
              </a>
            </li>
            <li class="me-2">
              <a href="#tab_removed_positions" @click.prevent="changesTab = 'removed'"
                :class="{ 'text-sky-600 border-sky-600': changesTab === 'removed', 'hover:text-gray-600 hover:border-gray-300': changesTab !== 'removed' }">
                <Icon name="fa6-solid:trash-can" class="display-inline mr-2" />
                {{ t('common.manually_deleted') }} ({{ selected_positions_to_remove.length }})
              </a>
            </li>
          </AtomsTabs>

          <div class="text-gray-900 rounded shadow">
            <div v-if="activeChanges.length > 0"
              class="group grid grid-cols-[0.5fr,1.5fr,1.5fr,2.5fr] divide-x text-sm text-center border-b leading-4 ">
              <span class="p-1 text-slate-400">{{ t('order') }}</span>
              <span class="p-1 text-slate-400">{{ t('common.identification') }}</span>
              <span class="p-1 text-slate-400">{{ t('common.name') }}</span>
              <span class="p-1 text-slate-400">{{ t('common.properties') }}</span>
            </div>

            <div v-if="activeChanges.length === 0" class="p-3 text-center text-slate-400 text-sm">
              {{ t('common.no_changes') }}
            </div>

            <div v-for="element in activeChanges" :key="element.id || element.token"
              class="group grid grid-cols-[0.5fr,1.5fr,1.5fr,2.5fr] divide-x text-sm text-center leading-4 border-b transition-all duration-300"
              :class="{ 'bg-yellow-50': element.is_new, 'bg-sky-50': element.is_edited && !element.is_new, 'bg-red-50': changesTab === 'removed' }">
              <div class="p-2 text-slate-800">{{ element.position }}</div>
              <div class="p-2 text-slate-800">{{ element.token }}</div>
              <div class="p-2 text-slate-800">{{ element.name || '-' }}</div>
              <div class="p-2 text-slate-800 relative">
                <template v-if="element._properties_display">
                  <span v-for="(prop, i) in element._properties_display" :key="i">{{ i > 0 ? ', ' : '' }}{{ prop }}</span>
                </template>
                <template v-else-if="element.properties && element.properties.length > 0">
                  <template v-if="typeof element.properties[0] === 'object'">
                    <span v-for="(prop, i) in element.properties" :key="prop.id">
                      {{ i > 0 ? ', ' : '' }}{{ prop.name || [prop.address_street?.name, prop.address_street_number?.name, prop.address_city?.name].filter(Boolean).join(' ') || prop.token }}
                    </span>
                  </template>
                  <template v-else>
                    <span v-for="(prop, i) in element.properties" :key="i">{{ i > 0 ? ', ' : '' }}{{ prop }}</span>
                  </template>
                </template>
                <span v-else class="text-slate-400">-</span>
                <div v-if="changesTab !== 'removed'" class="absolute right-1 top-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-all duration-300">
                  <button
                    class="cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white rounded-md text-slate-600 hover:text-sky-700 focus:border-none focus:outline-none"
                    @click="editPosition(element)">
                    <Icon name="fa6-solid:pencil" />
                  </button>
                  <button
                    class="cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white rounded-md text-slate-600 hover:text-red-700 focus:border-none focus:outline-none"
                    @click="removePosition(element)">
                    <Icon name="fa6-solid:trash" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="mb-2 row col-span-2 gap-3">
          <div class="field">
            <div class="flex">
              <label for="positions" class="pt-2 text-slate-500 mb-2">{{ $t('common.positions') }}</label>
            </div>
          </div>
          <form role="search"
            class="mb-2 text-base border-b border-gray-200 flex flex-start gap-4 justify-start items-center"
            @submit.prevent>
            <span class="input-group flex flex-start items-center gap-2 w-80">
              <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
              <input v-model="positionSearch" type="text" name="search"
                :placeholder="$t('dashboard.search')"
                class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
                autocomplete="off" />
            </span>
          </form>
          <div :class="{ 'mt-1': allPositions.length == 0 }" class="text-gray-900 rounded shadow">
            <div v-show="searching" class="p-4 bg-yellow-50 text-center flex items-center justify-center gap-2 border-b">
              <Icon name="fa6-solid:spinner" class="animate-spin text-sky-600" />
              <span class="text-sm text-slate-600">{{ t('common.loading') }}...</span>
            </div>
            <div v-if="allPositions.length > 0"
              class="group grid grid-cols-[0.5fr,1.5fr,1.5fr,2.5fr] divide-x text-sm text-center border-b leading-4 ">
              <span class="p-1 text-slate-400 cursor-pointer hover:text-slate-600 transition-colors duration-200 flex items-center justify-center gap-1"
                @click="handleSort('position')">
                {{ t('order') }}
                <Icon v-if="sortBy === 'position'" 
                  :name="sortDesc ? 'fa6-solid:arrow-down' : 'fa6-solid:arrow-up'" 
                  class="text-xs" />
                <Icon v-else name="fa6-solid:sort" class="text-xs opacity-50" />
              </span>
              <span class="p-1 text-slate-400 cursor-pointer hover:text-slate-600 transition-colors duration-200 flex items-center justify-center gap-1"
                @click="handleSort('token')">
                {{ t('common.identification') }}
                <Icon v-if="sortBy === 'token'" 
                  :name="sortDesc ? 'fa6-solid:arrow-down' : 'fa6-solid:arrow-up'" 
                  class="text-xs" />
                <Icon v-else name="fa6-solid:sort" class="text-xs opacity-50" />
              </span>
              <span class="p-1 text-slate-400 cursor-pointer hover:text-slate-600 transition-colors duration-200 flex items-center justify-center gap-1"
                @click="handleSort('name')">
                {{ t('common.name') }}
                <Icon v-if="sortBy === 'name'" 
                  :name="sortDesc ? 'fa6-solid:arrow-down' : 'fa6-solid:arrow-up'" 
                  class="text-xs" />
                <Icon v-else name="fa6-solid:sort" class="text-xs opacity-50" />
              </span>
              <span class="p-1 text-slate-400 cursor-pointer hover:text-slate-600 transition-colors duration-200 flex items-center justify-center gap-1"
                @click="handleSort('properties')">
                {{ t('common.properties') }}
                <Icon v-if="sortBy === 'properties'" 
                  :name="sortDesc ? 'fa6-solid:arrow-down' : 'fa6-solid:arrow-up'" 
                  class="text-xs" />
                <Icon v-else name="fa6-solid:sort" class="text-xs opacity-50" />
              </span>
            </div>

            <div class="dragArea max-h-96 overflow-y-auto">
              <template v-if="!hasPositionSearch">
                <!-- Insert-before-first button -->
                <div class="relative h-1 flex items-center justify-center group/insert cursor-pointer z-10"
                  @click="openPositionInsert(-1)">
                  <div class="absolute inset-x-0 h-1 bg-sky-400 opacity-0 group-hover/insert:opacity-100 transition-opacity duration-150"></div>
                  <button class="absolute bg-white border border-sky-400 text-sky-500 rounded-full w-6 h-6 flex items-center justify-center opacity-0 group-hover/insert:opacity-100 transition-opacity duration-150 hover:bg-sky-50 shadow-sm z-20"
                    title="Insertar posició aquí">
                    <Icon name="fa6-solid:plus" class="text-[10px]" />
                  </button>
                </div>
                <Draggable v-model="allPositions" :item-key="p => p.id || p.token" handle=".drag-handle" tag="div"
                  :options="{ animation: 200, filter: '.no-drag', preventOnFilter: false, disabled: sortBy !== 'position' }"
                  @end="onDraggableEnd">
                  <template #item="{ element, index }">
                    <div>
                      <div class="group grid grid-cols-[0.5fr,1.5fr,1.5fr,2.5fr] divide-x text-sm text-center leading-4 border-b transition-all duration-300"
                        :class="{ 'bg-yellow-50': element.is_new }"
                        :id="'pos-' + (element.id || element.token)">
                        <div class="p-2 text-slate-800 flex">
                          <span class="drag-handle text-slate-400 hover:text-slate-600 px-1"
                            :class="sortBy === 'position' ? 'cursor-move' : 'opacity-30 cursor-not-allowed'"
                            :title="sortBy === 'position' ? t('common.reorder') : ''">
                            <Icon name="fa6-solid:grip-vertical" />
                          </span>
                          <div class="pl-1">
                            {{ element.position }}
                          </div>
                        </div>
                        <div class="p-2 text-slate-800">{{ element.token }}</div>
                        <div class="p-2 text-slate-800">{{ element.name || '-' }}</div>
                        <div class="p-2 text-slate-800 relative">
                          <template v-if="element._properties_display">
                            <span v-for="(prop, i) in element._properties_display" :key="i">{{ i > 0 ? ', ' : '' }}{{ prop }}</span>
                          </template>
                          <template v-else-if="element.properties && element.properties.length > 0">
                            <template v-if="typeof element.properties[0] === 'object'">
                              <span v-for="(prop, i) in element.properties" :key="prop.id">
                                {{ i > 0 ? ', ' : '' }}{{ prop.name || [prop.address_street?.name, prop.address_street_number?.name, prop.address_city?.name].filter(Boolean).join(' ') || prop.token }}
                              </span>
                            </template>
                            <template v-else>
                              <span v-for="(prop, i) in element.properties" :key="i">{{ i > 0 ? ', ' : '' }}{{ prop }}</span>
                            </template>
                          </template>
                          <span v-else class="text-slate-400">-</span>
                          <div class="absolute right-1 top-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-all duration-300">
                            <button
                              class="cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white rounded-md text-slate-600 hover:text-sky-700 focus:border-none focus:outline-none"
                              @click="editPosition(element)">
                              <Icon name="fa6-solid:pencil" />
                            </button>
                            <button
                              class="cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white rounded-md text-slate-600 hover:text-red-700 focus:border-none focus:outline-none"
                              @click="removePosition(element)">
                              <Icon name="fa6-solid:trash" />
                            </button>
                          </div>
                        </div>
                      </div>
                      <!-- Insert-after-row button (exclosa del drag&drop amb .no-drag) -->
                      <div class="no-drag relative h-1 flex items-center justify-center group/insert cursor-pointer z-10"
                        @click="openPositionInsert(index)">
                        <div class="absolute inset-x-0 h-1 bg-sky-400 opacity-0 group-hover/insert:opacity-100 transition-opacity duration-150"></div>
                        <button class="absolute bg-white border border-sky-400 text-sky-500 rounded-full w-6 h-6 flex items-center justify-center opacity-0 group-hover/insert:opacity-100 transition-opacity duration-150 hover:bg-sky-50 shadow-sm z-20"
                          title="Insertar posició aquí">
                          <Icon name="fa6-solid:plus" class="text-[10px]" />
                        </button>
                      </div>
                    </div>
                  </template>
                </Draggable>
                <div v-if="reordering" class="flex justify-center items-center py-2 text-sky-600 text-sm gap-2">
                  <Icon name="fa6-solid:spinner" class="animate-spin" />
                  {{ t('common.saving') }}...
                </div>
              </template>
              <template v-else>
                <div v-for="element in filteredPositions" :key="element.id || element.token"
                  class="group grid grid-cols-[0.5fr,1.5fr,1.5fr,2.5fr] divide-x text-sm text-center leading-4 border-b transition-all duration-300"
                  :class="{ 'bg-yellow-50': element.is_new }"
                  :id="'pos-' + (element.id || element.token)">
                  <div class="p-2 text-slate-800 flex">
                    <div class="pl-1">
                      {{ element.position }}
                    </div>
                  </div>
                  <div class="p-2 text-slate-800">{{ element.token }}</div>
                  <div class="p-2 text-slate-800">{{ element.name || '-' }}</div>
                  <div class="p-2 text-slate-800 relative">
                    <template v-if="element._properties_display">
                      <span v-for="(prop, i) in element._properties_display" :key="i">{{ i > 0 ? ', ' : '' }}{{ prop }}</span>
                    </template>
                    <template v-else-if="element.properties && element.properties.length > 0">
                      <template v-if="typeof element.properties[0] === 'object'">
                        <span v-for="(prop, i) in element.properties" :key="prop.id">
                          {{ i > 0 ? ', ' : '' }}{{ prop.name || [prop.address_street?.name, prop.address_street_number?.name, prop.address_city?.name].filter(Boolean).join(' ') || prop.token }}
                        </span>
                      </template>
                      <template v-else>
                        <span v-for="(prop, i) in element.properties" :key="i">{{ i > 0 ? ', ' : '' }}{{ prop }}</span>
                      </template>
                    </template>
                    <span v-else class="text-slate-400">-</span>
                    <div class="absolute right-1 top-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-all duration-300">
                      <button
                        class="cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white rounded-md text-slate-600 hover:text-sky-700 focus:border-none focus:outline-none"
                        @click="editPosition(element)">
                        <Icon name="fa6-solid:pencil" />
                      </button>
                      <button
                        class="cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white rounded-md text-slate-600 hover:text-red-700 focus:border-none focus:outline-none"
                        @click="removePosition(element)">
                        <Icon name="fa6-solid:trash" />
                      </button>
                    </div>
                  </div>
                </div>
              </template>
              <div v-if="allPositions.length === 0 && !isLoadingMore && !searching" class="p-8 text-center text-slate-400">
                <Icon name="fa6-solid:circle-info" class="text-2xl mb-2 opacity-20" />
                <p>{{ t('common.no_results') }}</p>
              </div>
              <!-- Loading indicator for infinite scroll -->
              <div v-if="isLoadingMore" class="flex justify-center items-center py-4">
                <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500 mr-2" />
                <span class="text-slate-500">{{ $t('common.loading') }}...</span>
              </div>
              
              <!-- End of results indicator -->
              <div v-if="!hasMorePositions && allPositions.length > 0" class="text-center py-2 text-slate-400 text-sm">
                {{ $t('common.all_data_loaded') }}
              </div>
            </div>
            
            <div class="footering">
              <button @click="openRegion('position')"
                :class="{ 'invalid': attemptedSave && allPositions.length == 0 }"
                class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
                <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}</button>
            </div>
          </div>
        </div>

        <div class="col-span-2 flex flex-row-reverse mt-4">
          <button v-if="route != null" @click="deleteRoute" :disabled="saving" class="button-default mx-5">
            &nbsp; {{ $t('common.delete') }}</button>
          <button @click="save" :disabled="saving" class="button-primary"><Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}</button>
        </div>

      </div>

    </div>
    <div role="region" id="right_page"
      class="fixed h-screen overflow-hidden border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 rounded active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" /></button>
      </div>
      <div class="h-full" :class="{ 'overflow-y-auto px-10 pb-24': !editingPositions }">
        <div :class="{ 'px-10 pb-24 h-full': editingPositions }">
          <OrganismsAddRoutePosition v-if="editingPositions" :routeToken="token+''" :selectedOptions="selected_positions" @selected="loadPositions"
            :numPositions="totalPositionsCount" :isSubRegionOpen="isSubRegionOpen" :route_id="props.route?.id" @created="newPosition"
            :editingPosition="editingPosition" :insertAfterPosition="insertAfterPositionValue"
            @removePosition="removePosition" @show-subregion="handleSubRegionEvent"
            @preview-position="scrollToPosition" />
          <MoleculesAddRouteZone :id="null" v-if="editingZone" :zone_id="selected_zone_id" @new-zone="newZone" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sortable-chosen {
  @apply bg-yellow-100
}
</style>
