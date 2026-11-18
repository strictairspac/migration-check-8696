from src.config.database import Base,engine,Session
from src.models.identity import User,Audit
from src.models.batch import Batch
from src.models.mapping import Mapping
from src.models.run import Run,TargetRow
from src.utils.security import hash_password
RULES=[{'source':a,'target':b,'type':c,'required':True} for a,b,c in [('委托号','sample_code','text'),('检测项','test_name','text'),('结果','result_value','decimal'),('单位','unit','text'),('时间','measured_at','datetime')]]
def seed():
 Base.metadata.create_all(engine)
 with Session() as s:
  for role in ('admin','operator','viewer'):
   if not s.query(User).filter_by(email=role+'@migration.local').first():s.add(User(email=role+'@migration.local',role=role,password=hash_password('Migrate2026!')))
  good=[{'委托号':f'JS-20261117-{i:03d}','检测项':'拉伸强度','结果':str(420+i/10),'单位':'MPa','时间':'2026-11-17T09:00:00+08:00'} for i in range(1,13)]
  bad=[good[0],{'委托号':'JS-BAD-01','检测项':'拉伸强度','结果':'四百二十','单位':'MPa','时间':'2026-11-17T09:00:00+08:00'},{'委托号':'JS-BAD-02','检测项':'拉伸强度','结果':None,'单位':'MPa','时间':'2026-11-17T09:00:00+08:00'},{'委托号':'JS-BAD-03','检测项':'拉伸强度','结果':'430','时间':'2026-11-17T09:00:00+08:00'}]
  seeds=[('见山日班检验结果',good,'lab-results-20261117.json','12条正常检测结果'),('旧字段异常样本',good[:2]+bad,'legacy-edge-20261117.json','重复自然键、非法数字、空值与缺列'),('空批次验收',[],'empty-results.json','空输入可完成备份与恢复')]
  for name,rows,file,desc in seeds:
   if not s.query(Batch).filter_by(name=name).first():s.add(Batch(name=name,rows=rows,source_file=file,description=desc))
  s.flush()
  for i,(name,_,_,_) in enumerate(seeds):
   mname=['检验结果标准映射','异常隔离复核映射','空批次映射'][i]
   if not s.query(Mapping).filter_by(name=mname).first():s.add(Mapping(name=mname,batch_id=s.query(Batch).filter_by(name=name).one().id,rules=RULES,chunk_size=4,note='sample_code + test_name 为自然键'))
  s.commit();counts={m.__tablename__:s.query(m).count() for m in (User,Batch,Mapping,Run,TargetRow)};print(counts);return counts
if __name__=='__main__':seed()
