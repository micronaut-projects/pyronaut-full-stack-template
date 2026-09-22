// Does React 19's renderToReadableStream complete under plain Node, with no
// bundle and no polyfills involved?
import React from 'react';
import * as S from 'react-dom/server.browser';
const el = React.createElement('h1', null, 'hello');
const t = setTimeout(() => { console.log('TIMEOUT: render did not settle in 10s'); process.exit(3); }, 10000);
try {
  const stream = await S.renderToReadableStream(el, { onError(e) { console.log('onError:', e.message); } });
  const html = await new Response(stream).text();
  clearTimeout(t);
  console.log('OK:', html);
} catch (e) {
  clearTimeout(t);
  console.log('THREW:', e.message);
}
