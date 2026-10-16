// Classes literals (Tailwind no detecta les que es construeixen amb el nom del color).
const TASK_COLOR_CLASSES = {
  gray: { dot: 'bg-gray-500', chip: 'border-gray-400 bg-gray-50' },
  green: { dot: 'bg-green-500', chip: 'border-green-400 bg-green-50' },
  yellow: { dot: 'bg-yellow-500', chip: 'border-yellow-400 bg-yellow-50' },
  amber: { dot: 'bg-amber-500', chip: 'border-amber-400 bg-amber-50' },
  orange: { dot: 'bg-orange-500', chip: 'border-orange-400 bg-orange-50' },
  red: { dot: 'bg-red-500', chip: 'border-red-400 bg-red-50' },
  blue: { dot: 'bg-blue-500', chip: 'border-blue-400 bg-blue-50' },
  purple: { dot: 'bg-purple-500', chip: 'border-purple-400 bg-purple-50' },
  pink: { dot: 'bg-pink-500', chip: 'border-pink-400 bg-pink-50' },
};
const DEFAULT_COLOR = { dot: 'bg-sky-500', chip: 'border-sky-400 bg-sky-50' };

export const taskDotClass = (color) => (TASK_COLOR_CLASSES[color] || DEFAULT_COLOR).dot;
export const taskChipClass = (color) => (TASK_COLOR_CLASSES[color] || DEFAULT_COLOR).chip;

export const RECURRENCE_FREQUENCIES = ['daily', 'weekly', 'monthly', 'yearly'];

// 0 = dilluns ... 6 = diumenge, com al backend (dateutil)
export const WEEKDAY_KEYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
