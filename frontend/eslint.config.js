import vue from 'eslint-plugin-vue'
import tsparser from '@typescript-eslint/parser'
import tsplugin from '@typescript-eslint/eslint-plugin'

const tsRules = {
  ...tsplugin.configs.recommended.rules,
  'no-undef': 'off',
  '@typescript-eslint/no-explicit-any': 'off',
  '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
}

export default [
  {
    ignores: ['dist/**', 'node_modules/**', '.npm-cache/**', '*.config.js'],
  },
  ...vue.configs['flat/recommended'],
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsparser,
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
    },
    plugins: { '@typescript-eslint': tsplugin },
    rules: tsRules,
  },
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tsparser, ecmaVersion: 'latest', sourceType: 'module' },
    },
    plugins: { '@typescript-eslint': tsplugin },
    rules: tsRules,
  },
  {
    files: ['**/*.vue'],
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/html-indent': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/attributes-order': 'off',
      'vue/attribute-hyphenation': 'off',
      'vue/first-attribute-linebreak': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/html-closing-bracket-spacing': 'off',
      'vue/multiline-html-element-content-newline': 'off',
      'vue/no-v-html': 'off',
    },
  },
]
