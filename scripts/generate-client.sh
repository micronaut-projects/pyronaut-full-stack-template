#!/usr/bin/env bash
# Generate the TypeScript API client from the OpenAPI document.
#
# The document is a BUILD ARTIFACT: `pyronaut process` writes it while
# compiling, from the route decorators and the @Serdeable dataclasses. Nothing
# starts here — no server, no database, no valid runtime configuration, and a
# contract mistake is a build failure rather than a surprise in the client.
#
# Compare the upstream FastAPI template, which imports and constructs the
# application to obtain the same file:
#   uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))"
set -euo pipefail

cd "$(dirname "$0")/.."

SPEC=$(ls __pyronaut__/classes/META-INF/swagger/*.yml 2>/dev/null | head -1)
if [ -z "$SPEC" ]; then
  echo "No OpenAPI document found. Run 'pyronaut process' first." >&2
  exit 1
fi

echo "Generating client from $SPEC"
cp "$SPEC" openapi.yaml
npx openapi-ts
