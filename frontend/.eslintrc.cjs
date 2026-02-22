// =============================================================================
// FGA CRM - ESLint Configuration (React 18 + TypeScript)
// =============================================================================

module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['react-refresh', '@typescript-eslint'],
  rules: {
    // React Refresh — warn si export non-component
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

    // TypeScript — pragmatique, pas dogmatique
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    '@typescript-eslint/no-explicit-any': 'warn',

    // Desactiver les regles trop strictes pour du CRM interne
    '@typescript-eslint/no-empty-function': 'off',
  },
};
