ROLES=('admin','operator','viewer')
STATUSES=('queued','running','completed','failed','cancelled')
TYPES={'sample_code':'text','test_name':'text','result_value':'decimal','unit':'text','measured_at':'datetime'}
# 交班核对单状态：active 可续页；revoked 权限被撤回；expired 到期；reclaimed 版本已回收
SHEET_STATUSES=('active','revoked','expired','reclaimed')
SHEET_SECTIONS=('runs','targets','rejected')
DEFAULT_SHEET_TTL_MINUTES=240
MIN_SHEET_TTL_MINUTES=5
MAX_SHEET_TTL_MINUTES=1440
MAX_PAGE_SIZE=200
