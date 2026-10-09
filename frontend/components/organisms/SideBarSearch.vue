<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useSidebarStore } from '~/stores/useNavSideBar';
import debounce from 'lodash.debounce';
import { formatDate, formatDateTime } from '~/utils/date';
import Skeleton from '../atoms/Skeleton.vue';
import { searchValues, foundItemTranslation } from '~/utils/search';
import TimeRelative from '~/components/atoms/TimeRelative.vue';
import { format } from 'date-fns';

const sidebarStore = useSidebarStore();
const { t } = useI18n();
const route = useRoute()
const router = useRouter()

const searchTerm = ref('');
const searchResults = ref([]);
const searchOptions = ref([])
const currentSearch = ref(null);
const currentResult = ref(null);

const searchHistory = ref([]);
const groupedSearchHistory = ref({});

const loading = ref(false);
const isHover = ref(false);
const isFound = ref(true);
const isSearching = ref(false);
const entityFilter = ref([]);

const isFiltered = ref(false);
const selectedFilter = ref('-');

const page = ref(1);
const pageSize = 20;
const hasNextPage = ref(true);
const loadingMore = ref(false);
const allDataLoaded = ref(false);

const scrollPosition = ref(0); // Store the scroll position
const scrollContainer = ref(null); // Reference to the scrollable container

const { $SearchApiService } = useNuxtApp();

const getData = debounce(async (load = true) => {
  isSearching.value = true
  loading.value = load;
  loadingMore.value = true;
  try {
    const data = await $SearchApiService.getSearch(searchTerm.value, entityFilter.value[0], page.value);

    if (data.results && data.results.length > 0) {
      if (!data.has_next) {
        hasNextPage.value = false;
      }

      if (page.value === 1) {
        searchResults.value = data.results;
        
        const foundEntities = new Set(data.results.map(result => result.entity));
        searchOptions.value = Object.keys(searchValues)
          .filter(key => foundEntities.has(key))
          .map(key => ({
            id: key,
            name: ('sidebar_search_block.' + key.toLowerCase().replace(/-/g, '_')),
          }))
          .sort((a, b) => a.name.localeCompare(b.name));
        searchOptions.value.unshift({ id: '-', name: ("common.no_filter") });
      } else {
        searchResults.value = searchResults.value.concat(data.results);
        
        const currentEntities = new Set(searchOptions.value.map(opt => opt.id));
        const newEntities = data.results
          .filter(result => !currentEntities.has(result.entity))
          .map(result => result.entity);
        
        if (newEntities.length > 0) {
          const newOptions = newEntities.map(entity => ({
            id: entity,
            name: ('sidebar_search_block.' + entity.toLowerCase().replace(/-/g, '_')),
          }));
          searchOptions.value = [...searchOptions.value, ...newOptions]
            .sort((a, b) => a.name.localeCompare(b.name));
        }
      }

      if (data.results.length < pageSize || !hasNextPage.value) {
        allDataLoaded.value = true;
      }
      
      page.value++; 
    } else {
      if (page.value === 1) {
        searchResults.value = [];
        isFound.value = false;
      }
      allDataLoaded.value = true;
    }

  } catch (error) {
    console.error(`Error fetching:`, error);
  } finally {
    loading.value = false;
    loadingMore.value = false;
    isSearching.value = false;
    nextTick(() => {
      if (scrollContainer.value) {
        scrollContainer.value.scrollTop = scrollPosition.value;
      }
    });
  }
}, 200);

const onScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  scrollPosition.value = scrollTop; // Update the scroll position
  if (!hasNextPage.value || loadingMore.value) return;
  if (scrollHeight - scrollTop <= clientHeight + 50) {
    getData(false);
  }
};

const getHistoryData = async () => {
  isSearching.value = false
  try {
    const data = await $SearchApiService.getSearchHistory(searchTerm.value);
    const groupedData = data.results.reduce((acc, item) => {
      const dateKey = format(new Date(item.searched_at), 'yyyy-MM-dd');

      if (!acc[dateKey]) {
        acc[dateKey] = [];
      }
      acc[dateKey].push(item);
      return acc;
    }, {});
    groupedSearchHistory.value = groupedData;
  } catch (error) {
    console.error(`Error fetching:`, error);
  }
}

const handleSearch = (term) => {
  searchTerm.value = term;
  console.log('handleSearch', term);
  if (term.length > 2) {
    page.value = 1; // Reset page when starting a new search
    hasNextPage.value = true; 
    allDataLoaded.value = false;
    getData();
  } else {
    searchResults.value = [];
    selectedFilter.value = '-';
    isFiltered.value = false;
    getHistoryData()
    getSearchOptions()
  }
};

