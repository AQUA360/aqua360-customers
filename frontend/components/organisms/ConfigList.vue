<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import Draggable from 'vuedraggable';

const { t } = useI18n();
const {$apiManager,  $apiService} = useNuxtApp()

const props = defineProps({
  title: String, // Títol com a prop
  entity: String, // URL de l'API com a prop
  parent_entity: String, // (opcional) Entitat pare
  parent_id: Number, // (opcional) ID de l'entitat pare
  hasColor: Boolean, // L'entitat té camp de "color"
  hasMandatoryCheck: Boolean, // L'entitat té camp de "mandatory"
  blockEdits: {
    type: Boolean,
    default: false
  }, // Bloqueja les edicions
  hasDescription:{
    type: Boolean,
    default: false
  }, // L'entitat té camp de "description"
  hasCustomText: {
    type: Boolean,
    default: false
  }, // L'entitat té un camp personalitzable (ej. list_name)
  hasSerieDigits: {
    type: Boolean,
    default: false
  }, // L'entitat té els camps de dígit de sèrie per empresa (serie_digit_av/serie_digit_mv)
});

const router = useRouter();
const config = useRuntimeConfig();
const apiHost = config.public.apiHost;

// Blocks token edits when NUXT_EXTERNAL_GOT=True is set in `.env`
const blockTokenEdits = computed(() => props.blockEdits );

const columnClass = ref('grid-cols-[50px,1fr,1fr,70px,50px,50px]');

const gridStyle = computed(() => {
  let cols = '50px 2fr 2fr';
  if (props.hasCustomText) cols += ' 2fr';
  if (props.hasColor) cols += ' 50px';
  if (props.hasMandatoryCheck) cols += ' 80px';
  if (props.hasSerieDigits) cols += ' 90px 90px';
  cols += ' 70px 50px';
  return { 
    gridTemplateColumns: cols,
    display: 'grid'
  };
});
let authToken = '';

// Verifiquem si estem en l'entorn del client abans d'accedir a localStorage
if (process.client) {
  authToken = localStorage.getItem('auth_token') || '';
}

const emit = defineEmits(['changed']);
const entity = ref(props.entity);
const apiUrl = ref(apiHost + '/' + props.entity + '/');
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const page = ref(1);
const pageSize = 50;
const hasNextPage = ref(true);
const loadingMore = ref(false);
const allDataLoaded = ref(false);

const getData = (skip_clear = false) => {
  if (loadingMore.value || allDataLoaded.value) return;

  loadingMore.value = true;
  let url = apiUrl.value;
  if( props.parent_id ) {
    url = url + '?' + props.parent_entity + '=' + props.parent_id + '&page=' + page.value;
  } else {
    url = url + '?page=' + page.value;
  }
  
  $fetch(url, {
    lazy: true,
    server: false,
    method: 'GET',
    headers: {
      'Authorization': 'Token ' + authToken,
    },
    onRequest({ request, options }) {
      if (page.value === 1) {
        pending.value = true;
      }
      error.value = null;
    },
    onRequestError({ request, options, error }) {
      // Handle the request errors
      pending.value = false;
      loadingMore.value = false;
      error.value = error;
    },
    onResponse({ request, response, options }) {
      pending.value = false;
      loadingMore.value = false;
      
      if (typeof response._data.results != "undefined") {
        if (page.value === 1 || skip_clear) {
          items.value = response._data.results;
        } else {
          items.value = items.value.concat(response._data.results);
        }
        
        // Check if there are more pages
        if (response._data.next == null) {
          hasNextPage.value = false;
        }
        
        if (response._data.results.length < pageSize || !hasNextPage.value) {
          allDataLoaded.value = true;
        } else {
          page.value++;
        }
      } else {
        error.value = new Error('Error estructura `results` no trobat');
      }
    }
  });
}

const onScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollHeight - scrollTop <= clientHeight + 50 && !loadingMore.value && hasNextPage.value) {
    getData();
  }
};

// Utilitzem watch per a observar canvis en props.entity i cridar a refresh
watch(() => props.entity, () => {
  entity.value = props.entity;
  apiUrl.value = apiHost + '/' + props.entity + '/';
  page.value = 1;
  hasNextPage.value = true;
  allDataLoaded.value = false;
  getData(true);
});

watch(() => props.hasColor, () => {
  setColumnClass();
});

watch(() => props.hasMandatoryCheck, () => {
  setColumnClass();
});

