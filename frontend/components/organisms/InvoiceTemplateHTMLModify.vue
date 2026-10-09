<script setup>
//InvoiceTemplateHTMLModify.vue
import { ref, onMounted, computed } from 'vue';
import debounce from 'lodash.debounce';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useNuxtApp } from '#app';

import HTMLEditorHelper from '../molecules/HTMLEditorHelper.vue';


const { t } = useI18n();
const router = useRouter();
const { $apiManager, $InvoiceTemplateApiService, $DocumentManagerApiService } = useNuxtApp();

const props = defineProps({
  id: {
    type: Number,
    required: true
  }
});

const templateData = ref(null);
const templateFile = ref('');
const pending = ref(true);
const error = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const editableHtmlContent = ref(null);
const head = ref(null);
const body = ref(null);
const footer = ref(null);



const getTemplate = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $InvoiceTemplateApiService.getDetail(props.id);
    templateData.value = result;
    await getFile();
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const getFile = async () => {
  try {
    const fileBlob = await $DocumentManagerApiService.viewDocument(
      templateData.value.file_template.id
    );
    let htmlContent = await fileBlob.text();
    templateFile.value = htmlContent;

    head.value = templateFile.value.substring(templateFile.value.indexOf("<!DOCTYPE html>"), templateFile.value.indexOf("</head>") + 7);
    body.value = templateFile.value.substring(templateFile.value.indexOf("<body"), templateFile.value.indexOf("</body>") + 7);
    footer.value = templateFile.value.substring(templateFile.value.indexOf("<footer"), templateFile.value.indexOf("</footer>") + 8);

    editableHtmlContent.value = [head, body, footer]
  } catch (err) {
    error.value = "Error loading file";
    console.error(err);
  }
};

const saveTemplate = async () => {
  try {
    if (!templateFile.value) return;

    const finalHtml = head.value + body.value + footer.value;

    const blob = new Blob([finalHtml], { type: 'text/html' });
    const file = new File([blob], "template.html", { type: "text/html" });

    let saveData = {
      id: templateData.value.id,
      file_template_html: file,
    };

    const response = await $InvoiceTemplateApiService.save(saveData);
  } catch (error) {
    console.error('Error saving template:', error);
  }
};


const showPDF = async () => {
  try {
    const combinedHtml = head.value + body.value + footer.value;

    if (combinedHtml && combinedHtml.length > 0) {
      // Replace placeholders
      let final_html = combinedHtml.replace(/{{(.*?)}}/g, 'XXXX');
      final_html = final_html.replace(
        /{% if.*?%}/g,
        '<span style="color:red;">[Conditional Content]</span>'
      );
      final_html = final_html.replace(
        /{% for.*?%}/g,
        '<span style="color:blue;">[Looping Content]</span>'
      );
      final_html = final_html.replace(/{% load i18n %}/g, '');
      final_html = final_html.replace(/{% language 'ca' %}/g, '');
      final_html = final_html.replace(/{% endlanguage %}/g, '');
      final_html = final_html.replace(/{% endblock %}/g, '');
      final_html = final_html.replace(/{% blocktrans %}/g, '');
      final_html = final_html.replace(/{% endblocktrans %}/g, '');
      final_html = final_html.replace(/{% comment %}/g, '');
      final_html = final_html.replace(/{% endcomment %}/g, '');

      let file_data = {
        html_template: final_html,
      };

      const response = await $InvoiceTemplateApiService.getTemplatePDF(
        file_data
      );

      const pdfBlob = new Blob([response], { type: 'application/pdf' });
      const blobFileUrl = URL.createObjectURL(pdfBlob);

      const pdfContainer = document.querySelector('.invoice-preview');
      const iframe = document.createElement('iframe');
      iframe.src = blobFileUrl;
      iframe.width = '90%';
      iframe.style.height = '98vh';
      iframe.style.border = 'none';
      iframe.style.overflow = 'hidden';
      iframe.style.background = 'white';
      iframe.setAttribute('scrolling', 'no');

      pdfContainer.innerHTML = '';
      pdfContainer.appendChild(iframe);

      setTimeout(() => {
        window.URL.revokeObjectURL(blobFileUrl);
      }, 250);
    }
  } catch (error) {
    console.error('Error displaying PDF:', error);
    alert(t('Error displaying PDF. Please check the console.')); // User feedback
  }
};

const handleChange = (event) => {
  //templateFile.value = event.target.value;
}


const debouncedShowPDF = debounce(() => {
  showPDF();
}, 500);

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

watch(() => templateFile.value, () => {
  debouncedShowPDF();
});

watch([
    head,
    body,
    footer
  ],
  () => {
    debouncedShowPDF();
  },
  { deep: true });

onMounted(() => {
  getTemplate();
  showPDF()
});
</script>

<template>
  <div>
    <h1 class="text-xl font-bold mb-4">{{ t('common.modify') }} {{ t('common.template') }}: {{ templateData?.name }}</h1>

    <div v-if="pending">{{ t('common.loading') }}...</div>
    <div v-else-if="error">{{ t('common.error_load') }}</div>
    <div v-else class="pb-2">
      <div class="flex flex-row-reverse">
            <button class="button-default" @click="toggleRegion(true)">
              <Icon name="fa6-solid:info" class="mr-2" />
              {{ $t('common.info') }}
            </button>
          </div>
      <div class="grid grid-cols-[5fr,4fr] gap-4 border-b border-slate-200 overflow-y-auto no-scrollbar h-[90hv] pb-2">

        <div
          class="bg-white rounded-lg overflow-hidden flex flex-col"
        >
          <details class="p-4">
            <summary class="font-semibold text-lg text-gray-700 cursor-pointer">
              {{ t('editor_block.head') }}
            </summary>
            <textarea
              v-model="head"
              class="w-full h-64 border border-gray-300 p-2 rounded-md"
            />
          </details>

          <details class="p-4">
            <summary class="font-semibold text-lg text-gray-700 cursor-pointer">
              {{ t('editor_block.body') }}
            </summary>
            <textarea
              v-model="body"
              class="w-full h-96 border border-gray-300 p-2 rounded-md"
            />
          </details>

          <details class="p-4">
            <summary class="font-semibold text-lg text-gray-700 cursor-pointer">
              {{ t('editor_block.footer') }}
            </summary>
            <textarea
              v-model="footer"
              class="w-full h-48 border border-gray-300 p-2 rounded-md"
            />
          </details>
        </div>



        <div class="p-2 bg-white">
          
          <div class="origin-top-left overflow-auto">
            <div class="invoice-preview"></div>
          </div>
        </div>


      </div>


      <div class="mt-4 flex flex-row-reverse gap-2">
        <button @click="router.back()" class="button-default">{{ t('common.cancel') }}</button>
        <button @click="saveTemplate" class="button-primary">{{ t('common.save') }}</button>
      </div>
    </div>
  </div>
  <div v-if="showRegion" role="region" id="right_page"
    class="z-10 fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="px-10">
      <HTMLEditorHelper />
    </div>
  </div>
</template>


<style lang="scss">
.invoice-preview {
  width: 100%;
  height: 100vh;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
}

.invoice-preview iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.no-scrollbar::-webkit-scrollbar {
    display: none;
}

.no-scrollbar {
    -ms-overflow-style: none;  
    scrollbar-width: none;  
}

</style>
