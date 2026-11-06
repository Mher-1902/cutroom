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
  for (const [minutes, count] of [[0, 1], [121, 1], [NaN, 1], [60, 0], [60, 11], [60, 1.5]])
    assert.equal(planner.estimate(minutes, count), null);
});
