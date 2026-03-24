import argparse
import os
from pathlib import Path
from enum import Enum, auto
from typing import List, Tuple
import tiktoken
from tree_sitter import Language, Parser, Query, Node, QueryCursor
import tree_sitter_python


class PruningMode(Enum):
    TEACH = auto()
    REFACTOR = auto()
    ISOLATE = auto()
    ARCHITECT = auto()


class PythonPruner:
    def __init__(self):
        self.language = Language(tree_sitter_python.language())
        self.parser = Parser(self.language)

    def get_modifications(
        self,
        root: Node,
        source_bytes: bytes,
        mode: PruningMode,
        target_name: str = None,
    ) -> List[Tuple[int, int, bytes]]:
        mods = []
        if mode == PruningMode.TEACH:
            return mods

        strip_query = Query(
            self.language,
            """
            (comment) @comment
            (expression_statement (string)) @docstring
        """,
        )
        for node_list in QueryCursor(strip_query).captures(root).values():
            for node in node_list:
                mods.append((node.start_byte, node.end_byte, b""))

        if mode in (PruningMode.ARCHITECT, PruningMode.ISOLATE):
            struct_query = Query(
                self.language,
                """
                (function_definition) @func
                (class_definition) @class
            """,
            )
            captures = QueryCursor(struct_query).captures(root)

            for node_type in ["func", "class"]:
                for struct_node in captures.get(node_type, []):
                    name_node = struct_node.child_by_field_name("name")
                    body_node = struct_node.child_by_field_name("body")

                    if name_node and body_node:
                        name = source_bytes[
                            name_node.start_byte : name_node.end_byte
                        ].decode("utf-8")
                        if mode == PruningMode.ARCHITECT or (
                            mode == PruningMode.ISOLATE and name != target_name
                        ):
                            mods.append(
                                (body_node.start_byte, body_node.end_byte, b" ...")
                            )

        # Filter modifications: remove any that are contained within another
        sorted_mods = sorted(mods, key=lambda m: (m[0], -(m[1]-m[0])))
        filtered_mods = []
        last_end = -1
        for start, end, repl in sorted_mods:
            if start >= last_end:
                filtered_mods.append((start, end, repl))
                last_end = end
            elif end > last_end:
                # This should not happen with current queries, but for robustness:
                # If they partially overlap, we have a problem. 
                # For now, just skip or handle if needed.
                pass
        
        return sorted(filtered_mods, key=lambda m: m[0], reverse=True)

    def process(
        self, source_code: str, mode: PruningMode, target_name: str = None
    ) -> str:
        source_bytes = bytearray(source_code, "utf-8")
        root = self.parser.parse(source_bytes).root_node

        for start, end, replacement in self.get_modifications(
            root, source_bytes, mode, target_name
        ):
            source_bytes[start:end] = replacement

        cleaned = source_bytes.decode("utf-8")
        return "\n".join(line for line in cleaned.splitlines() if line.strip())


def auto_prune(
    pruner: PythonPruner, source_code: str, max_tokens: int, target: str = None
) -> str:
    """Selects the highest fidelity mode that fits within the token budget."""
    encoding = tiktoken.get_encoding("cl100k_base")

    for mode in [PruningMode.TEACH, PruningMode.REFACTOR]:
        result = pruner.process(source_code, mode=mode)
        if len(encoding.encode(result)) <= max_tokens:
            return result

    if target:
        result = pruner.process(
            source_code, mode=PruningMode.ISOLATE, target_name=target
        )
        if len(encoding.encode(result)) <= max_tokens:
            return result

    return pruner.process(source_code, mode=PruningMode.ARCHITECT)


def process_directory(
    dir_path: str, max_tokens_per_file: int, target: str = None
) -> str:
    """Compiles all Python files in a directory into a single LLM prompt."""
    pruner = PythonPruner()
    combined_prompt = []

    for path in Path(dir_path).rglob("*.py"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()

            pruned_code = auto_prune(pruner, code, max_tokens_per_file, target)
            combined_prompt.append(f"### File: {path}\n```python\n{pruned_code}\n```\n")
        except Exception as e:
            combined_prompt.append(
                f"### File: {path}\n# Error reading or parsing file: {e}\n"
            )

    return "\n".join(combined_prompt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bonsai: Context-aware code pruner.")
    # Now optional, defaults to current directory
    parser.add_argument("path", nargs="?", default=".", help="File or directory to prune")
    
    # Restore manual mode control
    parser.add_argument("--mode", type=str, choices=[m.name for m in PruningMode], 
                        help="Force a specific mode (skips auto-budget logic)")
    
    parser.add_argument("--max-tokens", type=int, default=1000, 
                        help="Max tokens per file for auto-mode (default: 1000)")
    
    parser.add_argument("--target", type=str, 
                        help="Target class/function to preserve")
    
    args = parser.parse_args()
    pruner = PythonPruner()
    
    path = Path(args.path)
    if not path.exists():
        if path.with_suffix('.py').exists():
            path = path.with_suffix('.py')
        else:
            print(f"Error: Path '{args.path}' does not exist.")
            exit(1)
            
    files = [path] if path.is_file() else list(path.rglob("*.py"))
    if not files:
        print(f"Error: No Python files found for path '{path}'.")
        exit(1)

    for p in files:
        try:
            with open(p, "r", encoding="utf-8") as f:
                code = f.read()
            
            # If user explicitly sets a mode, use it. Otherwise, use auto_prune logic.
            if args.mode:
                mode_enum = PruningMode[args.mode]
                result = pruner.process(code, mode=mode_enum, target_name=args.target)
            else:
                result = auto_prune(pruner, code, args.max_tokens, args.target)
                
            print(f"### File: {p}\n```python\n{result}\n```\n")
        except Exception as e:
            print(f"### File: {p}\n# Error: {e}\n")
