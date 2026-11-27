import { computed, toValue } from 'vue';

// Nivells de la barra de fortalesa (1 feble … 4 forta)
const STRENGTH_LEVELS = [
  { key: 'weak', bar: 'bg-red-500', text: 'text-red-600' },
  { key: 'fair', bar: 'bg-orange-400', text: 'text-orange-600' },
  { key: 'good', bar: 'bg-yellow-400', text: 'text-yellow-700' },
  { key: 'strong', bar: 'bg-green-500', text: 'text-green-600' },
];

// Llargada en caràcters (punts de codi), com `len()` del backend: un emoji compta 1, no 2
const codePointLength = (text) => [...text].length;

/**
 * Requisits i fortalesa d'una contrasenya nova (perfil, recuperació...).
 *
 * - Requisits: els mateixos que valida el backend (auth/validators.py): mínim 8 caràcters i un
 *   número per a tothom i, amb `strict` (superusuaris), també una lletra i un caràcter especial.
 * - Fortalesa: orientativa, no bloqueja. Punts per llargada (8/12/16/20) i tipus de caràcter
 *   (minúscula, majúscula, número, especial); en resta si conté el nom d'usuari, i és feble si
 *   és curta d'un sol tipus o un sol caràcter repetit.
 */
export function usePasswordRules(password, { strict = false, username = '' } = {}) {
  const rules = computed(() => {
    const pwd = toValue(password) || '';
    const list = [
      { key: 'min_length', ok: codePointLength(pwd) >= 8 },
      { key: 'number', ok: /\p{N}/u.test(pwd) },
    ];
    if (toValue(strict)) {
      list.push(
        { key: 'letter', ok: /\p{L}/u.test(pwd) },
        { key: 'special', ok: /[^\p{L}\p{N}\s]/u.test(pwd) },
      );
    }
    return list;
  });

  const rulesOk = computed(() => rules.value.every(rule => rule.ok));

  const strength = computed(() => {
    const pwd = toValue(password) || '';
    if (!pwd) return null;
    const classes = [/\p{Ll}/u, /\p{Lu}/u, /\p{N}/u, /[^\p{L}\p{N}\s]/u].filter(re => re.test(pwd)).length;
    const length = codePointLength(pwd);
    let score = [8, 12, 16, 20].filter(min => length >= min).length + Math.max(classes - 1, 0);
    const name = (toValue(username) || '').toLowerCase();
    if (name.length >= 3 && pwd.toLowerCase().includes(name)) score -= 2;
    // Un sol tipus de caràcter només és feble si és curta (una frase llarga sí que és segura)
    if ((classes <= 1 && length < 16) || /^(.)\1*$/u.test(pwd)) score = Math.min(score, 1);
    const level = score <= 1 ? 1 : score <= 3 ? 2 : score === 4 ? 3 : 4;
    return { level, ...STRENGTH_LEVELS[level - 1] };
  });

  return { rules, rulesOk, strength };
}
