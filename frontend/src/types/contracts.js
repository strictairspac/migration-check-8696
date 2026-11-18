/** @typedef {{id:number,name:string,source_file:string,rows:object[]}} Batch */
/** @typedef {{id:number,name:string,batch_id:number,rules:object[],chunk_size:number}} Mapping */
/** @typedef {{id:number,name:string,status:'queued'|'running'|'completed'|'failed'|'cancelled',result:object|null}} Run */
export {};
