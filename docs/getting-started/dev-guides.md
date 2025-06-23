# Developer's Guide

## Testing markdown linting locally

To test linting errors for markdown files locally, you need to install following npm package.

```bash
npm install -g markdownlint-cli
```

After this you can run the following command to check for markdown linting errors. Make sure you are at the root of the repo.

```bash
markdownlint docs/**/*.md --config .markdownlint.yaml
markdownlint README.md --config .markdownlint.yaml
markdownlint CHANGELOG.md --config .markdownlint.yaml
```

## Testing spell check locally

To test spell check locally  for markdown and python files, you need to install following npm package.

```bash
npm install -g cspell
```

After you install `cspell` you can run following command to test the spell check.

```bash
cspell --config .cspell.json "src/**/*.py" "docs/**/*.md" "README.md" "CHANGELOG.md"
```