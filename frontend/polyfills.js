// GraalJS does not expose the browser URL globals React Router uses during server
// rendering. This small WHATWG-compatible subset stays in the server bundle only; the
// browser bundle uses the platform implementations. TextEncoder/TextDecoder come from
// webpack's ProvidePlugin.
//
// MessageChannel used to be here too, for React 19's scheduler. micronaut-views-react
// 6.3.0 installs it itself, in host-polyfills.js, evaluated before this bundle
// (micronaut-views#1201) -- so that half is gone.
//
// TODO(upstream): URL and URLSearchParams are still hand-rolled in every Pyronaut project
// that server-renders React, including pyronaut-petclinic, and measured to be load-bearing:
// without them every server-rendered route returns 500. They belong in micronaut-views-react
// alongside MessageChannel. Tracked in this repository's issues; see PLAN.md section 12.

if (!globalThis.URLSearchParams) {
  globalThis.URLSearchParams = class {
    constructor(value = '') {
      this.values = new Map();
      const query = String(value).replace(/^\?/, '');
      if (query) {
        for (const pair of query.split('&')) {
          const [key, val = ''] = pair.split('=');
          this.append(decodeURIComponent(key), decodeURIComponent(val));
        }
      }
    }
    append(key, value) {
      const values = this.values.get(String(key)) || [];
      values.push(String(value));
      this.values.set(String(key), values);
    }
    get(key) {
      const values = this.values.get(String(key));
      return values && values.length ? values[0] : null;
    }
    getAll(key) {
      return [...(this.values.get(String(key)) || [])];
    }
    has(key) {
      return this.values.has(String(key));
    }
    delete(key) {
      this.values.delete(String(key));
    }
    toString() {
      return [...this.values]
        .flatMap(([key, values]) =>
          values.map((value) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
        )
        .join('&');
    }
  };
}

if (!globalThis.URL) {
  globalThis.URL = class {
    constructor(value, base = 'http://localhost') {
      let text = String(value);
      if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(text)) {
        text = `${String(base).replace(/\/$/, '')}/${text.replace(/^\//, '')}`;
      }
      const match = text.match(/^([^:]+:\/\/[^/]+)(\/[^?#]*)?(\?[^#]*)?(#.*)?$/);
      this.origin = match ? match[1] : '';
      this.pathname = (match && match[2]) || '/';
      this.search = (match && match[3]) || '';
      this.hash = (match && match[4]) || '';
      this.href = `${this.origin}${this.pathname}${this.search}${this.hash}`;
      this.searchParams = new globalThis.URLSearchParams(this.search);
    }
  };
}
