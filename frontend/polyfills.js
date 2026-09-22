// GraalJS does not expose the browser URL globals React Router uses during
// server rendering, nor TextEncoder/TextDecoder (supplied by webpack's
// ProvidePlugin) or the web streams React's renderer needs. This small
// WHATWG-compatible subset stays in the server bundle only; the browser bundle
// uses the platform implementations.
//
// TODO(upstream): these polyfills are hand-rolled in every Pyronaut project
// that server-renders React, including pyronaut-petclinic. They belong in
// micronaut-views-react. See PLAN.md section 12.

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
