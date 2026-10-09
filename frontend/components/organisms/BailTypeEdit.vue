<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import Draggable from 'vuedraggable';
import { formatMoney } from '~/utils/money';

const { t } = useI18n();
const { $apiManager, $BailTypeApiService, $apiService } = useNuxtApp()

const props = defineProps({});

const router = useRouter();
const config = useRuntimeConfig();
const apiHost = config.public.apiHost;

const columnClass = ref('grid-cols-[35px,120px,250px,1fr,50px]');

const emit = defineEmits(['changed']);
const entity = ref('contract/bail-type');
const apiUrl = ref(apiHost + '/' + entity.value + '/');
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const getData = () => {
  pending.value = true;
  items.value = [];

  $BailTypeApiService.getAll().then((data) => {
    data.results.forEach(function(item){
      item.default_import = formatMoney(item.default_import);
      items.value.push(item)
    })
    
    pending.value = false;
    error.value = null;
  });
}

function onDraggableEnd(event) {
  const items_positions = items.value.map(item => item.id);
  $apiManager.fetch(apiUrl.value + 'update-positions/', 'POST', JSON.stringify(items_positions)).then(() => {
    emit('changed');
  });
}

function onDelete(item_id) {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    $apiManager.fetch(apiUrl.value + item_id + '/', 'DELETE').then(() => {
      getData();
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
  getData();
  emit('changed');
}
const handleChanged = () => {
  emit('changed');
}



onMounted(() => {
  getData();
});
</script>

<template>
  <div v-if="pending">
    <p>{{ $t('common.loading') }}...</p>
  </div>
  <div v-else-if="error">
    <p>Error: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button>
    </p>
  </div>
  <div v-else>
    <H1Region class="mb-3">{{ $t('billing_block.bail_type') }}</H1Region>
    <!-- total -->
    <div v-if="items">
      <div id="config__totals" class="text-sm text-right text-slate-500">{{ $t('common.total') }}: {{ items.length }}</div>
      <div id="config__items text-base">
        <div :class="['heading', 'grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center']">
          <span class="text-slate-400 p-1">#</span>
          <span class="text-slate-400 p-1">{{ $t('common.identification') }} </span>
          <span class="text-slate-400 p-1">{{ $t('common.name') }} </span>
          <span class="text-slate-400 p-1">{{ $t('common.amount') }} (€) </span>
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
                <EditFieldDialog :entity=entity property="token" :id=item.id :value=item.token @changed="handleChanged">
                </EditFieldDialog>
              </span>
              <span class="text-slate-900 p-1 border-r font-semibold">
                <EditFieldDialog :entity=entity property="name" :id=item.id :value=item.name @changed="handleChanged"
                  inputClass="font-semibold">
                </EditFieldDialog>
              </span>
              <span class="text-slate-900 p-1 border-r font-semibold">
                <EditFieldDialog v-model='item.default_import' :entity=entity property="default_import" :id=item.id :value=item.default_import @changed="handleChanged"
                  inputClass="font-semibold"/>
              </span>
             
              <span class="text-slate-900 p-1 flex gap-2">
                <button @click="onDelete(item.id)"
                  class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300">
                  <Icon name="fa6-solid:trash-can" class="text-slate-500" />
                </button>
              </span>
            </div>
          </template>
        </Draggable>

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
            <button class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-500" />
            </button>
          </span>
        </div>
        <div class="footering">
          <button @click="newItem"
            class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300"><Icon
              name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}</button>
        </div>
      </div><!-- end items -->
    </div><!-- end if items -->


  </div>
</template>
