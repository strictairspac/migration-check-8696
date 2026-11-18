import {batches,mappings,runs,sheets} from '../api/business.js';
export const store={batches:[],mappings:[],runs:[],sheetList:[],permission:{enabled:true},user:null};
export async function refresh(){
 [store.batches,store.mappings,store.runs,store.sheetList]=await Promise.all([batches.list(),mappings.list(),runs.list(),sheets.list()]);
 try{store.permission=await sheets.permission();}catch(e){store.permission={enabled:true};}
}
