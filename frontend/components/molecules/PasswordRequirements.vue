<script setup>
// Barra de fortalesa i llista de requisits d'una contrasenya nova (vegeu usePasswordRules).
import { useI18n } from 'vue-i18n';

defineProps({
  rules: { type: Array, required: true },
  strength: { type: Object, default: null },
});

const { t } = useI18n();
</script>

<template>
  <div>
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
      <li v-for="rule in rules" :key="rule.key" class="flex items-center gap-x-2"
        :class="rule.ok ? 'text-green-600' : 'text-slate-500'">
        <Icon :name="rule.ok ? 'fa6-solid:circle-check' : 'fa6-regular:circle'" aria-hidden="true" />
        {{ t(`user_group.password_rule.${rule.key}`) }}
      </li>
    </ul>
  </div>
</template>
