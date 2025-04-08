import os
from glob import glob
import re
from typing import List
import json

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


def extract_parameters_from_first_script_in(path_tasks):
    """
    Extract parameters from each provided script path.

    Args:
        path_tasks (List[str]): List of Python file paths.

    Returns:
        dict: Aggregated config and level data across all files.
    """
    params = {}
    for path_task in path_tasks:
        with open(path_task, encoding='utf-8') as file:
            lines = [line.rstrip() for line in file]
            params_file = extract_config_and_levels(lines, path_task)
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
    with open('data.json', 'w') as fp:
        json.dump(params, fp, indent=4, sort_keys=True)


if __name__ == "__main__":
    main()
