import js from '@eslint/js';
import ts from 'typescript-eslint';
import a11y from 'eslint-plugin-jsx-a11y';
export default ts.config(
  { ignores: ['dist/**', 'src/generated/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  { files: ['src/**/*.{ts,tsx}'], plugins: { 'jsx-a11y': a11y }, rules: { ...a11y.configs.recommended.rules, '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }] } },
);
