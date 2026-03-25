import js from '@eslint/js';
import reactPlugin from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    plugins: {
      react: reactPlugin,
      'react-hooks': reactHooks,
    },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        window: 'readonly',
        document: 'readonly',
        console: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        fetch: 'readonly',
        Promise: 'readonly',
        FormData: 'readonly',
        URLSearchParams: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        navigator: 'readonly',
        location: 'readonly',
        process: 'readonly',
        Blob: 'readonly',
        alert: 'readonly',
        confirm: 'readonly',
        URL: 'readonly',
        File: 'readonly',
        FileReader: 'readonly',
        WebSocket: 'readonly',
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: 'detect' },
    },
    rules: {
      // React
      'react/react-in-jsx-scope': 'off',       // Vite는 자동 import
      'react/jsx-uses-vars': 'error',
      'react/prop-types': 'off',               // PropTypes 강제 안 함
      'react/display-name': 'off',

      // Hooks
      'react-hooks/rules-of-hooks': 'error',   // Hook 규칙 위반 → 에러
      'react-hooks/exhaustive-deps': 'warn',   // deps 누락 → 경고

      // 기본
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'no-console': 'off',
      'no-undef': 'error',
    },
  },
  {
    ignores: ['dist/**', 'node_modules/**', '*.config.js'],
  },
];