const getSearchOptions = () => {
  try {
    searchOptions.value = Object.keys(searchValues).map(key => {
      return {
        id: key,
        name: ('sidebar_search_block.' + key.toLowerCase().replace(/-/g, '_')),
      }
    })
    searchOptions.value.sort((a, b) => a.name.localeCompare(b.name));
    searchOptions.value.unshift({ id: '-', name: ("common.no_filter") });
  } catch (e) {
    console.log(e)
  }
}

const getItemTranslation = (item) => {
  //const translation = foundItemTranslation(item, 'cat');
  const translation = t('sidebar_search_block.' + item.toLowerCase());
  return translation;
};


const highlightedResult = (result) => {
  /* result_words = result.split(' ')
  search_words = searchTerm.value.split(' ') */
  let highlighted = result.toString().replace(new RegExp(searchTerm.value, 'gi'), '<span class="font-extrabold italic">$&</span>')
  /* for (let word of search_words) {
    highlighted = highlighted.replace(new RegExp(word, 'gi'), '<span class="font-extrabold italic">$&</span>')
  } */
  return highlighted
};


/* const handleHover = debounce(async (event) => {
  currentSearch.value = event;
  const result = await $SearchApiService.getData(event.app.toLowerCase(), event.entity.toLowerCase(), event.item_id)
  currentResult.value = result
  console.log(result)
  console.log(currentResult)
}, 200) */

const handleClick = (event) => {
  try {
    let pathName = '/' + event.app.toLowerCase() + '/' + searchValues[event.entity][0] + '/';
    sidebarStore.closeSearch()

    saveSearchHistory(event)
    /* if (location.pathname == pathName) {
      location.replace(location.pathname + "?action=showDetail&id=" + event.item_id)
    } */

    navigateTo({
      path: pathName,
      query: {
        action: 'showDetail',
        id: event.item_id,
      }
    })
  } catch (error) {
    console.error(error)
  }
}

const handleFiltersChange = (event) => {
  entityFilter.value = []
  selectedFilter.value = event[0].id;
  if (event[0].id === '-') {
    handleSearch(searchTerm.value)
    return
  }
  event.forEach(element => {
    entityFilter.value.push(element.id);
  })
  handleSearch(searchTerm.value)
}

const saveSearchHistory = async (event) => {
  console.log(event)
  try {
    let data = {
      app: event.app,
      query: event.search,
      found: event.found,
      entity: event.entity,
      item_id: event.item_id,
      found_field: event.found_field
    }
    await $SearchApiService.saveSearchHistory(data)
  } catch (error) {
    console.error(error)
  }
}

const getSlicedName = (name) => {
  if (name.length > 20) {
    return name.slice(0, 20) + '...';
  } else {
    return name;
  }
}

const handleClose = () => {
  searchTerm.value = '';
  searchResults.value = [];
  sidebarStore.isSearchOpen = false;
};

onMounted(() => {
  if (document.getElementById('initFocus')) {
    document.getElementById('initFocus').focus();
  }
  getHistoryData()
  getSearchOptions()
});


</script>

