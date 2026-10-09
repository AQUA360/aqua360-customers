<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import Draggable from 'vuedraggable';

const { t } = useI18n();
const { $apiManager, $PriceVariableIntervalStretchApiService } = useNuxtApp()

const props = defineProps({
  id: Number,
});
//TODO ADD ID PROPS
const router = useRouter();
const config = useRuntimeConfig();
const apiHost = config.public.apiHost;

const columnClass = ref('grid-cols-[1fr,1fr,1fr,1fr,3fr,1fr]');

const emit = defineEmits(['changed']);
const entity = ref('pricing/price-variable-interval-stretch');
const apiUrl = ref(apiHost + '/' + entity.value + '/');
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const dataId = ref(null)
const getData = () => {
  pending.value = true;
  items.value = [];

  if (!props.id) {
    dataId.value = -1
  } else {
    dataId.value = props.id
  }

  $PriceVariableIntervalStretchApiService.getAll('', [], 1, null, false, dataId.value).then((data) => {
    items.value = data.results;
    pending.value = false;
    error.value = null;
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
  getData();
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
    <p>{{ $t('common.error') }}: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button>
    </p>
  </div>
  <div v-else>
    <!-- total -->
    <div v-if="items">
      <div id="config__items text-base" class="mt-2 mx-10 ">
        <table class="table-auto w-full border-collapse border border-gray-200 table-layout-auto">
          <thead>
            <tr class="bg-gray-100">
              <th class="text-slate-400 p-2 text-left">{{ $t('pricing_block.stretch') }}</th>
              <th class="text-slate-400 p-2 text-left">{{ $t('common.name') }}</th>
              <th class="text-slate-400 p-2 text-left">{{ $t('common.limit') }}</th>
              <th class="text-slate-400 p-2 text-left">{{ $t('pricing_block.fixed_price') }}</th>
              <th class="text-slate-400 p-2 text-left">{{ $t('pricing_block.proportional_price') }}</th>
              <th class="text-slate-400 p-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id" class="bg-white">
              <td class="text-slate-900 p-2 border-r break-words">
                <span>{{ item.stretch }}</span>
              </td>
              <td class="text-slate-900 p-2 px-2 border-r break-words">
                <EditFieldDialog :entity="entity" property="name_stretch" :id="item.id" :value="item.name_stretch"
                  @refreshList="handleRefreshList" @changed="handleChanged" inputClass="font-semibold">
                </EditFieldDialog>
              </td>
              <td class="text-slate-900 p-2 px-2 border-r break-words">
                <EditFieldDialog :entity="entity" property="end_stretch" :id="item.id" :value="item.end_stretch"
                  @refreshList="handleRefreshList" @changed="handleChanged" inputClass="font-semibold">
                </EditFieldDialog>
              </td>
              
              <td class="text-slate-900 p-2 border-r break-words">
                <EditFieldDialog :entity="entity" property="price" :id="item.id" :value="item.price"
                  @refreshList="handleRefreshList" @changed="handleChanged" inputClass="font-semibold">
                </EditFieldDialog>
              </td>
              <td class="text-slate-900 p-2 border-r break-words">
                <EditFieldDialog :entity="entity" property="proportional_price" :id="item.id" :value="item.proportional_price"
                  @refreshList="handleRefreshList" @changed="handleChanged" inputClass="font-semibold">
                </EditFieldDialog>
              </td>
              <td class="text-slate-900 p-2 border-r">
                <button @click="onDelete(item.id)" class="px-1 py-1 hover:bg-slate-200 rounded active:bg-slate-300">
                  <Icon name="fa6-solid:trash-can" class="text-slate-500" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div id="item_new"
          :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white', 'hidden']">
          <span class="text-slate-900 p-2 "><!-- move --></span>
          <span class="text-slate-900 p-2 "><!-- move --></span>
          <span class="text-slate-900 p-2 ">
            <EditFieldDialog :entity="entity" property="token" :id="0" value="" @refreshList="handleRefreshList"
              @changed="handleChanged" :related_id="props?.id || null">
            </EditFieldDialog>
          </span>
          <span class="text-slate-900 p-2  font-semibold">
            &nbsp;<!-- name -->
          </span>
          <span class="text-slate-900 p-2  font-semibold">
            &nbsp;<!-- type -->
          </span>

          <span class="text-slate-900 p-2 flex gap-2">
            <button class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-500" />
            </button>
          </span>
        </div>
        <div class="footering">
          <button @click="newItem"
            class="display-block block w-full px-2 py-1 text-base text-slate-400 border hover:bg-slate-200 text-left active:bg-slate-300">
            <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
          </button>
        </div>
      </div>
      <!-- end items -->
    </div><!-- end if items -->


  </div>
</template>
