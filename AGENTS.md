# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Overview

dftly (pronounced "deftly") is a DataFrame Transformation Language parser that provides a YAML-friendly DSL for expressing simple dataframe operations. The library parses YAML configurations into a fully-resolved intermediate representation that can be translated to different execution engines (currently supports Polars).

## Development Commands

### Installation & Setup

```bash
# Development installation with all dependencies
pip install -e ".[dev,tests,polars]"

# Enable pre-commit hooks
pre-commit install
```

### Testing

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=dftly

# Run specific test files
pytest tests/test_parser.py
pytest tests/test_polars_engine.py
pytest tests/test_integration_polars.py

# Run doctests in README
pytest --doctest-glob=README.md
```

### Code Quality

```bash
# Run all pre-commit hooks
pre-commit run --all-files
```

## Architecture

### Core Components

1. **Parser (`src/dftly/parser.py`)**

    - Main entry point via `from_yaml()` function
    - Handles string parsing using Lark grammar
    - Transforms simplified YAML syntax to fully-resolved AST nodes

2. **AST Nodes (`src/dftly/nodes.py`)**

    - `Literal`: Simple values (numbers, strings, booleans)
    - `Column`: References to dataframe columns with optional type info
    - `Expression`: Complex operations with type and arguments

3. **Grammar (`src/dftly/grammar.lark`)**

    - Lark-based parser grammar for string expressions
    - Supports operator precedence, function calls, and complex expressions
    - Handles mathematical, boolean, and string operations

4. **Execution Engine (`src/dftly/polars.py`)**

    - Translates AST nodes to Polars expressions
    - Maps dftly operations to corresponding Polars operations
    - Handles type conversions and complex operations

### Two-Stage Parsing Process

1. **Simplified Form → Fully Resolved Form**

    - YAML/dictionary input is parsed into unambiguous AST nodes
    - String expressions are parsed using the Lark grammar
    - Context-aware parsing based on input schema

2. **Fully Resolved Form → Execution Engine**

    - AST nodes are translated to execution-specific expressions
    - Currently supports Polars via `to_polars()` function
    - Extensible design for additional engines

### Expression Types Supported

The library supports a comprehensive set of operations:

- Arithmetic: `ADD`, `SUBTRACT`
- Boolean: `AND`, `OR`, `NOT`
- Conditional: `CONDITIONAL` (ternary if-else)
- Type operations: `TYPE_CAST`, `COALESCE`
- String operations: `STRING_INTERPOLATE`, `REGEX`
- Temporal: `RESOLVE_TIMESTAMP`, `PARSE_WITH_FORMAT_STRING`
- Membership: `VALUE_IN_LITERAL_SET`, `VALUE_IN_RANGE`
- Utility: `HASH_TO_INT`

### Key Design Principles

1. **Human-Readable Input**: YAML-friendly syntax for non-technical users
2. **Fully-Resolved Intermediate Form**: Unambiguous representation for reliable execution
3. **Engine Independence**: Core parsing separate from execution engines
4. **Limited Scope**: Focuses on row-wise transformations, not table-level operations

## Testing Strategy

- **Unit Tests**: Individual parser components and node types
- **Integration Tests**: End-to-end parsing and execution with Polars
- **Doctest**: Examples in README.md are automatically tested
- **Type Safety**: All code uses type hints and is validated

## Important Files

- `src/dftly/__init__.py`: Public API exports
- `src/dftly/parser.py`: Core parsing logic with `DftlyTransformer` class
- `src/dftly/nodes.py`: AST node definitions with validation
- `src/dftly/grammar.lark`: Lark grammar for string expression parsing
- `src/dftly/polars.py`: Polars execution engine implementation
- `pyproject.toml`: Project configuration with dependencies and build settings
- `.pre-commit-config.yaml`: Code quality automation

## Common Development Patterns

### Adding New Expression Types

1. Add expression name to `_EXPR_TYPES` set in `parser.py`
2. Implement parsing logic in `Parser._parse_mapping()`
3. Add execution logic in `polars.py` `_expr_to_polars()`
4. Add comprehensive tests covering parsing and execution
5. Update documentation and examples

### Extending Grammar

1. Modify `grammar.lark` with new syntax rules
2. Update `DftlyTransformer` class in `parser.py`
3. Add corresponding expression type handling
4. Test string parsing alongside dictionary forms

### Adding New Execution Engines

1. Create new module (e.g., `src/dftly/pandas.py`)
2. Implement `to_[engine]()` function similar to `to_polars()`
3. Map each expression type to engine-specific operations
4. Add comprehensive integration tests
