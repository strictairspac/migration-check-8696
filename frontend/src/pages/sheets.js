import {store} from '../stores/business.js';
import {esc,json} from '../utils/html.js';
import {table} from '../components/common/table.js';
import {sheets} from '../api/business.js';
import {SHEET_STATUSES, SHEET_SECTIONS, SHEET_INVALID} from '../constants/enums.js';

// 每个单据的本地续页游标与累计行，键为 sheetId:section
const paging={};
function key(sid,section){return sid+':'+section;}
function state(sid,section){
 const k=key(sid,section);
 if(!paging[k])paging[k]={nextPage:1,pageSize:20,rows:[],finished:false,loading:false,last:null};
 return paging[k];
}

// 开新版本或回收后，旧版本页码不再适用，重置该单全部续页游标
export function resetPaging(sid){
 for(const k of Object.keys(paging))if(k.startsWith(sid+':'))delete paging[k];
}

function sheetStatus(s){return `<span class="status ${s.status==='active'?'completed':s.status==='revoked'?'failed':s.status==='expired'?'cancelled':'cancelled'}">${SHEET_STATUSES[s.status]||s.status}</span>`;}

function invalidBanner(invalid){
 if(!invalid)return '';
 const text=SHEET_INVALID[invalid.code]||invalid.message||'核对单已失效';
 return `<div class="feedback error"><b>本单已失效 · ${esc(invalid.code)}</b><br>${esc(text)}${invalid.reason?`<br>原因：${esc(invalid.reason)}`:''}${invalid.expires_at?`<br>到期时间：${esc(invalid.expires_at)}`:''}</div>`;
}

