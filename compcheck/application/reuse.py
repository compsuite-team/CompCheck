import os
import re
import json

from macros import CONTEXT_DIR
from macros import CHECK_DOWNLOADS_DIR
from macros import SEPERATE_FROM_INNER_CLASS_CALLSITES
from macros import REUSE_CALLER_JSON
from macros import ARG_OBJECT
from macros import KNOWLEDGE_JSON
from utils import findCallSiteByCid

def reuseCaller(cid):
    c = findCallSiteByCid(cid)
    caller = c['caller']
    caller_class_name = caller.split('.')[-2]
    caller_short_name = caller.split('.')[-1].split('(')[0]
    project_dir = f"{CHECK_DOWNLOADS_DIR}/{c['client']}"
    if c['submodule'] != "N/A":
        project_dir += "/" + c['submodule']
    if cid in SEPERATE_FROM_INNER_CLASS_CALLSITES:
        caller_class_name = caller_class_name.split("$")[-1]
    for dir_path, subpaths, files in os.walk(project_dir, False):
        for f in files:
            if f == f"{caller_class_name}.java":
                caller_file = f"{dir_path}/{f}"
    if not os.path.isfile(caller_file):
        print("Cannot find caller java file! Exit")
    with open(caller_file) as fr:
        lines = fr.readlines()
    
    

    search_method_name = caller_short_name
    if caller_short_name == '<init>':
        search_method_name = caller_class_name
    caller_start_line = None
    for i in range(len(lines)):
        if "new " in lines[i]:
            continue
        if cid == "c8-1":
            if lines[i].strip().startswith("public " + search_method_name + "("):
                caller_start_line = i
                break
        elif cid == "c9-3":
            if lines[i].strip().startswith(search_method_name + "(final String messageBody"):
                caller_start_line = i
                break
        elif cid == "c12-9":
            if lines[i].strip().startswith("public " + search_method_name + "(String loggerName"):
                caller_start_line = i
                break
        else:
            if lines[i].strip().endswith(" {") and search_method_name + "(" in lines[i]: 
                caller_start_line = i
                break
            if lines[i].strip().startswith("public ") and search_method_name + "(" in lines[i]:
                caller_start_line = i
                break
    if not caller_start_line:
        print("Cannot find caller start line!")
        exit(0)
    
    reused_lines, desc, args, imports_lines, deps_lines, func_lines = readReuseResultFromReusedCaller(cid)
    reused_caller_lines = []

    if cid == "c3-4":
        lines[caller_start_line] = lines[caller_start_line].replace("private", "public")
        reused_caller_lines.append(replace_brackets(lines[caller_start_line], "String url"))
    elif cid == "c2-2":
        reused_caller_lines.append(replace_brackets(lines[caller_start_line], "ClassLoader loader"))
    elif cid == "c8-1":
        reused_caller_lines.append(replace_brackets(lines[caller_start_line], "Map stormConf"))
    elif cid == "c9-2":
        reused_caller_lines.append("public static void " + replace_brackets(lines[caller_start_line], ""))
    elif cid == "c9-3":
        reused_caller_lines.append("public static void " + replace_brackets(lines[caller_start_line], "final int expectedType"))
    else:
        reused_caller_lines.append(replace_brackets(lines[caller_start_line], ""))
    leading_spaces = count_leading_spaces(lines[caller_start_line])
    for i in range(caller_start_line + 1, len(lines)):
        if "super(bean);" in lines[i]:
            reused_caller_lines.append(lines[i].replace("bean", "new SoyMsgExtractor()"))
        else:
            reused_caller_lines.append(lines[i])
        ls = count_leading_spaces(lines[i])
        if ls != 0 and leading_spaces >= ls:
            if func_lines == "":
                break
            else:
                for l in func_lines:
                    reused_caller_lines.append(l)
                break

    if len(reused_lines) > 0:
        if cid == "c8-2" or cid == "c8-3" or cid == "c8-1":
            reused_caller_lines = reused_caller_lines[:2] + reused_lines + ['\n'] + reused_caller_lines[2:]
        elif cid == "c2-2" or cid == "c6-12" or cid == "c9-2" or cid == "c9-3" or cid == "c15-1" or cid == "c15-2":
            reused_caller_lines = reused_caller_lines[:1] + reused_lines + ['\n'] + reused_caller_lines[2:]
        else:
            reused_caller_lines = reused_caller_lines[:1] + reused_lines + ['\n'] + reused_caller_lines[1:]

    caller_args_part = extract_substring(lines[caller_start_line])
    caller_args_list = caller_args_part.split(", ")
    caller_args_list = [item.strip() for item in caller_args_list]
    caller_alter_args = []
    
    for item in args:
        caller_alter_args.append(item.split("_")[-1])

    if cid == "c2-2" or cid == "c3-4" or cid == "c8-1":
        caller_args_list.pop(0)

    for i in range(1, len(reused_caller_lines)):
        for j in range(len(caller_args_list)):
            need_alt_arg = caller_args_list[j].split(" ")[-1]
            if need_alt_arg in reused_caller_lines[i]:
                reused_caller_lines[i] = replace_substring(reused_caller_lines[i], need_alt_arg, caller_alter_args[j])

    extra_reused = ["c15-1", "c15-2", "c15-3", "c15-4"]
    
    if cid in extra_reused:
        reused_caller_lines = readExtraUseFromReusedCaller(cid)

    extra_reused_file = ["c19-4", "c19-5"]
    if cid in extra_reused_file:
        reused_dir = f"{ARG_OBJECT}/reused/{cid}/reused_caller.java"
        with open(reused_dir, 'r') as frdr:
            reused_caller_lines = frdr.readlines()

    exit(0)

    if lines[caller_start_line - 1].strip().startswith("@"):
        lines = lines[:caller_start_line - 1] + reused_caller_lines + ['\n'] + lines[caller_start_line - 1:]
    else:
        lines = lines[:caller_start_line] + reused_caller_lines + ['\n'] + lines[caller_start_line:]
    
    for i in range(len(lines)):
        if "package " in lines[i]:
            lines = lines[:i+1] + imports_lines + lines[i+1:]
            break
    
    with open(caller_file, 'w') as fw:
        fw.write("".join(lines))
    if len(deps_lines):
        addExtraDeps(cid, deps_lines)
    if len(imports_lines):
        addExtraImports(cid, imports_lines)
    if caller_short_name == "<init>":
        if cid == "c9-2":
            caller_short_name = "Type2Message"
        if cid == "c9-3":
            caller_short_name = "NTLMMessage"
        return f"{caller_class_name}.{caller_short_name}{desc}"
    else:
        return f"{caller_class_name}.{caller_short_name}{desc}"

