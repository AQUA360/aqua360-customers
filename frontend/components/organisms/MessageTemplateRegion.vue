<script setup>
import { useRouter } from 'vue-router';
import AppLoading from '~/components/atoms/AppLoading.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import MessageTemplateDetail from '~/components/molecules/MessageTemplateDetail.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import MessageTemplateEdit from '~/components/organisms/MessageTemplateEdit.vue';
import MessageTypeTemplateEdit from '~/components/organisms/MessageTypeTemplateEdit.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close']);

const router = useRouter();
const { $MessageTemplateApiService, $ConfigProjectApiService, $ConfiglistApiService, $CommunicationApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const messageTypes = ref([]);
const messageTypeTemplates = ref([]);

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const getData = async (load = true) => {
  pending.value = load;
  error.value = null;
  try {
    const result = await $MessageTemplateApiService.getDetail(props.id);
    data.value = result;
    messageTypeTemplates.value = result.templates;
    messageTypes.value.forEach(type => {
      const hasTemplate = result.templates.some(template => template.type?.id === type.id && !template.unused);
      let template = result.templates.find(template => template.type?.id === type.id);
      type.checked = hasTemplate;
      type.template = template ? template : null;
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const getMessageTypes = async () => {
  try {
    const result = await $ConfiglistApiService.getAll('communication/message-type');
    result.results.forEach(messageType => {
      messageTypes.value.push({
        id: messageType.id,
        name: messageType.name,
        checked: false,
        template: null
      });
    });
  } catch (err) {
    console.error('Error obtenint les dades:', err);
  }
}

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = async function (component, id) {
  await closeSubRegion()

  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  showSubRegion();
}

const handleTypeChecked = async (id) => {
  let template = null;
  messageTypes.value.forEach(type => {
    if (type.id === id) {
      type.checked = !type.checked;
      template = type.template;
    }
  });
  if (template) {
    try {
      let save_data = {
        id: template.id,
        unused: !template.unused
      }
      await $MessageTemplateApiService.saveTypeTemplate(save_data);
      refresh(false, false);
    } catch (err) {
      console.error('Error eliminant la plantilla:', err);
    }
  }
}

const addNewTypeTemplate = async (id) => {
  try {
    let save_data = {
      type_id: id,
      subject: '',
      body: '',
      template_id: data.value.id
    }
    let msg_type = await $MessageTemplateApiService.saveTypeTemplate(save_data);
    showDetail('MessageTypeTemplateEdit', msg_type);
    refresh(false, false);
  } catch (err) {
    console.error('Error afegint la plantilla:', err);
  }
}

const deleteTemplate = async (id) => {
  if (!confirm('Estàs segur que vols eliminar aquesta plantilla?')) return;
  try {
    await $MessageTemplateApiService.deleteItem(id);
    emit('changed', true, true);
  } catch (err) {
    console.error('Error eliminant la plantilla:', err);
  }
}

const deleteTemplateType = async (id) => {
  if (!confirm('Estàs segur que vols eliminar aquest missatge?')) return;
  closeSubRegion()
  await $MessageTemplateApiService.deleteTypeTemplate(id);
  refresh(false, false);
}

const refresh = async (close = true, load = true) => {
  await getData(load)
  if (close) closeSubRegion()
  emit('changed', load, close)
}

watch(() => props.id, () => {
  getData();
});

onMounted(async () => {
  objectPermissions.value = await checkPermission($CommunicationApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  await getMessageTypes();
  await getData();
});
</script>

<template>
  <div v-if="objectPermissions?.can_view" class="region__content">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
          }}</button></p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[47%]': SubRegion }">
      <div class="flex justify-between relative mb-3">
        <H1Region class="mb-3">{{ $t('customer_service_block.comms_template') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="MessageTypeTemplateRegionOptions">
          <DropdownOption :name="t('common.modify')" @click="showDetail('MessageTemplateEdit', data.id)">
            <Icon name="fa6-solid:pencil" class="display-inline mr-2" /> {{ t('common.modify') }}
          </DropdownOption>
          <DropdownOption :name="t('common.delete')" @click="deleteTemplate(data.id)">
            <Icon name="fa6-solid:trash" class="display-inline mr-2" /> {{ t('common.delete') }}
          </DropdownOption>

        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <MessageTemplateDetail :id="data.id" :data="data" :isSubRegion="isSubRegion" />
      </div>
      <div class="mt-5">
        <!-- <label class="text-slate-400 font-medium text-base flex items-center gap-1 mt-3">
          {{ t('Missatges') }}
        </label> -->
        <div class="flex flex-col gap-2 my-2">
          <div v-for="messageType in messageTypes" :key="messageType.id" class="grid grid-cols-[150px,1fr]">
            <div class="flex items-center gap-2">
              <input :disabled="!objectPermissions?.can_change" type="checkbox" :id="'messageType_' + messageType.id" :value="messageType.id"
                :checked="messageType.checked" @change="handleTypeChecked(messageType.id)"
                class="w-4 h-4 text-sky-600 bg-gray-100 border-gray-300 rounded focus:ring-sky-500">
              <label :for="'messageType_' + messageType.id" class="text-sm text-gray-700">
                {{ messageType.name }}
              </label>
            </div>
            <div v-if="!messageType.template">
              <ButtonSeleccio :small="true" :disabled="!messageType.checked"
                @click="addNewTypeTemplate(messageType.id)">
                {{ t('common.add') }} {{ t('common.message') }}
              </ButtonSeleccio>
            </div>
            <div v-else
              class="group relative px-4 py-2 rounded max-w-lg border border-slate-400 transition-all duration-500 ease"
              :class="{ 'bg-slate-50': messageType.template.unused }">
              <p class="text-slate-500 transition-all duration-500 ease"
                :class="{ 'opacity-60': messageType.template.unused }">
                {{ messageType.template.subject != '' || messageType.template.subject ?
                  messageType.template.subject : t('customer_service_block.no_content') }}</p>
              <p class="text-slate-300 text-sm italic truncate transition-all duration-500 ease"
                :class="{ 'opacity-60': messageType.template.unused }">
                {{ messageType.template.body != '' || messageType.template.body ?
                  messageType.template.body : '-' }}</p>
                  <abbr v-if="messageType.template.subject == '' || messageType.template.subject == null  ||
                messageType.template.body == '' || messageType.template.body == null" 
                class="text-orange-500 absolute top-0 left-0 text-lg w-6 h-6 flex items-center justify-center"
                :title="t('informative_block.info_no_content_msg')">
                <Icon name="fa6-solid:circle-exclamation" />
              </abbr>
              <button v-if="objectPermissions?.can_change" @click="showDetail('MessageTypeTemplateEdit', messageType.template)"
                class="absolute top-1 right-1 w-6 h-6 bg-white border border-slate-400 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-all duration-300 ease">
                <Icon name="fa6-solid:pencil" class="text-slate-500" />
              </button>
              <button v-if="objectPermissions?.can_change" @click="deleteTemplateType(messageType.template.id)"
                class="absolute top-1 right-7 w-6 h-6 bg-white border border-slate-400 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-slate-200 transition-all duration-300 ease">
                <Icon name="fa6-solid:trash" class="text-slate-500" />
              </button>
            </div>
          </div>
        </div>
      </div>

    </div><!-- end if pending -->

    <div v-if="SubRegion == true" role="region" id="subregion"
      class="h-full border-l border-gray-100 py-2 text-base bg-white transition-all duration-500 ease fixed top-0 right-0 z-10 w-[47%] overflow-y-auto overflow-x-hidden">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <MessageTemplateEdit v-if="showRegionDetailComponent == 'MessageTemplateEdit'" :item="data"
          :isSubRegionOpen="isSubRegionOpen" @saved="refresh(true, false)"></MessageTemplateEdit>
        <MessageTypeTemplateEdit v-if="showRegionDetailComponent == 'MessageTypeTemplateEdit'" :template="data"
          :item="regionDetailId" :isSubRegionOpen="isSubRegionOpen" @saved="refresh(true, false)">
        </MessageTypeTemplateEdit>
      </div>
    </div>
  </div>
</template>
