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
 assert.equal(status.describe(job,[job],{}).progressLabel,'Stopped');
});
test('planning failures display a stopped state instead of a stuck percentage',()=>{
 const job={id:'failed',status:'failed',stage:'Needs attention',progress:50,error:'No videos reached rendering',failure_summary:{stage:'planning'}};
 const view=status.describe(job,[job],{});
 assert.equal(view.stage,'Edit planning failed');assert.equal(view.progressLabel,'Stopped');
 assert.match(view.detail,/No videos reached rendering/);
});
test('an incomplete review explains recovery without exposing model jargon',()=>{
 const job={id:'failed',status:'failed',stage:'Needs attention',progress:65,error:'vLLM reached its output limit. The incomplete response was not accepted.'};
 const view=status.describe(job,[job],{});
 assert.match(view.detail,/drafts are saved/);assert.match(view.detail,/Resume run/);
 assert.doesNotMatch(view.detail,/vLLM|output limit/);
});
test('automatic long-stream coverage shows failures and completed shorts accurately',()=>{
 const job={processing_strategy:{mode:'long_stream',scout_count:20},scout_progress:{total:20,complete:14,failed:1},clips:[{}],config:{count:5}};
 assert.match(status.scouting(job),/14\/20 sections scouted/);
 assert.match(status.scouting(job),/1 need attention/);
 assert.match(status.scouting(job),/1\/5 shorts ready/);
 assert.match(status.scouting(job),/one heavy task/);
 assert.equal(status.scouting({}),'');
});
test('resource cooldown is an automatic pause with saved progress',()=>{
 const job={id:'x',status:'running',progress:32,resource_pause:'Your Mac needs a cooling break'};
 const view=status.describe(job,[job],{});
 assert.match(view.stage,/cooling/);assert.match(view.detail,/resumes/);
});
