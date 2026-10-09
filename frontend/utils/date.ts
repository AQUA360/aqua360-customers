// ~/utils/date.ts

/**
 * Formats a date string into the 'dd/mm/YYYY' format.
 * 
 * @param dateString - The original date string.
 * @returns The formatted date string.
 */
export const formatDate = (dateString: string | null | undefined): string => {
  if (dateString == null || dateString === '') return '-';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('ca-ES', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
}

/**
 * Formats a date string into the 'dd/mm/YYYY HH:mm' format.
 * 
 * @param dateString - The original date string.
 * @returns The formatted date time string.
 */
export const formatDateTime = (dateTimeString: string | null | undefined): string => {
  if (dateTimeString == null || dateTimeString === '') return '-';
  const date = new Date(dateTimeString);
  if (isNaN(date.getTime())) return '-';
  return date.toLocaleString('ca-ES', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).replace(',', '');
}

export const formatTime = (timeString: string | null | undefined): string => {
  if (timeString == null || timeString === '') return '-';
  const time = new Date(timeString);
  if (isNaN(time.getTime())) return '-';
  return time.toLocaleTimeString('ca-ES', {
    hour: '2-digit',
    minute: '2-digit'
  }).replace(',', '');
}

/**
 * Formats a date string into a verbose format like "Dijous, 9 de maig de 2024".
 * 
 * @param dateString - The original date string.
 * @returns The formatted date string in a verbose format.
 */
export const formatDateVerbose = (dateString: string | null | undefined): string => {
  if (dateString == null || dateString === '') return '-';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('ca-ES', {
    weekday: 'long', // Display the day of the week
    year: 'numeric',
    month: 'long', // Display the full name of the month
    day: 'numeric'
  });
}
