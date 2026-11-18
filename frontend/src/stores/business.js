import {batches,mappings,runs} from '../api/business.js';
export const store={batches:[],mappings:[],runs:[],user:null};
export async function refresh(){[store.batches,store.mappings,store.runs]=await Promise.all([batches.list(),mappings.list(),runs.list()]);}
