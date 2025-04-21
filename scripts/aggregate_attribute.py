import os
from glob import glob
import re
from typing import List
import json
import ast

def extract_config_and_levels(lines: List[str], file: str) -> dict:
    """
    Extract config parameters and curriculum attribute levels from a Python script.

    Args:
        lines (List[str]): The script as a list of lines.
        file (str): The file name (used as key in the result).

    Returns:
        dict: {
            "file": {
                "config": {param_name: param_value, ...},
                "levels": {attribute_name: levels_list_as_str}
            }
        }
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    relative_file = os.path.relpath(file, start=project_root)

    result = {relative_file: {"config": {}, "levels": {}}}
    
    #result = {file: {"config": {}, "levels": {}}}
    inside_config = False
    inside_curriculum = False
    indent = ""

    class_config_pattern = re.compile(r"class\s+(\w*Config)\s*(\(.*?\))?\s*:")
    class_curriculum_pattern = re.compile(r"class\s+(\w*Curriculum)\s*(\(.*?\))?\s*:")
    param_pattern = re.compile(r"(\w+)\s*:\s*[^=]+=\s*(.+?)(?:\s+#.*)?$")

    buffered_param = None
    buffer_lines = []

    buffering_attribute = False
    attribute_buffer = []

    for line in lines:
        stripped = line.strip()

        # Detect config class
        if class_config_pattern.match(stripped):
            inside_config = True
            inside_curriculum = False
            indent = line[:len(line) - len(line.lstrip())]
            continue

        # Detect curriculum class
        if class_curriculum_pattern.match(stripped):
            inside_curriculum = True
            inside_config = False
            indent = line[:len(line) - len(line.lstrip())]
            continue

        # Leave class if indent breaks
        if line.startswith("class ") or (line and not line.startswith(indent)):
            inside_config = False
            inside_curriculum = False

        # --- Config parameters ---
        if inside_config:
            if not stripped or stripped.startswith("@") or stripped.startswith("def"):
                continue

            # Continue buffering multi-line parameter value
            if buffered_param:
                buffer_lines.append(stripped)
                if stripped.endswith((")", "]")):
                    full_value = " ".join(buffer_lines)
                    full_value = re.sub(r"#.*", "", full_value).strip()
                    full_value = re.sub(r"^\(+\s*|\s*\)+$", "", full_value).strip()
                    result[relative_file]["config"][buffered_param] = full_value

                    buffered_param = None
                    buffer_lines = []
                continue

            match = param_pattern.match(stripped)
            if match:
                param, value = match.groups()
                if value.endswith(("(", "[")):
                    buffered_param = param
                    buffer_lines = [value]
                else:
                    clean_value = re.sub(r"#.*", "", value).strip()
                    result[relative_file]["config"][param] = clean_value

        # --- Curriculum levels ---
        if inside_curriculum:
            if "AttributeDefinition(" in stripped:
                buffering_attribute = True
                attribute_buffer = [stripped]
                continue

            if buffering_attribute:
                attribute_buffer.append(stripped)
                if stripped.endswith("),") or stripped.endswith(")"):
                    attribute_block = " ".join(attribute_buffer)
                    buffering_attribute = False
                    attribute_buffer = []

                    name_match = re.search(r'name\s*=\s*["\'](\w+)["\']', attribute_block)
                    #levels_match = re.search(r'levels\s*=\s*(\[.*?\])', attribute_block)
                    levels_match = re.search(r'levels\s*=\s*(\[.*?\]|list\(.*?\))', attribute_block)    
                    if name_match and levels_match:
                        attr_name = name_match.group(1)
                        levels = levels_match.group(1)
                        result[relative_file]["levels"][attr_name] = levels

    return result
                    
def extract_level(path_task):
    if path_task.endswith("base_conversion.py"):
        a=0
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
                    try:
                        levels = ast.literal_eval(kw.value)
                    except Exception:
                        levels = None
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
        json.dump(params, fp, sort_keys=True, indent=2)
        
if __name__ == "__main__":
    main()
