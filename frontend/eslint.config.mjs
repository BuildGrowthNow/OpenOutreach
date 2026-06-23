import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // Custom config - disable warnings for React Hook Form integration
  defineConfig({
    rules: {
      // Disable unused-imports rule
      // 'unused-imports/no-unused-imports': 'warn',
      // Disable unused vars warnings
      '@typescript-eslint/no-unused-vars': 'off',
      // Disable incompatible-library warning for React Hook Form watch()
      // This is a false positive warning when using form.watch() in component body
      'react-hooks/incompatible-library': 'off',
      // Disable purity rule - Date.now() is commonly used and this rule is overly strict
      'react-hooks/purity': 'off',
      // Disable unescaped entities rule - apostrophes in JSX are common
      'react/no-unescaped-entities': 'off',
    },
  }),
]);

export default eslintConfig;