def replace_brackets(string, new_text):
    start_index = string.find("(")
    end_index = string.find(")")
    if start_index != -1 and end_index != -1:
        return string[:start_index+1] + new_text + string[end_index:]
    else:
        return string


def count_leading_spaces(s):
    return len(s) - len(s.lstrip(' '))


def readReuseResult(cid):
    result_file = f"{CONTEXT_DIR}/{cid}/reused_caller.txt"
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

def readReuseResultFromReusedCaller(cid):
    with open(REUSE_CALLER_JSON, 'r') as frcj:
        reused_context = json.load(frcj) 


    lines = []
    desc = ""
    for rc in reused_context:
        if rc["id"] == cid:
            for key in rc["args"]:    
                for l in rc["args"][key]: 
                    l = " " * 8 + l
                    l = l + "\n"
                    lines.append(l)
            desc = rc["desc"]
            args = rc["args"]
            imports_lines = rc["extra_imports"]
            deps_lines = rc["extra_deps"]
            if "extra_func" in rc:
                func_lines = rc["extra_func"]
            else:
                func_lines = ""
    return lines, desc, args, imports_lines, deps_lines, func_lines

def readExtraUseFromReusedCaller(cid):
    with open(REUSE_CALLER_JSON, 'r') as f:
        reused_context = json.load(f) 
    lines = []
    for rc in reused_context:
        if rc["id"] == cid:
            lines = rc["extra_use"]
    return lines


def addExtraDeps(cid, extra_lines):
    c = findCallSiteByCid(cid)
    poms = [f"{CHECK_DOWNLOADS_DIR}/{c['client']}/pom.xml"]
    if c['submodule'] != "N/A":
        poms.append(f"{CHECK_DOWNLOADS_DIR}/{c['client']}/{c['submodule']}/pom.xml")
    for pom in poms:
        deps_start_line = None
        with open(pom, 'r') as fr:
            lines = fr.readlines()
        for i in range(len(lines)):
            if lines[i].strip().startswith("<dependency>") and lines[i+1].strip().startswith("<groupId>"):
                deps_start_line = i
                break
        if not deps_start_line:
            continue
        lines = lines[:deps_start_line] + extra_lines + lines[deps_start_line:]
        with open(pom, 'w') as fw:
            fw.write("".join(lines))


def addExtraImports(cid, extra_lines):
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
    for i in range(len(lines)):
        if lines[i].strip().startswith("import ") and not lines[i+1].strip().startswith("import "):
            import_end_line = i
            break
    lines = lines[:import_end_line + 1] + extra_lines + ['\n'] + lines[import_end_line + 1:]
    with open(caller_file, 'w') as fw:
        fw.write("".join(lines))

def replace_comma(s):
    parts = re.findall(r'<[^>]*>', s)
    for part in parts:
        new_part = part.replace(", ", ",")
        s = s.replace(part, new_part)
    return s

def extract_substring(s):
    matches = re.findall(r'\((.*?)\)', s)
    if matches:
        return replace_comma(matches[-1])
    else:
        return None

def replace_substring(s, sub, arg):
    indices = [i for i in range(len(s)) if s.startswith(sub, i)]
    for index in indices[::-1]:
        if index == 0 or s[index-1] in [' ', '(', ')', ':', ',', '.']:
            if index + len(sub) == len(s) or s[index + len(sub)] in [' ', '(', ')', ':', ',', '.']:
                s = s[:index] + arg + s[index + len(sub):]
    return s














