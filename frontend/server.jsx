// Server-render entry point.
//
// Micronaut Views React resolves a view name to a named export of this module,
// so everything that can be a render root is exported here: `App` for the
// browser pages, and one component per transactional email. That is why the
// emails need no Node process and no build-time HTML compilation — they are
// rendered by the same GraalJS context as the pages.
import 'web-streams-polyfill/dist/polyfill';
import './polyfills';

import React from 'react';
import * as ReactDOMServer from 'react-dom/server.browser';

import { App } from './src/App';
import { NewAccountEmail } from './emails/NewAccountEmail';
import { ResetPasswordEmail } from './emails/ResetPasswordEmail';
import { TestEmail } from './emails/TestEmail';

export { App, NewAccountEmail, ResetPasswordEmail, TestEmail, React, ReactDOMServer };
