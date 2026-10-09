export function uniqid(prefix: string = '', moreEntropy: boolean = true): string {
    const base = Date.now().toString(16);
    let uniqueId = prefix + base;

    if (moreEntropy) {
        uniqueId += Math.floor(Math.random() * 1000000000).toString(4);
    }

    return uniqueId;
}