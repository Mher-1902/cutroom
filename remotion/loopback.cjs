// Remotion's default Studio bind is all interfaces. Keep Cutroom tooling local.
const net = require('node:net');
const originalListen = net.Server.prototype.listen;
net.Server.prototype.listen = function (...args) {
  if (typeof args[0] === 'object' && args[0] !== null && 'port' in args[0]) {
    args[0] = {...args[0], host: '127.0.0.1'};
  } else if (typeof args[0] === 'number') {
    if (typeof args[1] === 'string') args[1] = '127.0.0.1';
    else args.splice(1, 0, '127.0.0.1');
  }
  return originalListen.apply(this, args);
};
