
import os

from macros import CONTEXT_DIR
from macros import CHECK_DOWNLOADS_DIR
from utils import findCallSiteByCid

def makeCallerPublic(cid):
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
    caller_start_line = None
    for i in range(len(lines)):
        if lines[i].strip().endswith(") {") and caller_short_name in lines[i]:
            caller_start_line = i
            def_code = lines[i]
            break
        elif lines[i].strip().endswith(") throws IOException {") and caller_short_name in lines[i]: 
            caller_start_line = i
            def_code = lines[i]
            break
        elif caller_short_name + " (" in lines[i] and ")" not in lines[i]:
            caller_start_line = i
            def_code = lines[i]
            break
        elif caller_short_name + "(" in lines[i] and ")" not in lines[i]:
            caller_start_line = i
            def_code = lines[i]
            break
    if not caller_start_line:
        print("Cannot find caller start line!")
        exit(0)
    def_code = def_code.replace("private", "public").replace("protected", "public")
    lines = lines[:caller_start_line] + [def_code] + lines[caller_start_line+1:]
    with open(caller_file, 'w') as fw:
        fw.write("".join(lines))
