<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import debounce from 'lodash.debounce';
import H1Region from '../atoms/H1Region.vue';
import { fi, is } from 'date-fns/locale';
import _ from 'lodash';


const { t } = useI18n();

const props = defineProps({
  company_id: Number,
  config_data: Object,
});

const emit = defineEmits(['show-subregion', 'change']);
const { $ExploitationApiService, $ConfiglistApiService } = useNuxtApp();

const loading = ref(false);

const showRegion = ref(false)
const openSubRegion = ref(false);
const saving = ref(false);
const attemptedSave = ref(false);

const config_id = ref(null);
const token = ref(null);
const name = ref(null);
const mail_send_service = ref(null)
const mail_send_smtp_server = ref(null)
const mail_send_smtp_port = ref(null)
const mail_send_mail = ref(null)
const mail_send_user = ref(null)
const mail_send_contact_footer = ref(null)

const company_emails = ref([])
const comm_use_types = ref([])

const use_TLS = ref(false)
const use_SSL = ref(false)

const isValid = () => {
  //if (mail_send_service.value == null) return false;
  if (mail_send_smtp_server.value == null) return false;
  if (mail_send_smtp_port.value == null) return false;
  for (const mail of company_emails.value) {
    if (mail.mail_send_mail == null) return false;
    if (mail.mail_send_user == null) return false;
    if (mail.use_type == null) return false;
  }
  return true;
}

const removeCompanyEmail = (index) => {
  company_emails.value.splice(index, 1);
};

const save = async () => {
  attemptedSave.value = true;
  if (!isValid()) return
  try {
    saving.value = true;

    let data = {
      id: config_id.value,
      token: token.value,
      name: name.value,
      company_id: props.company_id,
      mail_send_service: mail_send_service.value,
      mail_send_smtp_server: mail_send_smtp_server.value,
      mail_send_smtp_port: mail_send_smtp_port.value,
      mail_send_contact_footer: mail_send_contact_footer.value,
      use_TLS: use_TLS.value,
      use_SSL: use_SSL.value,
      config_emails_data: company_emails.value,
    };

    if (config_id.value || props.company_id) {
      data = await $ExploitationApiService.saveCompanyConfig(data);
    }
    emit('change', data);
  } catch (error) {
    console.error(error)
  } finally {
    saving.value = false;
    attemptedSave.value = false;
  }
}

const getData = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('communication/communication-use-type')
    comm_use_types.value = response.results.map(item => ({
      label: item.name,
      value: item.id,
      token: item.token
    }))
  } catch (error) {
    console.error(error)
  }
  if (props.config_data != null) {
    config_id.value = props.config_data?.id || null;
    token.value = props.config_data?.token || null;
    name.value = props.config_data?.name || null;
    mail_send_service.value = props.config_data.mail_send_service;
    mail_send_smtp_server.value = props.config_data.mail_send_smtp_server;
    mail_send_smtp_port.value = props.config_data.mail_send_smtp_port;
    mail_send_contact_footer.value = props.config_data.mail_send_contact_footer;
    use_TLS.value = props.config_data.use_TLS ?? false;
    use_SSL.value = props.config_data.use_SSL ?? false;
    company_emails.value = props.config_data.company_config_emails;
  } else {
    config_id.value = null;
    token.value = null;
    name.value = null;
    mail_send_service.value = null;
    mail_send_smtp_server.value = null;
    mail_send_smtp_port.value = null;
    mail_send_contact_footer.value = null;
    use_TLS.value = false;
    use_SSL.value = false;
    company_emails.value = [];
  }

}

const defaultMailChange = (mail) => {
  company_emails.value.forEach(email => {
    email.is_default = email.id === mail.id;
  });
}

const addCompanyEmail = () => {
  company_emails.value.push({
    id: null,
    mail_send_mail: null,
    mail_send_user: null,
    use_type: null
  });
}

onMounted(() => {
  console.log("AddCompanyConfig mounted", props.config_data);
  getData()
});

watch(() => props.isSubRegionOpen, (newValue) => {
  openSubRegion.value = newValue;
});

watch(() => props.config_data, (newValue) => {
  if (newValue) {
    config_id.value = newValue.id;
    token.value = newValue.token;
    name.value = newValue.name;
    mail_send_service.value = newValue.mail_send_service;
    mail_send_smtp_server.value = newValue.mail_send_smtp_server;
    mail_send_smtp_port.value = newValue.mail_send_smtp_port;
    mail_send_contact_footer.value = newValue.mail_send_contact_footer;
    use_TLS.value = newValue.use_TLS ?? false;
    use_SSL.value = newValue.use_SSL ?? false;
  } else {
    config_id.value = null;
    token.value = null;
    name.value = null;
    mail_send_service.value = null;
    mail_send_smtp_server.value = null;
    mail_send_smtp_port.value = null;
    mail_send_contact_footer.value = null;
    use_TLS.value = false;
    use_SSL.value = false;
  }
});


