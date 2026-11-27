<script setup>
// Modal per canviar la contrasenya pròpia (s'obre des de la fitxa de l'usuari). Només canvia
// la de l'usuari que ha fet login; la dels altres es canvia des de la gestió d'usuaris (superusuaris).
import { ref, computed, watch, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const open = defineModel('open', { type: Boolean, default: false });

const props = defineProps({
  username: { type: String, default: '' },
  // Els superusuaris tenen requisits de contrasenya més estrictes
  isSuperuser: { type: Boolean, default: false },
});

const emit = defineEmits(['changed']);

const { t } = useI18n();
const toast = useToast();
const { $UserApiService } = useNuxtApp();

const currentPassword = ref('');
const newPassword = ref('');
const repeatPassword = ref('');
const saving = ref(false);
const attemptedSave = ref(false);
const currentInput = ref(null);

// Mateixos requisits que la gestió d'usuaris (el backend també els valida): mínim 8
// caràcters i un número per a tothom i, per als superusuaris, també una lletra i un caràcter especial
const passwordRules = computed(() => {
  const pwd = newPassword.value || '';
  const rules = [
    { key: 'min_length', ok: pwd.length >= 8 },
    { key: 'number', ok: /\p{N}/u.test(pwd) },
  ];
  if (props.isSuperuser) {
    rules.push(
      { key: 'letter', ok: /\p{L}/u.test(pwd) },
      { key: 'special', ok: /[^\p{L}\p{N}\s]/u.test(pwd) },
    );
  }
  return rules;
});

const rulesOk = computed(() => passwordRules.value.every(rule => rule.ok));

// Fortalesa orientativa (1 feble … 4 forta): llargada i varietat de caràcters, penalitzant
// si conté el nom d'usuari o és d'un sol tipus de caràcter. No bloqueja res: ho fan les regles.
const STRENGTH_LEVELS = [
  { key: 'weak', bar: 'bg-red-500', text: 'text-red-600' },
  { key: 'fair', bar: 'bg-orange-400', text: 'text-orange-600' },
  { key: 'good', bar: 'bg-yellow-400', text: 'text-yellow-700' },
  { key: 'strong', bar: 'bg-green-500', text: 'text-green-600' },
];

const strength = computed(() => {
  const pwd = newPassword.value || '';
  if (!pwd) return null;
  const classes = [/\p{Ll}/u, /\p{Lu}/u, /\p{N}/u, /[^\p{L}\p{N}\s]/u].filter(re => re.test(pwd)).length;
  let score = [8, 12, 16, 20].filter(min => pwd.length >= min).length + Math.max(classes - 1, 0);
  const username = (props.username || '').toLowerCase();
  if (username.length >= 3 && pwd.toLowerCase().includes(username)) score -= 2;
  // Un sol tipus de caràcter només és feble si és curta (una frase llarga sí que és segura)
  if ((classes <= 1 && pwd.length < 16) || /^(.)\1*$/u.test(pwd)) score = Math.min(score, 1);
  const level = score <= 1 ? 1 : score <= 3 ? 2 : score === 4 ? 3 : 4;
  return { level, ...STRENGTH_LEVELS[level - 1] };
});
const passwordsMatch = computed(() => newPassword.value === repeatPassword.value);
const showMismatch = computed(() => !!repeatPassword.value && !passwordsMatch.value);

const resetState = () => {
  currentPassword.value = '';
  newPassword.value = '';
  repeatPassword.value = '';
  attemptedSave.value = false;
};

watch(open, async (isOpen) => {
  if (!isOpen) {
    resetState();
    return;
  }
  await nextTick();
  currentInput.value?.focus();
});

const close = () => {
  if (saving.value) return;
  open.value = false;
};

const isValid = () => {
  if (!currentPassword.value) {
    toast.warning(t('user_group.current_password_required'));
    return false;
  }
  if (!rulesOk.value) {
    toast.warning(t('user_group.password_rules_not_met'));
    return false;
  }
  if (!passwordsMatch.value) {
    toast.warning(t('user_group.password_not_match'));
    return false;
  }
  if (newPassword.value === currentPassword.value) {
    toast.warning(t('user_group.new_password_same_as_current'));
    return false;
  }
  return true;
};

const save = async () => {
  attemptedSave.value = true;
  if (!isValid()) return;
  saving.value = true;
  try {
    // Els errors del backend (p. ex. contrasenya actual incorrecta) ja surten com a avís
    await $UserApiService.changeOwnPassword(currentPassword.value, newPassword.value);
    toast.success(t('user_group.own_password_changed'));
    saving.value = false;
    open.value = false;
    emit('changed');
  } catch (error) {
    console.error(error);
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <Teleport to="body">
    <div v-if="open" @keydown.esc="close">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="close" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" aria-labelledby="change-password-title" @click="close">
        <form class="bg-white rounded-lg shadow-xl p-6 max-w-md w-full relative" autocomplete="on"
          @click.stop @submit.prevent="save">
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.close')" @click="close">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <h2 id="change-password-title" class="text-lg font-semibold text-slate-800 pr-8">
            {{ t('user_group.change_password') }}
          </h2>
          <p class="text-sm text-slate-500 mt-1 mb-5">{{ t('user_group.change_password_sessions_help') }}</p>

          <!-- Camp ocult amb el nom d'usuari perquè els gestors de contrasenyes sàpiguen de quin compte és -->
          <input type="text" name="username" autocomplete="username" :value="username" class="hidden" readonly aria-hidden="true" tabindex="-1" />

          <div class="flex flex-col gap-4">
            <div>
              <label for="current-password" class="block text-sm font-medium text-slate-500 mb-2">{{ t('user_group.current_password') }}</label>
              <input id="current-password" ref="currentInput" v-model="currentPassword" type="password" class="input w-full"
                autocomplete="current-password"
                :class="{ 'invalid': attemptedSave && !currentPassword }" />
            </div>

            <div>
              <label for="new-password" class="block text-sm font-medium text-slate-500 mb-2">{{ t('user_group.new_password') }}</label>
              <input id="new-password" v-model="newPassword" type="password" class="input w-full"
                autocomplete="new-password"
                :class="{ 'invalid': attemptedSave && !rulesOk }" />
              <!-- Barra de fortalesa (orientativa) -->
              <div v-if="strength" class="mt-2 flex items-center gap-3">
                <div class="flex flex-1 gap-1" aria-hidden="true">
                  <span v-for="n in 4" :key="n" class="h-1.5 flex-1 rounded-full transition-colors"
                    :class="n <= strength.level ? strength.bar : 'bg-slate-200'" />
                </div>
                <span class="text-xs font-medium whitespace-nowrap" :class="strength.text" aria-live="polite">
                  {{ t('user_group.password_strength') }}: {{ t(`user_group.password_strength_level.${strength.key}`) }}
                </span>
              </div>
              <ul class="mt-2 text-sm flex flex-col gap-1">
                <li v-for="rule in passwordRules" :key="rule.key" class="flex items-center gap-x-2"
                  :class="rule.ok ? 'text-green-600' : 'text-slate-500'">
                  <Icon :name="rule.ok ? 'fa6-solid:circle-check' : 'fa6-regular:circle'" aria-hidden="true" />
                  {{ t(`user_group.password_rule.${rule.key}`) }}
                </li>
              </ul>
            </div>

            <div>
              <label for="repeat-password" class="block text-sm font-medium text-slate-500 mb-2">{{ t('user_group.repeat_password') }}</label>
              <input id="repeat-password" v-model="repeatPassword" type="password" class="input w-full"
                autocomplete="new-password"
                :class="{ 'invalid': (attemptedSave && !passwordsMatch) || showMismatch }" />
              <p v-if="showMismatch" class="mt-1 text-sm text-red-600">{{ t('user_group.password_not_match') }}</p>
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <button type="button" class="button-default" :disabled="saving" @click="close">
              {{ t('common.cancel') }}
            </button>
            <button type="submit" :disabled="saving" class="button-primary">
              <Icon v-if="saving" name="fa6-solid:spinner" class="animate-spin" />
              {{ t('user_group.change_password') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>
