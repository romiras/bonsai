# 🌳 Bonsai

**Bonsai** uses Tree-sitter to surgically trim comments and skeletonize non-essential logic, fitting massive codebases into small context windows without losing structural integrity.

[](https://opensource.org/licenses/MIT)
[](https://www.python.org/downloads/)

## 🎯 The Problem

Standard source code is "noisy" for LLMs. Indentation, docstrings, and helper functions consume thousands of tokens, often pushing your target logic out of the model's active attention span or exceeding context limits.

## ✨ The Solution: Waterfall Pruning

Bonsai treats code as an **Abstract Syntax Tree (AST)** rather than text. It applies a multi-stage "Waterfall" algorithm to reduce token counts while preserving the code's "mental map."

1.  **TEACH:** Raw code for full context.
2.  **REFACTOR:** Strips comments and docstrings (Logic-only).
3.  **ISOLATE:** Skeletonizes everything except your `target` function/class.
4.  **ARCHITECT:** Converts all bodies to `...` (Signatures-only).

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/romiras/bonsai.git
cd bonsai
uv sync
```

### Basic Usage

Prune a single file to fit a specific token budget:

```bash
python bonsai.py path/to/file.py --mode REFACTOR
```

Isolate a specific function for deep analysis:

```bash
python bonsai.py path/to/file.py --mode ISOLATE --target my_complex_function
```

Generate a compressed prompt for an entire directory:

```bash
python bonsai.py ./src --max-tokens 500 > llm_prompt.txt
```

---

## 🛠 Features

| Feature             | Description                                                           |
| :------------------ | :-------------------------------------------------------------------- |
| **AST-Aware**       | Uses Tree-sitter for 100% syntactically valid pruning.                |
| **Token Budgeting** | Integrated with `tiktoken` to hit exact context targets.              |
| **Skeletonization** | Replaces complex bodies with `...` to preserve interface definitions. |
| **AI-Ready**        | Designed for easy maintenance and extension by AI agents.             |

---

## 📐 Design Philosophy

Bonsai is built on the **Strategy Pattern**. Adding support for new languages or pruning rules is as simple as adding a new Tree-sitter query file (`.scm`).

### Comparison

**Original (200+ tokens)** → **Bonsai ISOLATE (80 tokens)**

```python
# Before                             # After
def helper():                        def helper(): ...
    """Docs..."""
    x = 1 + 1                        def target():
                                         helper()
def target():                            return True
    helper()
    return True
```
