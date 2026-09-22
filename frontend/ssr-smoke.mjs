// Smoke-checks the built server bundle the way Micronaut Views React uses it:
// resolve a view name to a named export of views/ssr-components.mjs and render
// it with props.
//
// This runs on Node, not GraalJS, so it does NOT prove GraalJS compatibility —
// that needs a running application. What it does prove, cheaply and in CI, is
// that the bundle exports every render root the Python code asks for and that
// each one renders without throwing. It already caught one real bug: the
// navigation links were mounted outside the router context.
//
// Run with: npm run verify:ssr   (after npm run build)

import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const bundlePath = path.resolve(here, '..', 'views', 'ssr-components.mjs');

const require = createRequire(import.meta.url);
if (!require('node:fs').existsSync(bundlePath)) {
  console.error(`No server bundle at ${bundlePath} — run "npm run build" first.`);
  process.exit(1);
}

const bundle = await import(bundlePath);
const { React, ReactDOMServer } = bundle;

// Every view name src/app/services/mail.py and src/app/controllers/views.py
// can ask for. Keep these two lists in step.
const REQUIRED_EXPORTS = [
  'App',
  'NewAccountEmail',
  'ResetPasswordEmail',
  'TestEmail',
  'React',
  'ReactDOMServer',
];

const failures = [];

for (const name of REQUIRED_EXPORTS) {
  if (!bundle[name]) failures.push(`missing export: ${name}`);
}

async function render(view, props) {
  const stream = await ReactDOMServer.renderToReadableStream(
    React.createElement(bundle[view], props)
  );
  return await new Response(stream).text();
}

function check(label, condition) {
  if (condition) {
    console.log(`  ok   ${label}`);
  } else {
    console.log(`  FAIL ${label}`);
    failures.push(label);
  }
}

const PAGES = [
  ['dashboard', '/', { user: { email: 'admin@example.com', fullName: 'Ada', isSuperuser: true } }],
  ['login', '/login', {}],
  ['signup', '/signup', {}],
  ['recoverPassword', '/recover-password', {}],
  ['resetPassword', '/reset-password?token=abc', { token: 'abc' }],
  ['items', '/items', { user: { email: 'a@example.com' }, items: [], count: 0 }],
  ['settings', '/settings', { user: { email: 'a@example.com', fullName: 'Ada' } }],
  ['admin', '/admin', { user: { email: 'a@example.com', isSuperuser: true }, users: [] }],
];

console.log('pages:');
for (const [page, url, data] of PAGES) {
  try {
    const html = await render('App', { page, url, data });
    check(`${page} renders`, html.length > 0 && html.includes('<html'));
  } catch (error) {
    check(`${page} renders (${error.message})`, false);
  }
}

const EMAILS = [
  ['TestEmail', { projectName: 'Acme', email: 'a@example.com' }],
  [
    'NewAccountEmail',
    { projectName: 'Acme', username: 'a@example.com', password: 'pw', link: 'https://acme.test/' },
  ],
  [
    'ResetPasswordEmail',
    {
      projectName: 'Acme',
      username: 'a@example.com',
      link: 'https://acme.test/reset-password?token=abc',
      validHours: 48,
    },
  ],
];

console.log('emails:');
for (const [view, props] of EMAILS) {
  try {
    const html = await render(view, props);
    check(`${view} renders`, html.includes('<html'));
    // An email carries no external stylesheet: everything must be inline.
    check(`${view} has no <link> tag`, !html.includes('<link'));
    check(`${view} uses inline styles`, html.includes('style="'));
  } catch (error) {
    check(`${view} renders (${error.message})`, false);
  }
}

if (failures.length) {
  console.error(`\n${failures.length} check(s) failed.`);
  process.exit(1);
}
console.log('\nAll server-render checks passed.');
