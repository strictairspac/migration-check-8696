/** @typedef {{id:number,name:string,source_file:string,rows:object[]}} Batch */
/** @typedef {{id:number,name:string,batch_id:number,rules:object[],chunk_size:number}} Mapping */
/** @typedef {{id:number,name:string,status:'queued'|'running'|'completed'|'failed'|'cancelled',result:object|null}} Run */
/** @typedef {{id:number,name:string,batch_id:number,status:'active'|'revoked'|'expired'|'reclaimed',current_version:number,expires_at:string,invalid:null|{code:string,message:string},current_summary:object}} HandoverSheet */
/** @typedef {{version:number,current:boolean,reclaimed:boolean,summary:object,progress:Object<string,{delivered_pages:number,finished:boolean,total:number}>}} SheetVersionView */
/** @typedef {{page:number,page_size:number,offset:number,next_offset:number,total:number,count:number,finished:boolean,replay:boolean,delivered_key:string,rows:object[],section:string,remaining_seconds:number}} SheetPageEnvelope */
export {};
