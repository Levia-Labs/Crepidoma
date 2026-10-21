# Configs

- Shared lint, format, type and security configs that pillars extend.

## Contents

<!-- contents:start -->

- [`ast-grep/`](ast-grep/README.md) - Structural lint rules run by ast-grep.
- [`semgrep/`](semgrep/README.md) - Custom semgrep rules run next to the default ruleset.
- [`.editorconfig`](.editorconfig) - Editor whitespace and encoding rules.
- [`.gitattributes`](.gitattributes) - Line endings and binary file rules.
- [`.hadolint.yaml`](.hadolint.yaml) - Dockerfile lint threshold.
- [`.prettierrc`](.prettierrc) - Prettier options.
- [`.yamllint`](.yamllint) - yamllint rules compatible with prettier.
- [`eslint.config.js`](eslint.config.js) - Flat ESLint config: JS and TypeScript recommended plus shared rules.
- [`gitleaks.toml`](gitleaks.toml) - Secret scan config extending the defaults.
- [`pyrightconfig.json`](pyrightconfig.json) - Type checker config for basedpyright or pyright.
- [`ruff.toml`](ruff.toml) - Ruff lint and format config.
- [`sgconfig.yml`](sgconfig.yml) - ast-grep project config.
- [`tsconfig.base.json`](tsconfig.base.json) - Strict TypeScript compiler options.
- [`zizmor.yml`](zizmor.yml) - GitHub Actions audit config.

<!-- contents:end -->
