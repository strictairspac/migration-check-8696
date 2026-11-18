import json,hashlib,math
from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone,timedelta
from src.constants.enums import TYPES
class Cancelled(Exception):pass
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def key_digest(row):return digest([row['sample_code'],row['test_name']])
def validate_rules(rules):
 if not isinstance(rules,list) or len(rules)!=5:raise ValueError('必须为五个目标字段各配置一条映射')
 targets=[]
 for rule in rules:
  if not isinstance(rule,dict) or set(rule)!={'source','target','type','required'}:raise ValueError('映射须包含source/target/type/required')
  target=rule['target']
  if not isinstance(target,str) or target not in TYPES or rule['type']!=TYPES[target]:raise ValueError('目标字段或类型不匹配')
  if not isinstance(rule['source'],str) or not 1<=len(rule['source'])<=60:raise ValueError('源字段名无效')
  if not isinstance(rule['required'],bool) or (target!='unit' and not rule['required']):raise ValueError('除unit外均为必填目标字段')
  targets.append(target)
 if len(set(targets))!=5:raise ValueError('目标字段不可重复')
 return rules

def convert(value,kind,required):
 if value is None or (isinstance(value,str) and not value.strip()):
  if required:raise ValueError('null_required')
  return None
 if kind=='text':
  v=str(value).strip()
  if len(v)>160:raise ValueError('text_too_long')
  return v
 if kind=='decimal':
  try:
   d=Decimal(str(value))
   if not d.is_finite() or abs(d)>Decimal('1000000000'):raise ValueError('invalid_decimal')
   return str(d.quantize(Decimal('0.000001')))
  except (InvalidOperation,TypeError):raise ValueError('invalid_decimal')
 if kind=='datetime':
  try:
   dt=datetime.fromisoformat(str(value))
   if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone(timedelta(hours=8)))
   return dt.astimezone(timezone.utc).isoformat(timespec='seconds')
  except (ValueError,TypeError):raise ValueError('invalid_datetime')
 raise ValueError('invalid_type')

def migrate(rows,rules,chunk_size,progress=lambda p:None):
 validate_rules(rules)
 if not 1<=chunk_size<=500 or len(rows)>2000:raise ValueError('迁移配额超限')
 accepted=[];rejected=[];seen=set();chunks=[]
 for start in range(0,len(rows),chunk_size):
  chunk=rows[start:start+chunk_size]
  for offset,source in enumerate(chunk):
   try:
    target={}
    for rule in rules:
     if rule['source'] not in source:raise ValueError('missing_column:'+rule['source'])
     try:target[rule['target']]=convert(source[rule['source']],rule['type'],rule['required'])
     except ValueError as e:raise ValueError(rule['target']+':'+str(e))
    key=key_digest(target)
    if key in seen:raise ValueError('duplicate_natural_key:sample_code+test_name')
    seen.add(key);accepted.append(target)
   except (ValueError,TypeError) as e:rejected.append({'row_number':start+offset+1,'reason':str(e),'source':source})
  item={'chunk':len(chunks)+1,'processed':start+len(chunk),'accepted':len(accepted),'rejected':len(rejected)}
  chunks.append(item);progress(item)
 if not rows:progress({'chunk':0,'processed':0,'accepted':0,'rejected':0})
 return {'accepted_rows':accepted,'rejected_rows':rejected,'row_hashes':[digest(r) for r in accepted],'checksum':digest(accepted),'chunks':chunks,'source_count':len(rows),'accepted_count':len(accepted),'rejected_count':len(rejected)}

def make_backup(result,run_id,batch_name):
 return {'version':1,'run_id':run_id,'batch_name':batch_name,'rows':result['accepted_rows'],'row_hashes':result['row_hashes'],'checksum':result['checksum'],'kind':'logical-json-snapshot'}
def validate_backup(backup,expected,run_id):
 if not isinstance(backup,dict) or backup.get('version')!=1 or backup.get('run_id')!=run_id or backup.get('kind')!='logical-json-snapshot':raise ValueError('备份版本或运行编号不一致')
 rows=backup.get('rows')
 if not isinstance(rows,list) or len(rows)>2000:raise ValueError('备份行数无效')
 if backup.get('checksum')!=digest(rows) or backup.get('checksum')!=expected:raise ValueError('备份checksum不匹配，拒绝恢复')
 if backup.get('row_hashes')!=[digest(r) for r in rows]:raise ValueError('逐行摘要不匹配')
 if any(not isinstance(r,dict) or set(r)!=set(TYPES) for r in rows):raise ValueError('目标schema不一致')
 if len({key_digest(r) for r in rows})!=len(rows):raise ValueError('备份自然键重复')
 return rows