export function sheetsPage(selectedId){
 const list=store.sheetList;
 const current=list.find(x=>x.id===Number(selectedId))||list[0];
 const canWrite=store.user.role!=='viewer';
 const isAdmin=store.user.role==='admin';
 const permOff=store.permission&&store.permission.enabled===false;
 return `<div class="split">
  <section>
   <h2>按批次开交班核对单</h2>
   <p>开单即冻结批次、运行、目标行与拒绝行快照；此后新迁移与备份恢复继续落库，都不改变本单。续页游标持久化，刷新或重启后仍可从下一页续查。</p>
   ${permOff?`<div class="feedback error"><b>核对权限已被管理员撤回</b><br>${esc(store.permission.reason||'暂停核对')}。撤回期间不能新开单或开新版本；已开单据全部失效，重新授权也不启用旧单。</div>`:''}
   <form id="sheet-form" ${permOff?'':''}>
    <label>核对单名称<input name="name" required placeholder="shift-20261117-handover" ${permOff?'disabled':''}></label>
    <label>源批次<select name="batch_id" ${permOff?'disabled':''}>${store.batches.map(b=>`<option value="${b.id}">${esc(b.name)}（${b.rows.length}行）</option>`).join('')}</select></label>
    <label>有效期（分钟，5-1440）<input name="ttl_minutes" type="number" min="5" max="1440" value="240" required ${permOff?'disabled':''}></label>
    <button type="submit" ${permOff?'disabled':''}>开单并冻结版本 →</button>
   </form>
   ${isAdmin?`<h3>管理员 · 核对权限</h3>
    <p>撤回后所有生效单据立即失效并拒绝续页；重新授权只允许开新单，不复活旧单。</p>
    <div class="actions">
     <button data-perm="off" ${permOff?'disabled':''}>撤回核对权限</button>
     <button class="quiet" data-perm="on" ${!permOff?'disabled':''}>重新授权（仅新单生效）</button>
    </div>
    <small id="perm-meta">${esc(store.permission.reason||('当前状态：'+(permOff?'已撤回':'已授权')))}</small>`:''}
  </section>
  <section>
   <h2>核对单册 <em>${list.length}</em></h2>
   ${table(['单据 / 批次','状态 / 到期','当前版本计数','操作'],list.map(sh=>[
    `<b>${esc(sh.name)}</b><small>#${sh.id} · 批次 ${sh.batch_id}<br>由 ${esc(sh.created_by)} 开</small>`,
    sheetStatus(sh)+`<small>${esc(sh.expires_at)}</small>`,
    sh.current_summary?`<small>运行 ${sh.current_summary.runs} · 目标 ${sh.current_summary.targets} · 拒绝 ${sh.current_summary.rejected}</small>`:'',
    `<button class="quiet" data-sheet="${sh.id}">查看 / 续页 →</button>`
   ]))}
   ${current?sheetDetail(current,canWrite,isAdmin):'<div class="empty">还没有核对单。在左侧按批次开一张。</div>'}
  </section>
 </div>`;
}

function sheetDetail(sh,canWrite,isAdmin){
 const detail=store._sheetDetail&&store._sheetDetail[sh.id];
 return `<div class="sheet-detail" id="sheet-detail-${sh.id}" data-sheet-id="${sh.id}">
  <div class="result-head"><div><span class="eyebrow">HANDOVER #${sh.id} / FROZEN VERSION v${sh.current_version}</span><h3>${esc(sh.name)}</h3></div>
   ${canWrite?`<button class="quiet" data-new-version="${sh.id}" ${sh.status!=='active'?'disabled title="单据已失效，不能开新版本"':''}>开新版本（纳入最新落库）</button>`:''}
   ${isAdmin?`<button class="quiet" data-reclaim="${sh.id}" ${sh.status==='active'?'disabled title="到期或撤回后才能回收"':''}>回收当前旧版本</button>`:''}
  </div>
  ${invalidBanner(sh.invalid)}
  ${detail?versionsBlock(detail):'<p class="muted">正在读取版本与续页进度…</p>'}
  <div class="sheet-sections">${Object.entries(SHEET_SECTIONS).map(([sec,label])=>sectionBlock(sh,sec,label)).join('')}</div>
 </div>`;
}

function versionsBlock(detail){
 return `<details open><summary>版本与续页进度（共 ${detail.versions.length} 个版本）</summary>
  ${table(['版本','状态','摘要(运行/目标/拒绝)','各分区已交付页'],detail.versions.map(v=>[
   `v${v.version}${v.current?'（当前）':''}`,
   v.reclaimed?'<span class="status cancelled">已回收</span>':'<span class="status completed">可读</span>',
   `${v.summary.runs} / ${v.summary.targets} / ${v.summary.rejected}`,
   esc(Object.entries(v.progress).map(([sec,p])=>`${SHEET_SECTIONS[sec]}:${p.delivered_pages}页${p.finished?'(完)':''}`).join('；'))
  ]))}
 </details>`;
}

function sectionBlock(sh,section,label){
 const st=state(sh.id,section);
 const disabled=!!sh.invalid;
 return `<div class="sheet-section" data-section="${section}">
  <h3>${esc(label)} ${st.finished?'<span class="status completed">已读完</span>':st.rows.length?`<span class="status running">续页中</span>`:''}</h3>
  <div class="actions">
   <button data-next-page="${sh.id}" data-section="${section}" ${disabled||st.loading||st.finished?'disabled':''}>${st.rows.length?'续查下一页':'开始续页（每页'+st.pageSize+'行）'}</button>
   <button class="quiet" data-replay-page="${sh.id}" data-section="${section}" ${disabled||!st.rows.length?'disabled':''}>重放本页</button>
   <small class="muted">已取 ${st.rows.length} 行 · 下一页第 ${st.nextPage} 页</small>
  </div>
  <div class="sheet-page-meta" id="meta-${sh.id}-${section}">${st.last?pageMeta(st.last):'尚未取页'}</div>
  <pre id="rows-${sh.id}-${section}" class="sheet-rows">${st.rows.length?json(st.rows.slice(-st.pageSize)):'// 点击开始续页，读取开单时冻结的版本'}</pre>
 </div>`;
}

function pageMeta(envelope){
 return `第 ${envelope.page} 页 · 偏移 ${envelope.offset}-${envelope.next_offset} · 本页 ${envelope.count} 行 · 全量 ${envelope.total} 行 · ${envelope.finished?'已到末页':'还有后续'} · 版本 v${envelope.version}${envelope.replay?' · 重放（未新增游标）':''}`;
}

export function bindSheetPage(rerender){
 const detailEl=document.querySelector('[id^="sheet-detail-"]');
 if(!detailEl)return;
 const sid=Number(detailEl.dataset.sheetId);

 document.querySelectorAll('[data-sheet]').forEach(b=>b.onclick=()=>rerender(Number(b.dataset.sheet)));

 const form=document.getElementById('sheet-form');
 form?.addEventListener('submit',async e=>{
  e.preventDefault();
  const d=Object.fromEntries(new FormData(form));
  d.batch_id=Number(d.batch_id);d.ttl_minutes=Number(d.ttl_minutes);
  try{await sheets.open(d);await rerender();}catch(err){alert(err.message);}
 });

 document.querySelectorAll('[data-perm]').forEach(b=>b.onclick=async()=>{
  const enabled=b.dataset.perm==='on';
  const reason=enabled?'管理员重新授权，仅新单生效':prompt('撤回核对权限的原因（将记录到审计与单据失效信息）','季度复核暂停')||'';
  try{await sheets.setPermission(enabled,reason);await rerender(sid);}catch(err){alert(err.message);}
 });

 document.querySelector('[data-new-version]')?.addEventListener('click',async()=>{
  try{await sheets.newVersion(sid);resetPaging(sid);await rerender(sid);}catch(err){alert(err.message);}
 });
 document.querySelector('[data-reclaim]')?.addEventListener('click',async()=>{
  if(!confirm('回收将清空当前版本快照载荷（保留摘要与翻页凭据），续页会提示重新开单。确认？'))return;
  try{await sheets.reclaim(sid,null);resetPaging(sid);await rerender(sid);}catch(err){alert(err.message);}
 });

 document.querySelectorAll('[data-next-page],[data-replay-page]').forEach(btn=>{
  btn.onclick=async()=>{
   const section=btn.dataset.section;
   const replay=btn.hasAttribute('data-replay-page');
   const st=state(sid,section);
   st.loading=true;
   try{
    const params={page_size:st.pageSize};
    if(replay)params.page=st.last.page;
    const envelope=await sheets.page(sid,section,params);
    st.last=envelope;
    if(!replay){
     if(envelope.count>0)st.rows.push(...envelope.rows);
     st.nextPage=envelope.page+1;
     st.finished=envelope.finished;
    }
    st.loading=false;
    await rerender(sid);
   }catch(err){
    st.loading=false;
    // 失效（撤回/到期/回收）等 409：刷新以渲染失效原因与重开提示
    if(err.status===409){await rerender(sid);}
    alert(err.message);
   }
  };
 });
}

export async function ensureDetail(id){
 if(!id)return;
 if(!store._sheetDetail)store._sheetDetail={};
 try{store._sheetDetail[id]=await sheets.detail(id);}catch(e){store._sheetDetail[id]=null;}
}
