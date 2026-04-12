# Design Philosophy

## The Form Hierarchy

Every expression in dftly can be represented in three equivalent forms. Understanding this
hierarchy is key to using dftly effectively and to contributing to the project.

### 1. String Form

Concise, human-readable syntax designed for YAML configs. Parsed by a Lark grammar.

```yaml
sum: $col1 + $col2 * 3
```

### 2. Dict/YAML Form (Base Form)

The fully explicit tree representation. Every node type, argument, and keyword argument is
spelled out. This is the **canonical** representation that all other forms reduce to.

```yaml
sum:
  add:
    - column: col1
    - multiply:
        - column: col2
        - literal: 3
```

### 3. Class Form

Python objects, isomorphic to the dict form. Used for programmatic construction.

```python
from dftly.nodes import Add, Column, Literal, Multiply

Add(Column("col1"), Multiply(Column("col2"), Literal(3)))
```

## The Rule

**All three forms produce the same internal AST and the same Polars expression.**

The string form is syntactic sugar over the dict form. Any expression you can write as a string
can also be written as an equivalent dict/YAML structure. When in doubt about what a string
expression means, look at its dict form -- that is the unambiguous specification.

### For contributors

When adding new features:

1. **Start from the base form.** Define the dict structure first. What node class does it map to?
    What are the required/optional kwargs or positional args?

2. **String form is sugar, not structure.** Grammar rules and `from_lark` methods must produce
    dicts that reduce to the same node objects as the dict form. `from_lark` must return a dict
    keyed by its own node's `KEY` -- never a different node type.

3. **Every string-form feature must have a dict-form equivalent.** If you can't define a clean
    base form, don't add string syntax. Composing existing primitives is always preferable to
    grammar-level magic.

See [AGENTS.md](https://github.com/mmcdermott/dftly/blob/main/AGENTS.md) for the full contributor
design guide.
