export const ROLES={admin:'管理员',operator:'操作员',viewer:'观察员'};
export const STATUSES={queued:'等待处理',running:'迁移中',completed:'已完成',failed:'失败',cancelled:'已取消'};
export const TYPES={sample_code:'text',test_name:'text',result_value:'decimal',unit:'text',measured_at:'datetime'};
export const SHEET_STATUSES={active:'生效中',revoked:'权限撤回',expired:'已到期',reclaimed:'已回收'};
export const SHEET_SECTIONS={runs:'已完成运行',targets:'目标行',rejected:'拒绝行'};
export const SHEET_INVALID={
 sheet_revoked:'核对权限已撤回：本单不能继续续页，重新授权也不会启用旧单，请新开核对单',
 sheet_expired:'核对单已到期：续页已关闭，请重新开单',
 sheet_reclaimed:'核对单版本已回收：快照已清空，请重新开单',
 version_reclaimed:'当前版本已回收：续页无法补读，请重新开单',
};
