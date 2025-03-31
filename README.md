# search-pr

[![Test](https://github.com/koyuki7w/search-pr/actions/workflows/test.yml/badge.svg)](https://github.com/koyuki7w/search-pr/actions/workflows/test.yml)

## Description

Search for open pull requests that modify lines containing a specific string.

## Install

```
pip install search-pr
```

## Usage

```
$ git-search-pr --help
Usage: git-search-pr [OPTIONS] QUERY

  Search for open pull requests that modify lines containing QUERY.

Options:
  --cache TEXT   Cache directory.  [default: ~/.cache/search-pr]
  --remote TEXT  The git remote.  [default: origin]
  --help         Show this message and exit.
```
