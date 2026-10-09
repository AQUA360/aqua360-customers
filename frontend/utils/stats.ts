import { differenceInDays } from 'date-fns';

export const calculateMedian = (durations: number[]): number => {
  if (durations.length === 0) return 0;
  const sorted = [...durations].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
};

export const hasDateRangeWarning = (duration: number, median: number): boolean => {
  if (median === 0) return false;
  const diff = Math.abs(duration - median);
  return diff > 0.25 * median;
};

export const getReadingDuration = (reading: any): number | null => {
  const start = reading.previous_reading_date || reading.date_from;
  const end = reading.reading_date || reading.date_to;
  if (start && end) {
    return differenceInDays(new Date(end), new Date(start));
  }
  return null;
}

export const getInvoiceDuration = (invoice: any): number | null => {
  const start = invoice.period_from;
  const end = invoice.period_to;
  if (start && end) {
    return differenceInDays(new Date(end), new Date(start));
  }
  return null;
}
