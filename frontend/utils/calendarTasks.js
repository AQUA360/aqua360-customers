// Classes literals (Tailwind no detecta les que es construeixen amb el nom del color).
const TASK_COLOR_CLASSES = {
  black: { dot: 'bg-black', chip: 'border-black bg-slate-100', icon: 'text-black' },
  slate: { dot: 'bg-slate-500', chip: 'border-slate-400 bg-slate-50', icon: 'text-slate-500' },
  gray: { dot: 'bg-gray-500', chip: 'border-gray-400 bg-gray-50', icon: 'text-gray-500' },
  zinc: { dot: 'bg-zinc-500', chip: 'border-zinc-400 bg-zinc-50', icon: 'text-zinc-500' },
  stone: { dot: 'bg-stone-500', chip: 'border-stone-400 bg-stone-50', icon: 'text-stone-500' },
  red: { dot: 'bg-red-500', chip: 'border-red-400 bg-red-50', icon: 'text-red-500' },
  rose: { dot: 'bg-rose-500', chip: 'border-rose-400 bg-rose-50', icon: 'text-rose-500' },
  pink: { dot: 'bg-pink-500', chip: 'border-pink-400 bg-pink-50', icon: 'text-pink-500' },
  fuchsia: { dot: 'bg-fuchsia-500', chip: 'border-fuchsia-400 bg-fuchsia-50', icon: 'text-fuchsia-500' },
  orange: { dot: 'bg-orange-500', chip: 'border-orange-400 bg-orange-50', icon: 'text-orange-500' },
  amber: { dot: 'bg-amber-500', chip: 'border-amber-400 bg-amber-50', icon: 'text-amber-500' },
  yellow: { dot: 'bg-yellow-500', chip: 'border-yellow-400 bg-yellow-50', icon: 'text-yellow-500' },
  lime: { dot: 'bg-lime-500', chip: 'border-lime-400 bg-lime-50', icon: 'text-lime-500' },
  green: { dot: 'bg-green-500', chip: 'border-green-400 bg-green-50', icon: 'text-green-500' },
  emerald: { dot: 'bg-emerald-500', chip: 'border-emerald-400 bg-emerald-50', icon: 'text-emerald-500' },
  teal: { dot: 'bg-teal-500', chip: 'border-teal-400 bg-teal-50', icon: 'text-teal-500' },
  cyan: { dot: 'bg-cyan-500', chip: 'border-cyan-400 bg-cyan-50', icon: 'text-cyan-500' },
  sky: { dot: 'bg-sky-500', chip: 'border-sky-400 bg-sky-50', icon: 'text-sky-500' },
  blue: { dot: 'bg-blue-500', chip: 'border-blue-400 bg-blue-50', icon: 'text-blue-500' },
  indigo: { dot: 'bg-indigo-500', chip: 'border-indigo-400 bg-indigo-50', icon: 'text-indigo-500' },
  violet: { dot: 'bg-violet-500', chip: 'border-violet-400 bg-violet-50', icon: 'text-violet-500' },
  purple: { dot: 'bg-purple-500', chip: 'border-purple-400 bg-purple-50', icon: 'text-purple-500' },
};
const DEFAULT_COLOR = { dot: 'bg-sky-500', chip: 'border-sky-400 bg-sky-50', icon: 'text-sky-500' };

const TASK_TEXT_COLOR_CLASSES = {
  black: 'text-black',
  slate: 'text-slate-700',
  gray: 'text-gray-700',
  zinc: 'text-zinc-700',
  stone: 'text-stone-700',
  red: 'text-red-600',
  rose: 'text-rose-600',
  pink: 'text-pink-600',
  fuchsia: 'text-fuchsia-600',
  orange: 'text-orange-600',
  amber: 'text-amber-600',
  yellow: 'text-yellow-700',
  lime: 'text-lime-700',
  green: 'text-green-700',
  emerald: 'text-emerald-700',
  teal: 'text-teal-700',
  cyan: 'text-cyan-700',
  sky: 'text-sky-700',
  blue: 'text-blue-700',
  indigo: 'text-indigo-700',
  violet: 'text-violet-700',
  purple: 'text-purple-700',
};

/** Return the task dot color class, falling back to sky for unknown colors. */
export const taskDotClass = (color) => (TASK_COLOR_CLASSES[color] || DEFAULT_COLOR).dot;
/** Return task chip border and background classes with a sky fallback. */
export const taskChipClass = (color) => (TASK_COLOR_CLASSES[color] || DEFAULT_COLOR).chip;
/** Return the task icon text color class, falling back to sky for unknown colors. */
export const taskIconClass = (color) => (TASK_COLOR_CLASSES[color] || DEFAULT_COLOR).icon;
/** Return the task title text color class, or empty when unset/unknown. */
export const taskTextClass = (textColor) => TASK_TEXT_COLOR_CLASSES[textColor] || '';

export const RECURRENCE_FREQUENCIES = ['daily', 'weekly', 'monthly', 'yearly'];

// 0 = dilluns ... 6 = diumenge, com al backend (dateutil)
export const WEEKDAY_KEYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
