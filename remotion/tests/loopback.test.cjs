const {test}=require('node:test');
const assert=require('node:assert/strict');
require('../loopback.cjs');
const net=require('node:net');
test('Remotion servers cannot bind all network interfaces',async()=>{
  const server=net.createServer();
  await new Promise(resolve=>server.listen({port:0,host:'0.0.0.0'},resolve));
  assert.equal(server.address().address,'127.0.0.1');
  await new Promise(resolve=>server.close(resolve));
});
