<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import EditFieldDialog from '~/components/molecules/EditFieldDialog.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { formatMoney } from '~/utils/money';

const { t } = useI18n();
const { $apiManager, $AddressApiService, $apiService } = useNuxtApp()

const props = defineProps({});

const router = useRouter();
const config = useRuntimeConfig();
const apiHost = config.public.apiHost;

const columnClass = ref('grid-cols-[120px,250px,1fr,50px]');

const emit = defineEmits(['changed']);
const entity = ref('coredata/bank');
const apiUrl = ref(apiHost + '/' + entity.value + '/');
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const searchTerm = ref('');
const getData = () => {
  pending.value = true;
  items.value = [];

  $AddressApiService.getBanks().then((data) => {
    data.forEach(function(item){
      items.value.push(item)
    })
    
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
  emit('changed');
}

// Computed property to filter items based on search term
const filteredItems = computed(() => {
  if (!searchTerm.value) {
    return items.value;
  }
  
  const term = searchTerm.value.toLowerCase();
  return items.value.filter(item => 
    (item.token && item.token.toLowerCase().includes(term)) ||
    (item.name && item.name.toLowerCase().includes(term))
  );
});



onMounted(() => {
  getData();
});
</script>

<template>
  <div v-if="pending">
    <AppLoading :text="$t('common.loading')" />
  </div>
  <div v-else-if="error">
    <p>Error: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
        }}</button>
    </p>
  </div>
  <div v-else>
    <H1Region class="mb-3">{{ $t('common.banks') }}</H1Region>
    
    <!-- Search input -->
    <div class="">
      <input 
        v-model="searchTerm"
        type="text" id="searchInput" 
        :placeholder="$t('dashboard.search') + '...'"
        class="w-full p-1 rounded-md focus:outline-none focus-visible:border-0"
      />
    </div>
    
    <!-- total -->
    <div v-if="items">
      <div id="config__totals" class="text-sm text-right text-slate-500">
        {{ $t('common.total') }}: {{ filteredItems.length }} / {{ items.length }}
      </div>
      <div id="config__items" class="text-base">
        <div :class="['heading', 'grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center']">
          <span class="text-slate-400 p-1">{{ $t('common.identification') }} </span>
          <span class="text-slate-400 p-1">{{ $t('common.name') }} </span>
          <span class="text-slate-400 p-1">{{ $t('common.bic') }} </span>
          <span class="text-slate-400 p-1"></span>
        </div>
        <div class="overflow-y-auto max-h-[calc(100vh-200px)]">
          <div v-if="filteredItems.length === 0 && searchTerm" class="text-center py-8 text-slate-500">
            {{ $t('common.no_results_found') }}
          </div>
          <div v-for="item in filteredItems" :key="item.id" :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white']">
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
            <EditFieldDialog v-model='item.bic' :entity=entity property="bic" :id=item.id :value=item.bic @changed="handleChanged"
              inputClass="font-semibold"/>
          </span>
         
          <span class="text-slate-900 p-1 flex gap-2">
            <button @click="onDelete(item.id)"
              class="px-2 py-1 hover:bg-slate-200 rounded active:bg-slate-300">
              <Icon name="fa6-solid:trash-can" class="text-slate-500" />
            </button>
          </span>
          </div>
        </div>

        <div id="item_new"
          :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white', 'hidden']">
          <span class="text-slate-900 p-1 border-r"><!-- position removed --></span>
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