const setColumnClass = () => {
  // Mantingut per retrocompatibilitat si algun estil ho usa, 
  // tot i que ara usem gridStyle inline per evitar problemes amb Tailwind JIT
  let txt = 'grid-cols-[50px,2fr,2fr';
  if (props.hasCustomText) {
    txt += ',2fr';
  }
  if (props.hasColor) {
    txt += ',50px';
  }
  if (props.hasMandatoryCheck) {
    txt += ',70px';
  }
  txt += ',50px,50px]';

  columnClass.value = txt;
}


function onDraggableEnd(event) {
  const items_positions = items.value.map(item => item.id);
  $apiManager.fetch(apiUrl.value + 'update-positions/', 'POST', JSON.stringify(items_positions)).then(() => {
    emit('changed');
  });
}

function onRadioDefaultChange(item_id) {
  $apiManager.fetch(apiUrl.value + 'update-default/', 'POST', JSON.stringify(item_id)).then(() => {
    emit('changed');
  });
}
function onCheckMandatoryChange(event, item) {
  const item_id = item.id;
  const value = event.target.checked; // is checked
  $apiService.updateValue(entity.value, 'is_mandatory', item_id, value).then(() => {
    emit('changed');
  });
}

function onDelete(item_id) {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    $apiManager.fetch(apiUrl.value + item_id + '/', 'DELETE').then(() => {
      page.value = 1;
      hasNextPage.value = true;
      allDataLoaded.value = false;
      getData(true);
      emit('changed');
    });
  }
}

function newItem() {
  let item_new = document.getElementById('item_new');
  item_new.classList.remove('hidden');
  item_new.querySelector('.edit_field_dialog button').click();
}

const handleRefreshList = () => {
  page.value = 1;
  hasNextPage.value = true;
  allDataLoaded.value = false;
  getData(true);
  emit('changed');
}
const handleChanged = () => {
  emit('changed');
}

onMounted(() => {
  page.value = 1;
  hasNextPage.value = true;
  allDataLoaded.value = false;
  getData(true);
  setColumnClass();
});
</script>

