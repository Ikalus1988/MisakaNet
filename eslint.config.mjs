import astro from 'eslint-plugin-astro';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  ...astro.configs['flat/recommended'],
  {
    rules: {
      'astro/no-html-style-link': 'error',
    },
  }
);
