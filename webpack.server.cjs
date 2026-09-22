// Server-render bundle, loaded by Micronaut Views React into a GraalJS context.
//
// It exports every component that can be a render root: `App` for the browser
// pages, and one component per transactional email. Micronaut Views React
// resolves a view name to an export of this single module, so both the page
// routes and `TemplateBody` email bodies are served from here.
const path = require('path');
const webpack = require('webpack');

module.exports = {
  entry: ['web-streams-polyfill/dist/polyfill', './frontend/server.jsx'],
  target: 'web',
  output: {
    path: path.resolve(__dirname, 'views'),
    filename: 'ssr-components.mjs',
    module: true,
    library: {type: 'module'},
    globalObject: 'globalThis'
  },
  experiments: {outputModule: true},
  module: {
    rules: [{
      test: /\.jsx?$/,
      exclude: /node_modules/,
      use: {loader: 'babel-loader'}
    }]
  },
  resolve: {extensions: ['.js', '.jsx']},
  plugins: [
    // GraalJS does not provide these; React's server renderer needs them.
    new webpack.ProvidePlugin({
      TextEncoder: ['text-encoding', 'TextEncoder'],
      TextDecoder: ['text-encoding', 'TextDecoder']
    })
  ]
};
