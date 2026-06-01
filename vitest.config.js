import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    include: ['tests/**/*.test.js', 'tests/**/*.spec.js'],
    pool: 'forks',
    singleFork: true,
  },
});
