import os
from glob import glob
import re
from typing import List
import json
import ast
                    
def extract_level(path_task):
    
    def _parse_levels(node):
        # 1. list / tuple / set
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            try:
                return ast.literal_eval(node)
            except Exception:
                values = []
                for elt in node.elts:
                    try:
                        values.append(ast.literal_eval(elt))
                    except Exception:
                        if isinstance(elt, (ast.BinOp, ast.UnaryOp, ast.Constant)):
                            expr = ast.Expression(elt)
                            values.append(eval(compile(expr, "", "eval"),
                                            {"__builtins__": {}}))
                        else:
                            return None
                return values

        # 2. range(...)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "range"):
            args = [ast.literal_eval(a) for a in node.args]
            return list(range(*args))

        # 3. list(range(...))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "list" and len(node.args) == 1):
            inner = node.args[0]
            if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
                    and inner.func.id == "range"):
                args = [ast.literal_eval(a) for a in inner.args]
                return list(range(*args))

        return None

    curriculum_pattern = re.compile(r"class\s+(\w*Curriculum)\s*(\(.*?\))?\s*:")
    
    with open(path_task, encoding="utf-8") as f:
        lines = f.readlines()

    code = "".join(lines)
    match = curriculum_pattern.search(code)
    if not match:
        return None

    start_line = code[:match.start()].count("\n")
    class_indent = len(lines[start_line]) - len(lines[start_line].lstrip())

    end_line = start_line + 1
    while end_line < len(lines):
        line = lines[end_line]
        if line.strip() == "":
            end_line += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= class_indent:
            break
        end_line += 1

    class_code = "".join(lines[start_line:end_line])
    class_node = ast.parse(class_code).body[0]
    levels_by_attr = {}

    for item in ast.walk(class_node):
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id in ("ScalarAttributeDefinition", "RangeAttributeDefinition"):
            name = None
            levels = None
            for kw in item.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    name = kw.value.value
                
                elif kw.arg == "levels":
                    levels = _parse_levels(kw.value)

            if name and levels is not None:
                levels_by_attr[name] = levels

    return levels_by_attr

    
def extract_config(path_task):
    
    class_config_pattern = re.compile(r"class\s+(\w*Config)\s*(\(.*?\))?\s*:")

    with open(path_task, encoding="utf-8") as f:
        lines = f.readlines()

    code = "".join(lines)
    match = class_config_pattern.search(code)

    if not match:
        return None

    start_line = code[:match.start()].count("\n")
    class_indent = len(lines[start_line]) - len(lines[start_line].lstrip())

    end_line = start_line + 1
    while end_line < len(lines):
        line = lines[end_line]
        if line.strip() == "":
            end_line += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= class_indent:
            break
        end_line += 1

    class_code = "".join(lines[start_line:end_line])
    class_node = ast.parse(class_code).body[0]  
    attributes = {}

    for item in class_node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            name = item.target.id
            type_ = ast.unparse(item.annotation) if hasattr(ast, "unparse") else None
            value = ast.unparse(item.value) if item.value else None
            attributes[name] = {"type": type_, "value": value}
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    value = ast.unparse(item.value) if hasattr(ast, "unparse") else None
                    attributes[name] = {"type": None, "value": value}

    return attributes

def extract_parameters_from_first_script_in(path_tasks):
    """
    Extract parameters from each provided script path.

    Args:
        path_tasks (List[str]): List of Python file paths.

    Returns:
        dict: Aggregated config and level data across all files.
    """
    params = {}
    marker = "reasoning_gym"

    for path_task in path_tasks:
        config = extract_config(path_task)
        levels = extract_level(path_task)
        parts = path_task.split(marker, maxsplit=1)
        path = os.path.join(marker, parts[1].lstrip("\\/"))
        params_file = {path: {"config":config, "levels":levels}}
        params.update(params_file)
    return params


def has_config(script_path):
    """
    Check whether a script defines a Config class.

    Args:
        script_path (str): Path to a Python script.

    Returns:
        bool: True if the script contains a Config class.
    """
    class_pattern = re.compile(r"class\s+(\w*Config)\s*(\(.*?\))?\s*:")
    with open(script_path, encoding='utf-8') as file:
        lines = [line.rstrip() for line in file]
    for line in lines:
        if class_pattern.match(line.strip()):
            return True
    return False

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    task_path = os.path.join(current_dir, "..", "reasoning_gym")
    task_path = os.path.abspath(task_path)  # Important pour nettoyer le chemin
    #task_path = "reasoning_gym"
    script_paths = [
        script for script in glob(os.path.join(task_path, "**", "*.py"), recursive=True)
        if not script.endswith('__init__.py')
    ]
    script_paths = [
        script for script in script_paths
        if has_config(script) and not script.endswith('composite.py')
    ]

    params = extract_parameters_from_first_script_in(script_paths)

    with open('data.json', 'w', encoding='utf-8') as fp:
        #json.dump(params, fp, sort_keys=True, indent=4)
        #json.dump(params, fp, indent=2, separators=(',', ': '), ensure_ascii=False)       
        fp.write(json.dumps(params, indent=2, separators=(',', ': ')).replace('[\n', '[').replace('\n]', ']').replace(',\n', ', ')) 
if __name__ == "__main__":
    main()
