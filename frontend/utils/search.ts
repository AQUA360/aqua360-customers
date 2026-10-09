export const searchValues = {
  'Supply-Point': ['supplypoints', 'fa6-solid:street-view'],
  'Meter': ['meters', 'my-icon:meter-icon-black'],
  'Cluster': ['clusters', 'fa6-solid:list'],
  'Connection': ['connections', 'fa6-solid:plug'],
  'Connection-Request': ['connection-requests', 'fa6-solid:plug-circle-plus'],
  'SupplyCut': ['supply-cut', 'fa6-solid:scissors'],
  'Contract': ['contracts', 'fa6-solid:file-contract'],
  'ContractTerminationRequest': ['contract-terminations', 'fa6-solid:file-circle-xmark'],
  'ContractRequest': ['contract-requests', 'fa6-solid:file-circle-plus'],
  'Bail': ['bails', 'fa6-solid:money-bills'],
  'Person': ['persons', 'fa6-solid:users'],
  'ReadingBatch': ['reading-batches', 'fa6-solid:clipboard-list'],
  'Invoice': ['invoice', 'fa6-solid:file-invoice'],
  'Order': ['orders', 'fa6-solid:screwdriver-wrench'],
  'Operator': ['operators', 'healthicons:construction-worker'],
};

type Translation = {
  [language: string]: string;
};

const translationsMap: Record<string, Translation> = {
  token: { en: 'Ident.', cat: 'Ident.' },
  holder__token: { en: 'Contract Holder', cat: 'Titular del contracte' },
  holder__name: { en: 'Contract Holder', cat: 'Titular del contracte' },
  holder_full_name: { en: 'Contract Holder', cat: 'Titular del contracte' },
  holder__surname: { en: 'Contract Holder', cat: 'Titular del contracte' },
  tenant__token: { en: 'Tenant', cat: 'Inquilí del contracte' },
  tenant__name: { en: 'Tenant', cat: 'Inquilí del contracte' },
  tenant__surname: { en: 'Tenant', cat: 'Inquilí del contracte' },
  owner__token: { en: 'Owner', cat: 'Propietari del contracte' },
  owner__name: { en: 'Owner', cat: 'Propietari del contracte' },
  owner__surname: { en: 'Owner', cat: 'Propietari del contracte' },
  contract__token: { en: 'Contract Identifier', cat: 'Ident. del Contracte' },
  code: { en: 'Ident.', cat: 'Ident.' },
  code_gis: { en: 'GIS Code', cat: 'Codi GIS' },
  exploitation__token: { en: 'Exploitation Ident.', cat: 'Ident. d\'Explotació' },
  company__alias: { en: 'Company', cat: 'Empresa' },
  number: { en: 'Number', cat: 'Número' },
  supply_point__token: { en: 'Supply Point Ident.', cat: 'Ident. de Punt de Subministrament' },
  surname: { en: 'Surname', cat: 'Cognoms' },
  name: { en: 'Name', cat: 'Nom' },
  full_name: { en: 'Name', cat: 'Nom' },
  address_complete: { en: 'Address', cat: 'Adreça' },
  'Supply-Point': { en: 'Supply Point', cat: 'Punt de Subministrament' },
  Meter : { en: 'Meter', cat: 'Comptador' },
  Cluster : { en: 'Cluster', cat: 'Bateria' },
  Connection : { en: 'Connection', cat: 'Escomesa' },
  'Connection-Request' : { en: 'Connection Request', cat: 'Sol·licitud d\'Escomesa' },
  SupplyCut : { en: 'Supply Cut', cat: 'Tall de Subministrament' },
  Contract : { en: 'Contract', cat: 'Contracte' },
  ContractTerminationRequest : { en: 'Contract Termination Request', cat: 'Baixa de Contracte' },
  ContractRequest : { en: 'Contract Request', cat: 'Sol·licitud de Contracte' },
  Bail : { en: 'Bail', cat: 'Fiança' },
  Person : { en: 'Person', cat: 'Persona' },
  ReadingBatch : { en: 'Reading Batch', cat: 'Lot de Lectura' },
  Invoice : { en: 'Invoice', cat: 'Factura' },
  Order : { en: 'Order', cat: 'Ordre' },
  Operator : { en: 'Operator', cat: 'Operador' },
};

export const foundItemTranslation = (item: string, language: string = 'en'): { [key: string]: string } => {
  return {
    [language]: translationsMap[item]?.[language] ?? item,
  };
};


