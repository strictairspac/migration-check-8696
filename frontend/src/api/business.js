import {api,post} from './client.js';
export const batches={list:()=>api('/batches'),save:(d,id)=>post('/batches'+(id?'/'+id:''),d,id?'PUT':'POST')};
export const mappings={list:()=>api('/mappings'),save:(d,id)=>post('/mappings'+(id?'/'+id:''),d,id?'PUT':'POST')};
export const runs={list:()=>api('/runs'),run:d=>post('/runs',d),cancel:id=>post('/runs/'+id+'/cancel',{}),targets:id=>api('/runs/'+id+'/targets'),restore:(id,backup)=>post('/runs/'+id+'/restore',{backup})};
export const sheets={
 list:()=>api('/sheets'),
 detail:id=>api('/sheets/'+id),
 open:d=>post('/sheets',d),
 newVersion:id=>post('/sheets/'+id+'/versions',{}),
 page:(id,section,params={})=>{const q=new URLSearchParams({page_size:params.page_size||50,...(params.page?{page:params.page}:{})});return api(`/sheets/${id}/pages/${section}?${q}`);},
 permission:()=>api('/review/permission'),
 setPermission:(enabled,reason)=>post('/review/permission',{enabled,reason},'PUT'),
 reclaim:(id,version)=>post('/sheets/'+id+'/reclaim',{version:version??null}),
};
