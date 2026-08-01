import type { NextConfig } from 'next';

const config: NextConfig = {
  // The corpus bundles are read from disk at request time (lib/corpus.ts), not
  // imported, so Next must be told to ship the content directory with the
  // serverless function.
  outputFileTracingIncludes: {
    '/doc/[docId]': ['./content/**/*'],
    '/api/**': ['./content/**/*'],
  },
};

export default config;
