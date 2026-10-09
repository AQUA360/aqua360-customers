export const AdjustmentConditionOperationChoices = {
  'eq': 'pricing_condition_block.equal',
  'ne': 'pricing_condition_block.not_equal',
  'gt': 'pricing_condition_block.greater_than',
  'lt': 'pricing_condition_block.less_than',
  'ge': 'pricing_condition_block.greater_or_equal',
  'le': 'pricing_condition_block.less_or_equal',
  'in': 'pricing_condition_block.in',
  'ni': 'pricing_condition_block.not_in',
  'is_true': 'pricing_condition_block.is_true',
  'is_false': 'pricing_condition_block.is_false',
  'is_null': 'pricing_condition_block.is_null',
  'is_not_null': 'pricing_condition_block.is_not_null'
};

export const AdjustmentConditionQuantityDefaultChoices = {
  'consumption': ['billing_block.consumption',''],
  'consumption_days': ['billing_block.consumption_days',''],
  'consumption_leakage': ['billing_block.consumption_leak',''],
  'consumption_responsible': ['billing_block.consumption_responsible',''],
  'reading_batch_id': ['billing_block.reading_batch_id',''],
  'contract.total_persons': ['pricing_block.adj_total_persons',''],
  'contract.use_type': ['pricing_block.adj_use_type','contract/contract-use-type/'],
  'contract.client_type': ['pricing_block.adj_client_type','contract/contract-client-type/'],
  'contract.category': ['pricing_block.adj_category',''],
  'contract.communication_type': ['pricing_block.adj_communication_type',''],
  'supply_point.type': ['pricing_block.adj_supply_type', 'service/supply-point-type/'],
};