<template>
  <div v-if="pending">
    <p>{{ $t('common.loading') }}...</p>
  </div>
  <div v-else-if="error">
    <p>Error: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again') }}</button>
      </p>
  </div>
  <div v-else>
    <H1Region class="mb-3">{{ title }}</H1Region>
    <!-- total -->
    <div v-if="items">
      <div id="config__totals" class="text-sm text-right text-slate-500">{{ $t('common.total') }}: {{ items.length }}</div>
      <div id="config__items text-base">
        <div class="heading text-base border-b items-center bg-slate-50" :style="gridStyle">
          <span class="text-slate-400 p-2 border-r border-slate-100">#</span>
          <span class="text-slate-400 p-2 border-r border-slate-100">{{ $t('common.identification') }} </span>
          <span class="text-slate-400 p-2 border-r border-slate-100">{{ $t('common.name') }} </span>
          <span v-if="hasCustomText" class="text-slate-400 p-2 border-r border-slate-100">{{ $t('common.custom_text') }} </span>
          <span v-if="hasColor" class="text-slate-400 p-2 border-r border-slate-100">{{ $t('common.color') }} </span>
          <span v-if="hasMandatoryCheck" class="text-slate-400 p-2 border-r border-slate-100">{{ $t('common.mandatory') }} </span>
          <span v-if="hasSerieDigits" class="text-slate-400 p-2 border-r border-slate-100">{{ $t('billing_block.serie_digit_av') }} </span>
          <span v-if="hasSerieDigits" class="text-slate-400 p-2 border-r border-slate-100">{{ $t('billing_block.serie_digit_mv') }} </span>
          <span class="text-slate-400 p-2 border-r border-slate-100">{{ $t('default') }}</span>
          <span class="text-slate-400 p-2"></span>
        </div>
        <div @scroll="onScroll" :style="{
          overflowY: 'auto',
          maxWidth: '100%',
          maxHeight: 'calc(100vh - 250px)'
        }"  >
          <Draggable v-model="items" itemKey="id" handle=".handle-move" class="dragArea" @end="onDraggableEnd">
            <template #item="{ element: item }">
              <div class="text-base border-b items-center bg-white" :style="gridStyle">
                <span class="text-slate-900 p-1 border-r border-slate-100 handle-move cursor-move h-full flex items-center justify-center">
                  <button class="">
                    <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500 block-inline mr-1" />
                    <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500" />
                  </button>
                </span>
                <span class="text-slate-900 p-1 border-r border-slate-100 cursor_pointer relative h-full flex items-center">
                  <span v-if="blockTokenEdits" class="w-full">{{ item.token }}</span>
                  <EditFieldDialog v-else class="w-full" :entity=entity property="token" :id=item.id :value=item.token @changed="handleChanged" ></EditFieldDialog>
                </span>
                <span class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center" :class="{ 'grid grid-cols-[1fr,50px]': hasDescription }">
                  <EditFieldDialog class="w-full" :entity=entity property="name" :id=item.id :value=item.name @changed="handleChanged" inputClass="font-semibold"  >
                  </EditFieldDialog>
                  <abbr :title="item.description" v-if="hasDescription" class="ml-1 text-slate-500 font-semibold">
                    <Icon name="fa6-solid:circle-info" class="text-slate-300" />
                  </abbr>
                </span>
                <span v-if="hasCustomText" class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center">
                  <EditFieldDialog class="w-full" :entity=entity property="list_name" :id=item.id :value=item.list_name @changed="handleChanged" >
                  </EditFieldDialog>
                </span>
                <span v-if="hasColor" class="text-slate-900 p-1 border-r border-slate-100 h-full flex items-center justify-center">
                  <AtomsColorPicker :entity=entity :id="item.id" :code="item.color"></AtomsColorPicker>
                </span>
                <span v-if="hasMandatoryCheck" class="text-slate-900 p-1 border-r border-slate-100 h-full flex items-center justify-center">
                  <input class="ml-1 mt-1" type="checkBox" name="mandatory" :value="item.id" :checked="item.is_mandatory"
                    @change="(event) => onCheckMandatoryChange(event, item)" />
                </span>
                <span v-if="hasSerieDigits" class="text-slate-900 p-1 border-r border-slate-100 h-full flex items-center justify-center">
                  <EditFieldDialog class="w-full text-center" :entity=entity property="serie_digit_av" :id=item.id :value=item.serie_digit_av :maxlength="1" @changed="handleChanged">
                  </EditFieldDialog>
                </span>
                <span v-if="hasSerieDigits" class="text-slate-900 p-1 border-r border-slate-100 h-full flex items-center justify-center">
                  <EditFieldDialog class="w-full text-center" :entity=entity property="serie_digit_mv" :id=item.id :value=item.serie_digit_mv :maxlength="1" @changed="handleChanged">
                  </EditFieldDialog>
                </span>
                <span class="text-slate-900 p-1 border-r border-slate-100 h-full flex items-center justify-center">
                  <input type="radio" name="default" class="ml-2" :value="item.id" :checked="item.is_default"
                    @change="onRadioDefaultChange(item.id)" />
                </span>
                <span class="text-slate-900 p-1 flex gap-2 h-full items-center justify-center">
                  <button @click="onDelete(item.id)" :disabled="blockTokenEdits"
                    class="px-2 py-1 disabled:opacity-20 enabled:hover:bg-slate-200 rounded enabled:active:bg-slate-300"><Icon name="fa6-solid:trash-can"
                      class="text-slate-500" /></button>
                </span>
              </div>
            </template>
          </Draggable>
          <div v-if="loadingMore" class="text-center py-4">
            <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500 mr-2" />
            {{ $t('common.loading') }}...
          </div>
        </div>

        <div id="item_new" v-if="!blockTokenEdits" class="text-base border-b items-center bg-white hidden" :style="gridStyle">
          <span class="text-slate-900 p-1 border-r border-slate-100 h-full">
          </span>
          <span class="text-slate-900 p-1 border-r border-slate-100 h-full flex items-center">
            <EditFieldDialog 
              class="w-full"
              :entity="entity" 
              property="token" 
              :id="0" 
              value="" 
              @refreshList="handleRefreshList"
              @changed="handleChanged" 
              :parent_entity="props.parent_entity || ''"  
              :parent_id="props.parent_id || null">
            </EditFieldDialog>
          </span>
          <span class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center">
            &nbsp;
          </span>
          <span v-if="hasCustomText" class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center">
            &nbsp;
          </span>
          <span v-if="hasColor" class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center">
            &nbsp;
          </span>
          <span v-if="hasMandatoryCheck" class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center">
            &nbsp;
          </span>
          <span v-if="hasSerieDigits" class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center">
            &nbsp;
          </span>
          <span v-if="hasSerieDigits" class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center">
            &nbsp;
          </span>
          <span class="text-slate-900 p-1 border-r border-slate-100 font-semibold h-full flex items-center">
            &nbsp;
          </span>
          <span class="text-slate-900 p-1 flex gap-2 h-full items-center justify-center">
            <button class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300"><Icon name="fa6-solid:plus"
                class="text-slate-500" /></button>
          </span>
        </div>
        <div v-if="!blockTokenEdits" class="footering">
          <button @click="newItem"
            class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
            <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}</button>
        </div>
      </div><!-- end items -->
    </div><!-- end if items -->


  </div>
</template>
