import js from "@eslint/js";
import stylex from "@stylexjs/eslint-plugin";
import prettier from "eslint-config-prettier";
import astro from "eslint-plugin-astro";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/node_modules/", "**/dist/", "**/.astro/", "**/generated/"] },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  ...astro.configs.recommended,
  jsxA11y.flatConfigs.strict,
  reactHooks.configs.flat.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        projectService: { allowDefaultProject: ["eslint.config.ts", "*.config.ts"] },
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      "@typescript-eslint/consistent-type-imports": ["error", { fixStyle: "inline-type-imports" }],
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/non-nullable-type-assertion-style": "off",
      "no-console": ["error", { allow: ["warn", "error"] }],
    },
  },
  {
    // The design system: StyleX rules keep tokens and styles honest.
    files: ["**/*.{ts,tsx}"],
    plugins: { "@stylexjs": stylex },
    rules: {
      "@stylexjs/valid-styles": "error",
      "@stylexjs/valid-shorthands": "error",
      "@stylexjs/sort-keys": "error",
      "@stylexjs/no-unused": "error",
      "@stylexjs/enforce-extension": "error",
    },
  },
  {
    files: ["**/*.astro"],
    rules: {
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
    },
  },
  {
    files: ["**/*.test.{ts,tsx}", "**/scripts/**"],
    rules: { "no-console": "off" },
  },
  {
    // Config files pull in plugins without type declarations.
    files: ["**/*.config.{ts,js}"],
    rules: {
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
    },
  },
  { files: ["**/*.js"], ...tseslint.configs.disableTypeChecked },
  prettier,
);
