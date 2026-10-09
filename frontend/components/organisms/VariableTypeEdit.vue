<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import Draggable from 'vuedraggable';

const { t } = useI18n();
const { $apiManager, $VariableTypeApiService, $apiService } = useNuxtApp()
import { VariableTypeDataTypeChoices, VariableTypeApplicationChoices } from '~/utils/variable-type';

const props = defineProps({});

const router = useRouter();
const config = useRuntimeConfig();
const apiHost = config.public.apiHost;

const columnClass = ref('grid-cols-[35px,2fr,4fr,2fr,2fr,1fr,50px]');

const emit = defineEmits(['changed']);
const entity = ref('contract/variable-type');
const apiUrl = ref(apiHost + '/' + entity.value + '/');
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
  if (page.value === 1) {
    pending.value = true;
  }
  if (page.value === 1 || skip_clear) {
    items.value = [];
  }

  $VariableTypeApiService.getAll('', [], page.value).then((data) => {
    if (page.value === 1 || skip_clear) {
      items.value = data.results;
    } else {
      items.value = items.value.concat(data.results);
    }
    
    // Check if there are more pages
    if (data.next == null) {
      hasNextPage.value = false;
    }
    
    if (data.results.length < pageSize || !hasNextPage.value) {
      allDataLoaded.value = true;
    } else {
      page.value++;
    }
    
    pending.value = false;
    loadingMore.value = false;
    error.value = null;
  }).catch((err) => {
    pending.value = false;
    loadingMore.value = false;
    error.value = err;
  });
}

const onScroll = (event) => {
  const { scrollTop, scrollHeight, clientHeight } = event.target;
  if (scrollHeight - scrollTop <= clientHeight + 50 && !loadingMore.value && hasNextPage.value) {
    getData();
  }
};

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
function onCheckMandatoryChange(item_id, value) {
  $apiService.updateValue(entity.value, 'is_mandatory', item_id, !value).then(() => {
    emit('changed');
  });
}

function onDelete(item_id) {

  if (confirm(t('confirmation_text_block.confirm_delete') )) {
    $apiManager.fetch(apiUrl.value + item_id + '/', 'DELETE').then(() => {
      page.value = 1;
      hasNextPage.value = true;
      allDataLoaded.value = false;
      getData(true);
    });
  }
  emit('changed');
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

function handleDataTypeChanged(event, item) {
  const newValue = event.target.value;
  $apiService.updateValue(entity.value, 'data_type', item.id, newValue).then(() => {
    emit('changed');
  });
}

function onVulnerableChange(item_id, value) {
  $apiService.updateValue(entity.value, 'is_vulnerable', item_id, value).then(() => {
    emit('changed');
  });
}

function handleApplicationChanged(event, item) {
  const newValue = event.target.value;
  $apiService.updateValue(entity.value, 'application', item.id, newValue).then(() => {
    emit('changed');
  });
}

onMounted(() => {
  page.value = 1;
  hasNextPage.value = true;
  allDataLoaded.value = false;
  getData(true);
});
</script>

<template>
  <div v-if="pending">
    <p>{{ $t('common.loading') }}...</p>
  </div>
  <div v-else-if="error">
    <p>{{t('common.error')}}: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button>
    </p>
  </div>
  <div v-else>
    <H1Region class="mb-3">{{ $t('contract_block.variable_types') }}</H1Region>
    <!-- total -->
    <div v-if="items">
      <div id="config__totals" class="text-sm text-right text-slate-500">{{ $t('common.total') }}: {{ items.length }}</div>
      <div id="config__items text-base">
        <div :class="['heading', 'grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center']">
          <span class="text-slate-400 p-1">#</span>
          <span class="text-slate-400 p-1">{{ $t('common.identification') }} </span>
          <span class="text-slate-400 p-1">{{ $t('common.name') }} </span>
          <span class="text-slate-400 p-1">{{ $t('common.type') }} </span>
          <span class="text-slate-400 p-1">{{ $t('pricing_block.application') }} </span>
          <span class="text-slate-400 p-1">{{ $t('contract_block.vulnerable') }} </span>
          <span class="text-slate-400 p-1"></span>
        </div>
        <div @scroll="onScroll" :style="{
          overflowY: 'auto',
          maxWidth: '100%',
          maxHeight: 'calc(100vh - 250px)'
        }">
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
                  <EditFieldDialog :entity=entity property="token" :id=item.id :value=item.token @changed="handleChanged">
                  </EditFieldDialog>
                </span>
                <span class="text-slate-900 p-1 border-r font-semibold">
                  <EditFieldDialog :entity=entity property="name" :id=item.id :value=item.name @changed="handleChanged"
                    inputClass="font-semibold">
                  </EditFieldDialog>
                </span>
                <span class="text-slate-900 p-1 border-r">
                  <select v-model="item.data_type" @change="(event) => handleDataTypeChanged(event, item)">
                    <option v-for="(label, value) in VariableTypeDataTypeChoices" :key="value" :value="value">
                    {{ label }}
                    </option>
                  </select>
                </span>
                <span class="text-slate-900 p-1 border-r">
                  <select v-model="item.application" @change="(event) => handleApplicationChanged(event, item)">
                    <option v-for="(label, value) in VariableTypeApplicationChoices" :key="value" :value="value">
                      {{ label }}
                    </option>
                  </select>
                </span>
                <span class="text-slate-900 p-1 border-r font-semibold">
                  <input type="checkbox" :checked="item.is_vulnerable" @change="onVulnerableChange(item.id, !item.is_vulnerable)">
                </span>
                <span class="text-slate-900 p-1 flex gap-2">
                  <button @click="onDelete(item.id)"
                    class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300"><Icon name="fa6-solid:trash-can"
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

        <div id="item_new"
          :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white', 'hidden']">
          <span class="text-slate-900 p-1 border-r"><!-- move --></span>
          <span class="text-slate-900 p-1 border-r">
            <EditFieldDialog :entity="entity" property="token" :id="0" value="" @refreshList="handleRefreshList" @changed="handleChanged" >
            </EditFieldDialog>
          </span>
          <span class="text-slate-900 p-1 border-r font-semibold">
            &nbsp;<!-- name -->
          </span>
          <span class="text-slate-900 p-1 border-r font-semibold">
            &nbsp;<!-- type -->
          </span>
          <span class="text-slate-900 p-1 border-r font-semibold">
            &nbsp;<!-- app -->
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