</script>
<!-- TODO: CONTINUAR CON LA CONFIGURACIÓ PARA CONTINUAR CON EL ENVIO DE MAILS -->
<template>
  <div id="wrapper" class="text-base">
    <div class="pr-5 justify-between mb-2 w-full">
      <div class="transition-all duration-500 ease" :class="{ 'mr-[47%]': openSubRegion }">
        <div class="flex justify-between items-center mb-3" :class="{ 'grid grid-cols-2': openSubRegion }">
          <H1Region>{{ $t('service_block.company_config') }}</H1Region>
        </div>
        <div class="field mb-3 grid grid-cols-2 gap-5">
          <div>
            <p class="flex items-center block text-sm font-medium text-slate-600 mb-2">
              <abbr :title="t('service_block.config_id')">
                <Icon name="fa6-solid:circle-info" class="text-slate-500" />
              </abbr>
              <span class="ml-2">
                {{ $t('common.identification') }} *
              </span>
            </p>
            <input type="text" v-model="token" :class="{ 'invalid': attemptedSave && (token == '' || token == null) }"
              class="input" placeholder="customers01" />
          </div>
          <!-- <div>
            <label class="flex items-center">
              <input type="radio" value="smtp" v-model="mail_send_service" class="mr-2">
              {{ $t('SMTP') }}
            </label>
            <label class="flex items-center">
              <input type="radio" value="gmail" v-model="mail_send_service" class="mr-2">
              {{ $t('Gmail') }}
            </label>
          </div> -->
          <div>
            <p class="flex items-center block text-sm font-medium text-slate-600 mb-2">
              <span class="ml-2">
                {{ $t('service_block.config_name') }} *
              </span>
            </p>
            <input type="text" v-model="name" :class="{ 'invalid': attemptedSave && (name == '' || name == null) }"
              class="input" placeholder="Config CUSTOMERS S.A." />
          </div>
          <div>
            <p class="flex items-center block text-sm font-medium text-slate-600 mb-2">
              <span class="ml-2">
                {{ $t('service_block.config_server') }} *
              </span>
            </p>
            <input type="text" v-model="mail_send_smtp_server"
              :class="{ 'invalid': attemptedSave && (mail_send_smtp_server == '' || mail_send_smtp_server == null) }"
              class="input" placeholder="smtp.example.com" />
          </div>
          <div>
            <p class="flex items-center block text-sm font-medium text-slate-600 mb-2">
              <span class="ml-2">
                {{ $t('service_block.config_port') }} *
              </span>
            </p>
            <input type="number" v-model="mail_send_smtp_port"
              :class="{ 'invalid': attemptedSave && (mail_send_smtp_port == '' || mail_send_smtp_port == null) }"
              class="input" placeholder="123" />
          </div>
          <div>
            <p class="flex items-center block text-sm font-medium text-slate-600 mb-2">
              <span class="ml-2">
                {{ $t('service_block.config_mail_contact_footer') }} ({{ t('common.optional') }})
              </span>
            </p>
            <input type="email" v-model="mail_send_contact_footer" class="input" placeholder="example@example.com" />
          </div>
          <div></div>
          <div class="flex items-center gap-2 mt-2">
            <input id="use_TLS" type="checkbox" v-model="use_TLS" />
            <label for="use_TLS" class="text-sm font-medium text-slate-600">TLS</label>
          </div>
          <div class="flex items-center gap-2 mt-2">
            <input id="use_SSL" type="checkbox" v-model="use_SSL" />
            <label for="use_SSL" class="text-sm font-medium text-slate-600">SSL</label>
          </div>
          <div class="col-span-2 mt-2 pt-4 border-t border-slate-200">
            <p class="text-sm font-semibold text-slate-600 mb-3">{{ $t('common.emails') }}</p>
            <div class="space-y-3">
              <div v-for="(mail, index) in company_emails" :key="mail.id ?? index"
                class="relative rounded-lg">
                <button type="button" @click="removeCompanyEmail(index)"
                  class="absolute right-3 top-3 flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                  :title="$t('common.delete')">
                  <Icon name="fa6-solid:trash" class="text-sm" />
                </button>
                <div class="flex items-center gap-2">
                  <input type="radio" name="default_bank" class="ml-2" :value="mail.id"
                  :checked="mail.is_default" @change="defaultMailChange(mail)" />
                  <div class=" p-4 bg-slate-50">

                    <div class="grid gap-4 grid-cols-3">
                      <div class="flex flex-col justify-between h-full">
                        <label class="mb-2 block text-sm font-medium text-slate-600">
                          {{ $t('service_block.config_mail') }} *
                        </label>
                        <input type="email" v-model="mail.mail_send_mail" class="input" placeholder="example@example.com" />
                      </div>
                      <div class="flex flex-col justify-between h-full">
                        <label class="mb-2 block text-sm font-medium text-slate-600">
                          {{ $t('service_block.config_mail_sender') }} ({{ t('common.optional') }})
                        </label>
                        <input type="email" v-model="mail.mail_send_user" class="input" placeholder="example@example.com" />
                      </div>
                      <div class="flex flex-col justify-between h-full">
                        <label class="mb-2 block text-sm font-medium text-slate-600">
                          {{ $t('common.use_type') }} *
                        </label>
                        <v-select class="block w-full custom-select" v-model="mail.use_type"
                          :options="comm_use_types" :clearable="false" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div>
                <button @click="addCompanyEmail()"
                  class="w-full px-2 py-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-100 flex items-center justify-center gap-2">
                  <Icon name="fa6-solid:plus" /> {{ $t('common.add_email') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <hr class="my-2" />
        <div class="flex flex-row-reverse mt-4">
          <button @click="save" class="button-primary">
            <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
          </button>
        </div>
      </div>

      <div role="region" id="subregion" v-if="showRegion"
        class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-y-auto overflow-x-hidden fixed top-0 right-0 w-[47%] z-10"
        :class="{ 'translate-x-0': openSubRegion, 'translate-x-full': !openSubRegion }">
        <div id="region_nav" class="mb-3 px-3">
          <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
            <Icon name="fa6-solid:angles-right" class="text-slate-500" />
          </button>
        </div>
        <div class="pl-10">

        </div>
      </div>
    </div>
  </div><!-- end wrapper -->
</template>
