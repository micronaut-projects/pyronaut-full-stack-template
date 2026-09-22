import { defineConfig } from '@hey-api/openapi-ts';

// `openapi.json` is a BUILD ARTIFACT produced by `pyronaut process` — generating
// the client needs no running server, no database and no valid runtime
// configuration. See PLAN.md section 8.2.
export default defineConfig({
  input: './openapi.yaml',
  output: './frontend/src/client',
  plugins: [
    { name: '@hey-api/client-fetch', throwOnError: true },
    { name: '@hey-api/typescript', case: 'preserve' },
    // Flat, tree-shakeable functions rather than the upstream template's
    // service classes. Upstream groups by OpenAPI tag and notes in its own
    // config that doing so "doesn't allow tree-shaking"; we would not get the
    // grouping anyway, because Swagger's @Tag never reaches the generated
    // OpenAPI document — see PLAN.md section 12.
    { name: '@hey-api/sdk' }
  ]
});
