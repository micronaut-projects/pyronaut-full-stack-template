// jsdom does not define TextEncoder/TextDecoder, and `react-dom/server.browser`
// needs them at import time. This is the same gap GraalJS has, which
// webpack.server.cjs fills with a ProvidePlugin for the server bundle.
const { TextDecoder, TextEncoder } = require('node:util');

if (!globalThis.TextEncoder) globalThis.TextEncoder = TextEncoder;
if (!globalThis.TextDecoder) globalThis.TextDecoder = TextDecoder;
