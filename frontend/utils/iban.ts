export function hideIban(iban: string): string {
    if (typeof iban !== 'string') {
        return ''; 
    }

    const cleanIban = iban.replace(/\s/g, '');
    const ibanLength = cleanIban.length;


    const firstPart = cleanIban.slice(0, 8);
    const lastPart = cleanIban.slice(-8);
    const hiddenPart = '********';

    const combined = firstPart + hiddenPart + lastPart;

    // Add spaces every 4 characters
    return combined.replace(/(.{4})/g, '$& ').trim();
}

export function formatIban(iban: string): string {
    if (typeof iban !== 'string') {
        return ''; 
    }
    const cleanIban = iban.replace(/\s/g, '');
    return cleanIban.replace(/(.{4})/g, '$& ').trim();
}
