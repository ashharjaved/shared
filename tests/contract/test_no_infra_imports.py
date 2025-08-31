import ast
import pathlib

def test_no_infrastructure_imports_in_api():
    root = pathlib.Path("src")
    for api_py in root.glob("**/api/**/*.py"):
        tree = ast.parse(api_py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and ".infrastructure" in node.module:
                    raise AssertionError(f"Infrastructure import in API file: {api_py} -> from {node.module} import ...")
            if isinstance(node, ast.Import):
                for n in node.names:
                    if "infrastructure" in n.name:
                        raise AssertionError(f"Infrastructure import in API file: {api_py} -> import {n.name}")
