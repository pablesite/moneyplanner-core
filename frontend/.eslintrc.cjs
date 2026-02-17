module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier',
  ],
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@typescript-eslint/parser',
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  ignorePatterns: ['dist', 'coverage'],
  overrides: [
    {
      files: ['src/**/*.spec.ts', 'e2e/**/*.spec.ts'],
      rules: {
        complexity: 'off',
        'vue/one-component-per-file': 'off',
      },
    },
  ],
  rules: {
    'vue/multi-word-component-names': 'off',
    'vue/require-default-prop': 'off',
    '@typescript-eslint/no-explicit-any': 'off',
    '@typescript-eslint/no-unused-vars': 'off',
    complexity: ['error', 20],
    'spaced-comment': ['error', 'always'],
  },
};
