<script setup>
import { ca } from 'date-fns/locale';
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import { useI18n } from 'vue-i18n';
import ButtonOutline from '../atoms/ButtonOutline.vue';


const { t } = useI18n();
const router = useRouter();
const toast = useToast();
const { $DocumentManagerApiService, $apiManager } = useNuxtApp();


const props = defineProps({
    document: Number,
});

const pending = ref(true);
const error = ref(null);
const documentContent = ref("");
const document_id = ref(props.document? props.document: null)

const emit = defineEmits(['changed']);

const formatXml = (xml) => {
    const PADDING = "  "; // Indentation
    const reg = /(>)(<)(\/*)/g;
    let formatted = "";
    let pad = 0;

    xml = xml.replace(reg, "$1\n$2$3"); 
    xml.split("\n").forEach((node) => {
        let indent = 0;
        if (node.match(/.+<\/\w[^>]*>$/)) {
            indent = 0; 
        } else if (node.match(/^<\/\w/)) {
            pad -= 1; 
        } else if (node.match(/^<\w([^>]*[^/])?>.*$/)) {
            indent = 1; 
        }

        formatted += PADDING.repeat(pad) + node + "\n";
        pad += indent;
    });

    return formatted.trim();
};

const showDocument = async () => {
    pending.value = true;
    documentContent.value = "";
    try {
        const response = await $DocumentManagerApiService.viewDocument(document_id.value);
        
        const blob = new Blob([response], { type: 'application/xml' });
        const text = await blob.text();

        // Parse and format XML
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(text, "application/xml");

        if (xmlDoc.getElementsByTagName("parsererror").length) {
            throw new Error("Error parsing XML");
        }

        documentContent.value = formatXml(new XMLSerializer().serializeToString(xmlDoc));
        pending.value = false;
    } catch (err) {
        console.error("Error fetching document:", err);
        error.value = "common.error_load";
    }
};

const printDocument = async () => {
  try {
    const document_file = await $DocumentManagerApiService.getDetail(document_id.value)
    let file = await $DocumentManagerApiService.viewDocument(document_id.value);
    const link = document.createElement('a');
    const file_url = URL.createObjectURL(file);
    link.href = file_url;
    link.download = document_file.document_name;

    link.click();

    setTimeout(() => {
      window.URL.revokeObjectURL(file_url);
    }, 250);

  } catch (error) {
    console.log(error)
  }
}



onMounted(() => {
    
    showDocument()
});

watch(() => props.document, (newVal) => {
    document_id.value = newVal
    showDocument();
}, { immediate: true })


</script>

<template>
    <div class="p-6 bg-white shadow-md rounded-lg bg-sky-50 max-w-3xl mx-auto">
        <div class="flex justify-between items-center border-b pb-4 mb-4">
            <h2 class="text-2xl font-bold text-gray-800">
                {{ $t('common.doc') }}
            </h2>
            <button 
                class="flex items-center px-4 py-2 text-white bg-sky-500 hover:bg-sky-600 transition rounded-lg shadow-md"
                @click="printDocument">
                <Icon name="fa6-solid:download" class="mr-2" />
                {{ $t('common.download') }} {{ $t('common.doc') }}
            </button>
        </div>

        <div class="relative p-4 bg-gray-100 rounded-lg h-[60vh] overflow-auto">
            <div v-if="pending" class="text-gray-500 text-center">
                <p>{{ $t('common.loading') }}...</p>
            </div>
            <div v-else-if="error" class="text-red-500 text-center">{{ error }}</div>
            <pre v-else class="text-sm whitespace-pre-wrap break-words text-gray-700">
                {{ documentContent }}
            </pre>
        </div>
    </div>
</template>

<style scoped>
button {
    transition: all 0.3s ease-in-out;
}
</style>