
import os

from macros import CONTEXT_DIR
from macros import CHECK_DOWNLOADS_DIR
from utils import findCallSiteByCid

def sliceCaller(cid):
    c = findCallSiteByCid(cid)
    caller = c['caller']
    caller_class_name = caller.split('.')[-2]
    caller_short_name = caller.split('.')[-1].split('(')[0]
    if caller_short_name == '<init>':
        caller_short_name = caller_class_name
    project_dir = f"{CHECK_DOWNLOADS_DIR}/{c['client']}"
    if c['submodule'] != "N/A":
        project_dir += "/" + c['submodule']
    for dir_path, subpaths, files in os.walk(project_dir, False):
        for f in files:
            if f == f"{caller_class_name}.java":
                caller_file = f"{dir_path}/{f}"
    if not os.path.isfile(caller_file):
        print("Cannot find caller java file! Exit")
    with open(caller_file) as fr:
        lines = fr.readlines()
    sliced_caller_lines, desc = readSliceResult(cid)
    caller_start_line = None
    for i in range(len(lines)):
        if lines[i].strip().endswith(") {") and caller_short_name in lines[i]: 
            caller_start_line = i
            break
        elif caller_short_name + " (" in lines[i] and ")" not in lines[i]:
            caller_start_line = i
            break
        elif lines[i].strip().startswith("public ") and caller_short_name + "(" in lines[i]:
            caller_start_line = i
            break
    if not caller_start_line:
        print("Cannot find caller start line!")
        exit(0)
    if lines[caller_start_line - 1].strip().startswith("@"):
        lines = lines[:caller_start_line - 1] + sliced_caller_lines + ['\n'] + lines[caller_start_line - 1:]
    else:
        lines = lines[:caller_start_line] + sliced_caller_lines + ['\n'] + lines[caller_start_line:]
    with open(caller_file, 'w') as fw:
        fw.write("".join(lines))
    if os.path.isfile(f"{CONTEXT_DIR}/{cid}/extra_imports.txt"):
        addExtraImports(cid)
    if caller_short_name == "<init>":
        return f"{caller_class_name}.{caller_short_name}{desc}"
    else:
        return f"{caller_class_name}.{caller_short_name}_SLICE{desc}"


def readSliceResult(cid):
    result_file = f"{CONTEXT_DIR}/{cid}/sliced_caller.txt"
    with open(result_file, 'r') as fr:
        lines = fr.readlines()
    desc = None
    for i in range(len(lines)):
        if lines[i].strip().startswith("// desc = "):
            desc = lines[i].strip().split(" = ")[-1]
            break
    if not desc:
        print("Txt file has no desc!")
        exit(0)
    return lines, desc


def addExtraImports(cid):
    c = findCallSiteByCid(cid)
    caller = c['caller']
    caller_class_name = caller.split('.')[-2]
    caller_short_name = caller.split('.')[-1].split('(')[0]
    if caller_short_name == '<init>':
        caller_short_name = caller_class_name
    project_dir = f"{CHECK_DOWNLOADS_DIR}/{c['client']}"
    if c['submodule'] != "N/A":
        project_dir += "/" + c['submodule']
    for dir_path, subpaths, files in os.walk(project_dir, False):
        for f in files:
            if f == f"{caller_class_name}.java":
                caller_file = f"{dir_path}/{f}"
    if not os.path.isfile(caller_file):
        print("Cannot find caller java file! Exit")
    with open(caller_file) as fr:
        lines = fr.readlines()
    with open(f"{CONTEXT_DIR}/{cid}/extra_imports.txt") as fr:
        extra_lines = fr.readlines()
    for i in range(len(lines)):
        if lines[i].strip().startswith("import ") and not lines[i+1].strip().startswith("import "):
            import_end_line = i
            break
    lines = lines[:import_end_line + 1] + extra_lines + ['\n'] + lines[import_end_line + 1:]
    with open(caller_file, 'w') as fw:
        fw.write("".join(lines))
