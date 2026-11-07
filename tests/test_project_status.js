const test=require('node:test');
const assert=require('node:assert/strict');
const status=require('../static/project-status.js');
test('queued jobs explain the active project instead of displaying 0 percent',()=>{
 const job={id:'new',status:'queued',progress:0};
 const other={id:'active',status:'running',name:'Earlier project',stage:'Editing'};
 const view=status.describe(job,[job,other],{gpu_waiting:true});
 assert.equal(view.progressLabel,'Queued');
 assert.match(view.detail,/Earlier project/);assert.match(view.detail,/Editing/);
 assert.doesNotMatch(view.detail,/model server/);
});
test('a running job distinguishes memory waiting from numerical progress',()=>{
 const job={id:'active',status:'running',progress:40,stage:'Analyzing',events:[]};
 assert.equal(status.describe(job,[job],{gpu_waiting:true}).progressLabel,'Waiting');
 assert.equal(status.describe(job,[job],{gpu_waiting:false}).progressLabel,'40%');
});
test('import failures show the actual blocker immediately',()=>{
 const job={id:'failed',status:'failed',stage:'Needs attention',progress:2,error:'YouTube requires an authorized session'};
 assert.match(status.describe(job,[job],{}).detail,/authorized session/);
});
