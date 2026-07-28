import js from '@eslint/js';
import eslintConfigPrettier from 'eslint-config-prettier';
import globals from 'globals';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import vuePlugin from 'eslint-plugin-vue';

const appFiles = ['**/*.{js,mjs,cjs,ts,mts,cts,vue}'];

export default [
  {
    ignores: ['dist/**', 'coverage/**'],
  },
  js.configs.recommended,
  ...tsPlugin.configs['flat/recommended'],
  ...vuePlugin.configs['flat/recommended'],
  {
    files: appFiles,
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        ecmaVersion: 'latest',
        parser: tsParser,
        sourceType: 'module',
      },
    },
  },
  {
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      complexity: ['error', 20],
      'spaced-comment': ['error', 'always'],
      'vue/multi-word-component-names': 'off',
      'vue/require-default-prop': 'off',
    },
  },
  eslintConfigPrettier,
  {
    files: ['**/*.spec.ts', '**/*.spec.vue'],
    rules: {
      complexity: 'off',
      'vue/one-component-per-file': 'off',
    },
  },
];
