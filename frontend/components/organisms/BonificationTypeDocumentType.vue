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
  parent_entity: String, 
  parent_id: Integer, 
  hasColor: Boolean, // L'entitat té camp de "color"
  hasMandatoryCheck: Boolean, // L'entitat té camp de "mandatory"
});

const router = useRouter();
const config = useRuntimeConfig();
const apiHost = config.public.apiHost;

const columnClass = ref('grid-cols-[50px,1fr,1fr,70px,50px,50px]');
let authToken = '';

// Verifiquem si estem en l'entorn del client abans d'accedir a localStorage
if (process.client) {
  authToken = localStorage.getItem('auth_token') || '';
}

const entity = ref(props.entity);
const apiUrl = ref(apiHost + '/' + props.entity + '/');
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const getData = () => {
  $fetch(apiUrl.value, {
    lazy: true,
    server: false,
    method: 'GET',
    headers: {
      'Authorization': 'Token ' + authToken,
    },
    onRequest({ request, options }) {
      pending.value = true;
      error.value = null;
    },
    onRequestError({ request, options, error }) {
      // Handle the request errors
      pending.value = false;
      error.value = error;
    },
    onResponse({ request, response, options }) {
      pending.value = false;
      if (typeof response._data.results != "undefined") {
        items.value = response._data.results;
      } else {
        error.value = new Error('Error estructura `results` no trobat');
      }
    }
  });
}

// Utilitzem watch per a observar canvis en props.entity i cridar a refresh
watch(() => props.entity, () => {
  entity.value = props.entity;
  apiUrl.value = apiHost + '/' + props.entity + '/';
  getData();
});

watch(() => props.hasColor, () => {
  setColumnClass();
});

watch(() => props.hasMandatoryCheck, () => {
  setColumnClass();
});

const setColumnClass = () => {
  let txt = 'grid-cols-[50px,1fr,1fr';
  if (props.hasColor) {
    txt += ',50px';
  }
  if (props.hasMandatoryCheck) {
    txt += ',70px';
  }
  txt += ',50px,50px]';

  // columnClass.value = "grid-cols-[50px,1fr,1fr,70px,50px,50px]";
  // console.log('grid-cols-[50px,1fr,1fr,50px,50px,50px]')
  // console.log('grid-cols-[50px,1fr,1fr,50px,50px]')

  columnClass.value = txt;
}


function onDraggableEnd(event) {
  const items_positions = items.value.map(item => item.id);
  $apiManager.fetch(apiUrl.value + 'update-positions/', 'POST', JSON.stringify(items_positions));
}

function onRadioDefaultChange(item_id) {
  $apiManager.fetch(apiUrl.value + 'update-default/', 'POST', JSON.stringify(item_id));
}
function onCheckMandatoryChange(item_id, value) {
  $apiService.updateValue(entity.value, 'is_mandatory', item_id, !value);
}

function onDelete(item_id) {
  console.log('onDelete');
  if (confirm('Segur que vols esborrar aquest element?')) {
    $apiManager.fetch(apiUrl.value + item_id + '/', 'DELETE').then(() => {
      getData();
    });
  }
}

function newItem() {
  let item_new = document.getElementById('item_new');
  item_new.classList.remove('hidden');
  item_new.querySelector('.edit_field_dialog button').click();
}

onMounted(() => {
  getData();
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
        <div :class="['heading', 'grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center']">
          <span class="text-slate-400 p-1">#</span>
          <span class="text-slate-400 p-1">{{ $t('common.identification') }} </span>
          <span class="text-slate-400 p-1">{{ $t('common.name') }} </span>
          <span v-if="hasColor" class="text-slate-400 p-1">{{ $t('common.color') }} </span>
          <span v-if="hasMandatoryCheck" class="text-slate-400 p-1">{{ $t('common.mandatory') }} </span>
          <span class="text-slate-400 p-1">{{ $t('default') }}</span>
          <span class="text-slate-400 p-1"></span>
        </div>
        <Draggable v-model="items" itemKey="id" handle=".handle-move" class="dragArea" @end="onDraggableEnd">
          <template #item="{ element: item }">
            <div :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white']">
              <span class="text-slate-900 p-1 border-r">
                <button class="handle-move cursor-move">
                  <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500 block-inline mr-1" />
                  <Icon name="fa6-solid:ellipsis-vertical" class="text-slate-500" />
                </button>
              </span>
              <span class="text-slate-900 p-1 border-r cursor_pointer relative">
                <EditFieldDialog :entity=entity property="token" :id=item.id :value=item.token></EditFieldDialog>
              </span>
              <span class="text-slate-900 p-1 border-r font-semibold">
                <EditFieldDialog :entity=entity property="name" :id=item.id :value=item.name inputClass="font-semibold">
                </EditFieldDialog>
              </span>
              <span v-if="hasColor" class="text-slate-900 p-1 border-r">
                <AtomsColorPicker :entity=entity :id="item.id" :code="item.color"></AtomsColorPicker>
              </span>
              <span v-if="hasMandatoryCheck" class="text-slate-900 p-1 border-r">
                <input class="ml-1 mt-1" type="checkBox" :name="t('common.mandatory')" :value="item.id" :checked="item.is_mandatory"
                  @change="onCheckMandatoryChange(item.id, item.is_mandatory)" />
              </span>
              <span class="text-slate-900 p-1 border-r">
                <input type="radio" :name="t('default')" class="ml-2" :value="item.id" :checked="item.is_default"
                  @change="onRadioDefaultChange(item.id)" />
              </span>
              <span class="text-slate-900 p-1 flex gap-2">
                <button @click="onDelete(item.id)"
                  class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300"><Icon name="fa6-solid:trash-can"
                    class="text-slate-500" /></button>
              </span>
            </div>
          </template>
        </Draggable>

        <div id="item_new" :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white', 'hidden']">
          <span class="text-slate-900 p-1 border-r">

          </span>
          <span class="text-slate-900 p-1 border-r">
            <EditFieldDialog :entity=entity property="token" :id=0 value="" @refreshList="getData"></EditFieldDialog>
          </span>
          <span class="text-slate-900 p-1 border-r font-semibold">
            &nbsp;
          </span>
          <span class="text-slate-900 p-1 border-r font-semibold">
            &nbsp;
          </span>
          <span class="text-slate-900 p-1 flex gap-2">
            <button class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300"><Icon name="fa6-solid:plus"
                class="text-slate-500" /></button>
          </span>
        </div>
        <div class="footering">
          <button @click="newItem"
            class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
            <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}</button>
        </div>
      </div><!-- end items -->
    </div><!-- end if items -->


  </div>
</template>
