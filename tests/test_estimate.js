const assert = require('node:assert/strict');
const test = require('node:test');
const planner = require('../static/estimate.js');

test('one short still includes analysis of the complete source', () => {
  assert.ok(planner.estimate(60, 1).analysisLow >= 22);
  const one = planner.estimate(60, 1), ten = planner.estimate(60, 10);
  assert.equal(ten.analysisLow, one.analysisLow);
  assert.equal(ten.reviewedClips, 10);
  assert.match(one.basis, /analysis-stage-only/);
  assert.equal(one.calibrated, false);
});

test('all ten counts produce ordered planning ranges', () => {
  let previous = 0;
  for (let n = 1; n <= 10; n++) {
    const value = planner.estimate(60, n);
    assert.ok(value.analysisLow >= previous && value.analysisHigh >= value.analysisLow);
    previous = value.analysisLow;
    assert.match(planner.range(value), /mapping \+/);
  }
});

test('invalid count and source length do not produce a misleading estimate', () => {
  for (const [minutes, count] of [[0, 1], [721, 1], [NaN, 1], [60, 0], [60, 11], [60, 1.5]])
    assert.equal(planner.estimate(minutes, count), null);
});

test('long stream routing is automatic above three hours and never promises an unmeasured latency',()=>{
  assert.notEqual(planner.estimate(180,5).mode,'long_stream');
  for(const [minutes,count]of [[181,7],[240,8],[600,20],[720,24]]){
    const value=planner.estimate(minutes,5);
    assert.equal(value.mode,'long_stream');assert.equal(value.scoutCount,count);
    assert.equal(value.heavyConcurrency,1);assert.equal(value.calibrated,false);
    assert.match(planner.range(value),/timing uncalibrated/);
    assert.equal(value.analysisLow,undefined);
  }
});
