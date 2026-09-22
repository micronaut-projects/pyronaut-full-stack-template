import { defineConfig } from '@hey-api/openapi-ts';

// `openapi.json` is a BUILD ARTIFACT produced by `pyronaut process` — generating
// the client needs no running server, no database and no valid runtime
// configuration. See PLAN.md section 8.2.
export default defineConfig({
  input: './openapi.json',
  output: './frontend/src/client',
  plugins: [
    { name: '@hey-api/client-fetch', throwOnError: true },
    { name: '@hey-api/typescript', case: 'preserve' },
    { name: '@hey-api/sdk', operations: { strategy: 'byTags', methods: 'static' } }
  ]
});