<template>
  <div class="fixed inset-0 bg-gray-900 bg-opacity-50 z-50 flex items-center justify-center transition-opacity"
    v-if="sidebarStore.isSearchOpen" @click="handleClose">
    <div class="bg-white w-[50%] h-[78%] px-4 py-2 shadow-xl z-60 transform transition-transform rounded-xl "
      @click.stop>
      <div class="border-b flex items-center">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500 mr-2" />
        <input type="text" id="initFocus" v-model="searchTerm" @input="handleSearch(searchTerm)"
          :placeholder="t('dashboard.search')" autocomplete="off"
          class="type-hidden w-full p-2 rounded-md focus:outline-none focus-visible:border-0" />

        <button v-if="isSearching" @click="isFiltered = !isFiltered"
          class="p-1 mx-2 text-sm font-medium border border-transparent rounded-3xl transition duration-200 ease-in-out"
          :class="isFiltered?'text-sky-500':'text-slate-700 '">
          <Icon  name="fa6-solid:filter" class="text-md mx-1" size="15px" />
        </button>
      </div>
      <AtomsTabs v-if="isFiltered && isSearching" class="rounded-lg bg-white" :is_tab="false">
        <template v-for="(filter, index) in searchOptions" :key="index"
          class="flex items-center justify-between overflow-hidden max-w-full ">
          <div class="flex items-center justify-center h-[45px]">
            <button
              class="px-2 mx-2 text-sm font-medium  border border-transparent rounded-3xl  transition duration-200 ease-in-out"
              :aria-label="'Filter by ' + filter.name" @click="handleFiltersChange([filter])"
              :class="selectedFilter === filter.id?'border border-sky-500 bg-sky-50 hover:bg-sky-400 hover:text-white text-sky-600 rounded-3xl font-semibold ring-1 ring-sky-400':'text-slate-400 hover:bg-slate-200 hover:border hover:border-slate-200 '">
              {{ t(filter.name) }}
            </button>
          </div>
        </template>
      </AtomsTabs>


      <div v-if="!loading" class="overflow-y-auto scrollbar-hide h-[85%]" @scroll="onScroll" ref="scrollContainer"
        :class="{ 'grid grid-cols-[2fr,1fr] gap-3': isHover, 'mt-4': !isFiltered || !isSearching }">
        <div class="overflow-y-auto scrollbar-hide relative">
          <ul class="">
            <li v-for="(result, index) in searchResults" :key="index"
              class="py-1 rounded-md hover:bg-slate-100 cursor-pointer " @mouseenter="" @click="handleClick(result)">
              <div class="px-1 py-1 grid grid-rows-2">
                <div class="font-medium text-slate-800 flex items-center gap-2">
                  <Icon :name="searchValues[result.entity][1]" size="13px" class="text-md ml-2 mr-1 text-slate-500" />
                  <span class="text-slate-400 text-base px-2">{{t( getItemTranslation(result.found_field)) }}: </span>
                  <span v-html="highlightedResult(result.found)"></span>
                  <span class="text-slate-400 text-xs px-5">
                    {{ t(result.app.toLowerCase()) }} / {{ t(result.entity.replace(/-/g, '_').toLowerCase()) }}</span>
                </div>
                <div class="flex items-center text-sm text-blue-400 font-medium italic text-sm gap-2">
                  <div v-for="(data, key) in result.object_data">
                    <AtomsColorBadge v-if="key && key.toLowerCase().includes('status')" :value="data" :color="'blue'" />
                    <span v-else>
                      {{ data }}
                    </span>
                  </div>
                </div>
              </div>
            </li>
            <li v-if="searchResults.length === 0 && !isFound && isSearching" class="text-gray-500">
              {{ t('common.no_search_results') }}
              {{ searchTerm }}
            </li>

            <li v-if="Object.entries(groupedSearchHistory).length === 0 && !isSearching" class="text-gray-500">
              {{ t('common.start_search') }}
            </li>
          </ul>

          <!-- Loading and end of results messages -->
          <div v-if="isSearching && searchResults.length > 0 && loadingMore" class="sticky bottom-4 left-0 right-0 bg-white py-2 border-t">
            <div v-if="loadingMore" class="text-gray-500 text-center">
              {{t('common.loading')}}...
            </div>
          </div>
          <div v-if="isSearching && searchResults.length > 0 && allDataLoaded" class="sticky bottom-2 left-0 right-0 bg-white py-2 border-t">
            <div v-if="allDataLoaded" class="text-gray-500 text-center">
              {{t('common.all_data_loaded')}}
            </div>
          </div>

          <ul v-if="Object.entries(groupedSearchHistory).length > 0 && !isSearching">
            <template v-for="[date, results] in Object.entries(groupedSearchHistory)" :key="date">
              <li class="text-sm text-slate-400">
                {{ formatDate(date) }}
              </li>
              <li v-for="(result, index) in results" :key="index" @click="handleClick(result)"
                class="py-1 rounded-md hover:bg-slate-100 cursor-pointer">
                <div class="px-1 py-1 ">
                  <div class="font-semibold text-slate-800 items-center gap-2 grid grid-cols-[20px,auto,1fr,auto] gap-2">
                    <Icon :name="searchValues[result.entity][1]" size="13px" class="text-md ml-2 mr-1 text-slate-500" />
                    <span class="text-slate-400 text-base px-2 truncate">{{ getItemTranslation(result.found_field) }}: </span>
                    <div class="flex items-center gap-2">
                      <span v-html="result.found"></span>
                      <span class="text-slate-400 text-xs px-5">
                        {{ t(result.app.toLowerCase()) }} / {{ t(result.entity.replace(/-/g, '_').toLowerCase()) }}
                      </span>
                    </div>
                    <div class="text-xs text-slate-400">
                      <TimeRelative :datetime="result.searched_at" />
                    </div>
                    <span class="col-span-full text-slate-300 italic text-xs">
                      {{ t('dashboard.search') }}: {{ result.query }}
                    </span>
                  </div>
                </div>
              </li>
            </template>
          </ul>
        </div>
      </div>
      <div v-else class=" space-y-2 h-[90%] overflow-y-hidden">
        <ul>
          <Skeleton :height="20" />
        </ul>
      </div>
    </div>
  </div>

</template>