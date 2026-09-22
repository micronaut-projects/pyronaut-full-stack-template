// Browser hydration entry point. `Micronaut.rootProps` is injected into the
// server-rendered document by Micronaut Views React and carries the same model
// the controller returned, so the client tree starts from the server's state
// instead of re-fetching it.
import React from 'react';
import { hydrateRoot } from 'react-dom/client';

import { App } from './src/App';

hydrateRoot(document, React.createElement(App, globalThis.Micronaut.rootProps));
