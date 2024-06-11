import os
import json
import re
import collections
import shutil
import uuid
import subprocess as sub
import xml.etree.ElementTree as ET

from macros import KNOWLEDGE_DOWNLOADS_DIR
from macros import TEST_LOGS_DIR
from macros import AGENT_LOGS_DIR
from macros import TRACES_DIR
from macros import XMLS_DIR
from macros import KNOWLEDGE_CLIENTS_JSON_FILE
from macros import TRACEAGENT_JAR
from macros import TRACE_BOUND
from macros import KNOWLEDGE_JSON

def runKnowledgeDiscovery():
    pass


def runKnowledgeDiscoveryOnOneTest(id):
    print('===> Discovering Knowledge --- id', id)
    with open(KNOWLEDGE_CLIENTS_JSON_FILE, 'r') as fr:
        clients_info = json.load(fr)
    for ci in clients_info:
        if ci['id'] == id:
            client, sha, url, lib, old, new, client_prefix, lib_prefix, test, submodule, test_cmd, co_evolve_libs = \
            ci['client'], ci['sha'], ci['url'], ci['lib'], ci['old'], ci['new'], ci['client_prefix'], \
            ci['lib_prefix'], ci['test'], ci['submodule'], ci['test_cmd'], ci['co_evolve_libs']
            break
    print(f"{client},{sha},{url},{lib},{old},{new},{client_prefix},{lib_prefix},{test},{submodule},{co_evolve_libs}")
    if not os.path.exists(KNOWLEDGE_DOWNLOADS_DIR):
        os.makedirs(KNOWLEDGE_DOWNLOADS_DIR)
    client_dir = KNOWLEDGE_DOWNLOADS_DIR + '/' + client
    if not os.path.isdir(client_dir):
        cwd = os.getcwd()
        os.chdir(KNOWLEDGE_DOWNLOADS_DIR)
        sub.run('git clone ' + url, shell=True)
        os.chdir(KNOWLEDGE_DOWNLOADS_DIR + '/' + client)
        sub.run('git checkout ' + sha, shell=True)
        os.chdir(cwd)
    cwd = os.getcwd()
    os.chdir(KNOWLEDGE_DOWNLOADS_DIR + '/' + client)
    sub.run('git checkout .', shell=True)
    sub.run('mvn install -DskipTests -fn -Denforcer.skip -Dgpg.skip -Drat.skip -Dcheckstyle.skip -Danimal.sniffer.skip', shell=True, stdout=open(os.devnull, 'w'), stderr=sub.STDOUT)
    if submodule != "N/A":
        os.chdir(f"{KNOWLEDGE_DOWNLOADS_DIR}/{client}/{submodule}")
    sub.run(f"mvn test -fn -Drat.ignoreErrors=true -DtrimStackTrace=false -Dtest={test}", shell=True, stdout=open(os.devnull, 'w'), stderr=sub.STDOUT)
    changeLibVersion(client, lib, new)
    removeSurefireArgs(client, submodule)
    if not os.path.isdir(TEST_LOGS_DIR + '/' + id):
        os.makedirs(TEST_LOGS_DIR + '/' + id)
    test_log_file = TEST_LOGS_DIR + '/' + id + '/test.log'
    if not os.path.isdir(AGENT_LOGS_DIR + '/' + id):
        os.makedirs(AGENT_LOGS_DIR + '/' + id)
    agent_log_file = AGENT_LOGS_DIR + '/' + id + '/agent.log'
    if not os.path.isdir(TRACES_DIR + '/' + id):
        os.makedirs(TRACES_DIR + '/' + id)
    trace_file = TRACES_DIR + '/' + id + '/trace'
    xmls_dir = XMLS_DIR + '/' + id
    if os.path.isdir(xmls_dir):
        shutil.rmtree(xmls_dir)
    os.makedirs(xmls_dir)
    if submodule != "N/A":
        os.chdir(f"{KNOWLEDGE_DOWNLOADS_DIR}/{client}/{submodule}")
    if test_cmd == "N/A":
        test_cmd = f"mvn test -fn -Drat.ignoreErrors=true -DtrimStackTrace=false -Dtest={test}"
    sub.run(test_cmd, shell=True, stdout=open(test_log_file, 'w'), stderr=sub.STDOUT)
    print(test_cmd)
    agent_cmd = test_cmd + f" -DargLine=\"-javaagent:{TRACEAGENT_JAR}" + \
                f"=out={trace_file},xmls_path={xmls_dir},bound={TRACE_BOUND},tracing=method#argvalue#return," + \
                f"client_prefix={client_prefix},lib_prefix={lib_prefix}\""
    print(agent_cmd)
    if submodule != "N/A":
        os.chdir(f"{KNOWLEDGE_DOWNLOADS_DIR}/{client}/{submodule}")
    sub.run(agent_cmd, shell=True, stdout=open(agent_log_file, 'w'), stderr=sub.STDOUT)
    os.chdir(cwd)
    api, index = findTargetAPI(id)
    convertTrace(id, api, index)

def changeLibVersion(client: str, lib: str, lib_version: str,
                     downloads_dir=KNOWLEDGE_DOWNLOADS_DIR):
    client_dir = downloads_dir + '/' + client
    for dir_path, subpaths, files in os.walk(client_dir):
        for f in files:
            if f == 'pom.xml':
                pom_file = dir_path + '/' + f
                changeLibVersionOfOnePomFile(lib, lib_version, pom_file)


def changeLibVersionOfOnePomFile(lib: str, lib_version: str, pom_file: str):
    group_id = lib.split(':')[0]
    artifact_id = lib.split(':')[1]
    fr = open(pom_file, 'r')
    lines = fr.readlines()
    fr.close()
    for i in range(len(lines)):
        if '<groupId>' + group_id + '</groupId>' in lines[i]:
            if '<artifactId>' + artifact_id + '</artifactId>' in lines[i + 1]:
                lines[i + 2] = re.sub('\<version\>.*\<\/version\>',
                                      '<version>' + lib_version + '</version>',
                                      lines[i + 2])
    fw = open(pom_file, 'w')
    fw.write(''.join(lines))
    fw.close()


def removeSurefireArgs(client, submodule, downloads_dir=KNOWLEDGE_DOWNLOADS_DIR):
    root_dir = f"{downloads_dir}/{client}"
    for dir_path, subpaths, files in os.walk(root_dir):
        for f in files:
            if f == 'pom.xml':
                pom_file = dir_path + '/' + f
                removeSurefireArgsOfOnePomFile(pom_file)


def removeSurefireArgsOfOnePomFile(pom_file):
    keep_first = False
    with open(pom_file, 'r') as fr:
        first_line = fr.readlines()[0]
        if '<?xml version=' in first_line:
            keep_first = True
    tree = ET.parse(pom_file)
    root = tree.getroot()
    for elem in root.iter():
        if str(elem.tag).split('}')[-1] == "plugin":
            surefire = False
            for child in elem:
                if child.tag.split('}')[-1] == 'artifactId' and child.text == "maven-surefire-plugin":
                    surefire = True
                    break
            if not surefire:
                continue
            for child in elem:
                if child.tag.split('}')[-1] == 'configuration':
                    for grandchild in child:
                        if grandchild.tag.split('}')[-1] == 'argLine':
                            child.remove(grandchild)
                        if grandchild.tag.split('}')[-1] == 'forkCount' and grandchild.text == "0":
                            child.remove(grandchild)
    tree.write(pom_file)
    with open(pom_file, 'r') as fr:
        lines = fr.readlines()
    for i in range(len(lines)):
        lines[i] = lines[i].replace("<ns0:", "<").replace("</ns0:", "</").replace("xmlns:ns0=", "xmlns=")
    if keep_first:
        lines = [first_line] + lines
    with open(pom_file, 'w') as fw:
        fw.write(''.join(lines))

def findTargetAPI(id):
    print('===> Finding Target API --- id', id)
    with open(KNOWLEDGE_CLIENTS_JSON_FILE, 'r') as fr:
        clients_info = json.load(fr)
    for ci in clients_info:
        if ci['id'] == id:
            client, sha, url, lib, old, new, client_prefix, lib_prefix, test = \
                ci['client'], ci['sha'], ci['url'], ci['lib'], ci['old'], ci['new'], ci['client_prefix'], ci['lib_prefix'], ci['test']
            break
    test_log_file = f"{TEST_LOGS_DIR}/{id}/test.log"
    with open(test_log_file, 'r') as fr:
        lines = fr.readlines()
    for i in range(len(lines)):
        if "<<< FAILURE!" in lines[i].strip():
            exception_line = lines[i+2]
            break
    exception_fqn = exception_line.strip().split(":")[0]
    if "Assertion" in exception_fqn or "org.junit.ComparisonFailure" in exception_fqn:
        api, index = findAssertationTargetAPI(id)
    else:
        api, index = findExceptionTargetAPI(id)
    print(f"=== Target API: {api}, index: {index}")
    return api, index

def findExceptionTargetAPI(id):
    with open(KNOWLEDGE_CLIENTS_JSON_FILE, 'r') as fr:
        clients_info = json.load(fr)
    for ci in clients_info:
        if ci['id'] == id:
            client, sha, url, lib, old, new, client_prefix, lib_prefix, test = \
                ci['client'], ci['sha'], ci['url'], ci['lib'], ci['old'], ci['new'], ci['client_prefix'], ci['lib_prefix'], ci['test']
            break
    trace_file = f"{TRACES_DIR}/{id}/trace"
    test_log_file = f"{TEST_LOGS_DIR}/{id}/test.log"
    error_api_fqn = None
    with open(test_log_file, 'r') as fr:
        lines = fr.readlines()
    root_cause_error = ""
    for i in range(len(lines)):
        if lines[i].startswith("Caused by: "):
            root_cause_error = lines[i].split()[2].replace(":", "")
            print("root cause error: ", root_cause_error)
            if root_cause_error == "java.lang.ClassNotFoundException":
                continue
            if root_cause_error == "java.lang.AssertionError":
                return findAssertationTargetAPI(id)
            lines = lines[i:]
            break
    for i in range(len(lines)):
        if lines[i].strip().startswith("at ") and lines[i].strip().endswith(")"):
            method_fqn = lines[i].strip().split("at ")[-1].split("(")[0]
            if method_fqn.startswith(client_prefix):
                prev_method_fqn = lines[i - 1].strip().split("at ")[-1].split("(")[0]
                if prev_method_fqn.startswith(lib_prefix):
                    error_api_fqn = prev_method_fqn
                    print(f"boundary api: {error_api_fqn}")
                    if root_cause_error != "java.lang.NoSuchMethodError":
                        break
    with open(trace_file, 'r') as fr:
        trace_lines = fr.readlines()
    if error_api_fqn:
        for i in reversed(range(len(trace_lines))):
            if trace_lines[i].split()[1].replace("/", ".") == error_api_fqn:
                api = trace_lines[i].split()[1].replace("/", ".") + trace_lines[i].split()[2]
                break
    else:
        for i in reversed(range(len(trace_lines))):
            if trace_lines[i].split()[1].replace("/", ".").startswith(lib_prefix) and trace_lines[i].strip().split()[-1] == "null":
                api = trace_lines[i].split()[1].replace("/", ".") + trace_lines[i].split()[2]
                break
    return api, i

def findAssertationTargetAPI(id):
    with open(KNOWLEDGE_CLIENTS_JSON_FILE, 'r') as fr:
        clients_info = json.load(fr)
    for ci in clients_info:
        if ci['id'] == id:
            client, sha, url, lib, old, new, client_prefix, lib_prefix, test, submodule, test_cmd = \
                ci['client'], ci['sha'], ci['url'], ci['lib'], ci['old'], ci['new'], ci['client_prefix'], \
                ci['lib_prefix'], ci['test'], ci['submodule'], ci['test_cmd']
            break
    test_log_file = f"{TEST_LOGS_DIR}/{id}/test.log"
    with open(test_log_file, 'r') as fr:
        lines = fr.readlines()
    for i in range(len(lines)):
        if lines[i].startswith("Caused by: "):
            root_cause_error = lines[i].split()[2].replace(":", "")
            print("root cause error: ", root_cause_error)
            if "AssertionError" not in root_cause_error and "AssertionException" not in root_cause_error:
                return findExceptionTargetAPI(id)
    for i in range(len(lines)):
        if "<<< FAILURE!" in lines[i].strip():
            exception_line_no = i+2
            break
    for i in range(exception_line_no, len(lines)):
        if lines[i].strip().startswith("at ") and lines[i].strip().endswith(")"):
            method_fqn = lines[i].split("at ")[-1].split("(")[0]
            if method_fqn.startswith(client_prefix):
                last_called_client_method = method_fqn
                break
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        new_trace_lines = fr.readlines()
    lib_pts = set()
    for i in reversed(range(len(new_trace_lines))):
        if new_trace_lines[i].split()[1].replace('/', '.') == last_called_client_method:
            last_call_client_method_index = i
            desc = new_trace_lines[i].split()[2].split("(")[-1].split(")")[0]
            param_types = extractParamTypesFromDesc(desc)
            for pt in param_types:
                if pt.startswith(lib_prefix):
                    lib_pts.add(pt.split("@")[0])
            break
    if lib_pts:
        for i in reversed(range(last_call_client_method_index + 1)):
            if new_trace_lines[i].split()[1].split('.')[0].replace('/', '.') in lib_pts:
                api = new_trace_lines[i].split()[1].replace('/', '.') + new_trace_lines[i].split()[2]
                return api, i
    print("Need compare old & new traces")
    cwd = os.getcwd()
    os.chdir(f"{KNOWLEDGE_DOWNLOADS_DIR}/{client}")
    sub.run('git checkout .', shell=True)
    removeSurefireArgs(client, submodule)
    if test_cmd != "N/A":
        agent_cmd = test_cmd + f" -DargLine=\"-javaagent:{TRACEAGENT_JAR}" + \
          f"=out={TRACES_DIR}/{id}/old.trace,xmls_path={XMLS_DIR}/{id},bound={TRACE_BOUND},tracing=method#argvalue#return," + \
          f"client_prefix={client_prefix},lib_prefix={lib_prefix}\""
    else:
        agent_cmd = f"mvn test -Dtest={test} -fn -Drat.ignoreErrors=true -DtrimStackTrace=false -DargLine=\"-javaagent:{TRACEAGENT_JAR}" + \
          f"=out={TRACES_DIR}/{id}/old.trace,xmls_path={XMLS_DIR}/{id},bound={TRACE_BOUND},tracing=method#argvalue#return," + \
          f"client_prefix={client_prefix},lib_prefix={lib_prefix}\""
    print(agent_cmd)
    if submodule != "N/A":
        os.chdir(f"{KNOWLEDGE_DOWNLOADS_DIR}/{client}/{submodule}")
    sub.run(agent_cmd, shell=True, stdout=open(f"{AGENT_LOGS_DIR}/{id}/old.agent.log", 'w'), stderr=sub.STDOUT)
    os.chdir(cwd)
    if not os.path.isfile(f"{TRACES_DIR}/{id}/old.trace"):
        return "UNKNOWN", -1
    api, index = findLibraryCallSameInputDiffOutput(id, last_called_client_method, lib_prefix)
    if (api, index) == ("UNKNOWN", -1):
        print("try stage 2")
        api, index = findLibraryCallDiffOutput(id, last_called_client_method, lib_prefix)
    if (api, index) == ("UNKNOWN", -1):
        print("try stage 3")
        api, index = findLibraryCallInNewTraceButNotInOldTrace(id, last_called_client_method, lib_prefix)
    if (api, index) == ("UNKNOWN", -1):
        print("try stage 5")
        api, index = findLastLibraryCallDiffOutWithoutCallerInfo(id, lib_prefix)
    if (api, index) == ("UNKNOWN", -1):
        print("try stage 6")
        api, index = findLibraryCallReturnNull(id, last_called_client_method, lib_prefix)
    return api, index


def findLibraryCallSameInputDiffOutput(id, last_called_client_method, lib_prefix):
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        new_trace_lines = fr.readlines()
    with open(f"{TRACES_DIR}/{id}/old.trace", 'r') as fr:
        old_trace_lines = fr.readlines()
    for j in range(len(new_trace_lines)):
        method_fqn = new_trace_lines[j].split()[1].replace("/", ".") + f"{new_trace_lines[j].split()[2].split(')')[0]})"
        caller_fqn = new_trace_lines[j].split()[6].replace("/", ".")
        if isMethodFQNInLib(method_fqn, lib_prefix) and caller_fqn == last_called_client_method:
            new_arg_values = new_trace_lines[j].strip().split()[-3].replace("[", "").replace("]", "").split(",")
            new_ret = new_trace_lines[j].strip().split()[-1]
            for k in range(len(old_trace_lines)):
                if method_fqn == old_trace_lines[k].split()[1].replace("/",
                                                                       ".") + f"{old_trace_lines[k].split()[2].split(')')[0]})" and \
                        caller_fqn == old_trace_lines[k].split()[6].replace("/", "."):
                    old_arg_values = old_trace_lines[k].strip().split()[-3].replace("[", "").replace("]", "").split(",")
                    old_ret = old_trace_lines[k].strip().split()[-1]
                    if arg_values_equal(id, old_arg_values, new_arg_values):
                        if not value_equal(id, old_ret, new_ret):
                            return method_fqn + old_trace_lines[k].split()[2].split(')')[-1], j
    return "UNKNOWN", -1

def findLibraryCallDiffOutput(id, last_called_client_method, lib_prefix):
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        new_trace_lines = fr.readlines()
    with open(f"{TRACES_DIR}/{id}/old.trace", 'r') as fr:
        old_trace_lines = fr.readlines()
    for j in range(len(new_trace_lines)):
        method_fqn = new_trace_lines[j].split()[1].replace("/", ".") + f"{new_trace_lines[j].split()[2].split(')')[0]})"
        caller_fqn = new_trace_lines[j].split()[6].replace("/", ".")
        if isMethodFQNInLib(method_fqn, lib_prefix) and caller_fqn == last_called_client_method:
            new_arg_values = new_trace_lines[j].strip().split()[-3].replace("[", "").replace("]", "").split(",")
            new_ret = new_trace_lines[j].strip().split()[-1]
            for k in range(len(old_trace_lines)):
                if method_fqn == old_trace_lines[k].split()[1].replace("/",
                                                                       ".") + f"{old_trace_lines[k].split()[2].split(')')[0]})" and \
                        caller_fqn == old_trace_lines[k].split()[6].replace("/", "."):
                    old_arg_values = old_trace_lines[k].strip().split()[-3].replace("[", "").replace("]", "").split(",")
                    old_ret = old_trace_lines[k].strip().split()[-1]
                    if not value_equal(id, old_ret, new_ret):
                        return method_fqn + old_trace_lines[k].split()[2].split(')')[-1], j
    return "UNKNOWN", -1

def findLibraryCallInNewTraceButNotInOldTrace(id, last_called_client_method, lib_prefix):
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        new_trace_lines = fr.readlines()
    with open(f"{TRACES_DIR}/{id}/old.trace", 'r') as fr:
        old_trace_lines = fr.readlines()
    api, index = "UNKNOWN", -1
    for j in range(len(new_trace_lines)):
        method_fqn = new_trace_lines[j].split()[1].replace("/", ".") + f"{new_trace_lines[j].split()[2].split(')')[0]})"
        caller_fqn = new_trace_lines[j].split()[6].replace("/", ".")
        if isMethodFQNInLib(method_fqn, lib_prefix) and caller_fqn == last_called_client_method:
            print(f"<NEW> {method_fqn}")
            exist_in_old = False
            for k in range(len(old_trace_lines)):
                if method_fqn == old_trace_lines[k].split()[1].replace("/", ".") + f"{old_trace_lines[k].split()[2].split(')')[0]})" and \
                        caller_fqn == old_trace_lines[k].split()[6].replace("/", "."):
                    exist_in_old = True
                    break
            if not exist_in_old:
                api, index = method_fqn + new_trace_lines[j].split()[2].split(')')[-1], j
    return api, index


def findLastLibraryCallSameInDiffOutWithoutCallerInfo(id, lib_prefix):
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        new_trace_lines = fr.readlines()
    with open(f"{TRACES_DIR}/{id}/old.trace", 'r') as fr:
        old_trace_lines = fr.readlines()
    for j in range(len(new_trace_lines)):
        method_fqn = new_trace_lines[j].split()[1].replace("/", ".") + f"{new_trace_lines[j].split()[2].split(')')[0]})"
        caller_fqn = new_trace_lines[j].split()[6].replace("/", ".")
        if isMethodFQNInLib(method_fqn, lib_prefix):
            new_arg_values = new_trace_lines[j].strip().split()[-3].replace("[", "").replace("]", "").split(",")
            new_ret = new_trace_lines[j].strip().split()[-1]
            for k in range(len(old_trace_lines)):
                if method_fqn == old_trace_lines[k].split()[1].replace("/", ".") + f"{old_trace_lines[k].split()[2].split(')')[0]})" and \
                        caller_fqn == old_trace_lines[k].split()[6].replace("/", "."):
                    old_arg_values = old_trace_lines[k].strip().split()[-3].replace("[", "").replace("]", "").split(",")
                    old_ret = old_trace_lines[k].strip().split()[-1]
                    if arg_values_equal(id, old_arg_values, new_arg_values):
                        if not value_equal(id, old_ret, new_ret):
                            return method_fqn + old_trace_lines[k].split()[2].split(')')[-1], j
    return "UNKNOWN", -1


def findLastLibraryCallDiffOutWithoutCallerInfo(id, lib_prefix):
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        new_trace_lines = fr.readlines()
    with open(f"{TRACES_DIR}/{id}/old.trace", 'r') as fr:
        old_trace_lines = fr.readlines()
    api, index = "UNKNOWN", -1
    for j in range(len(new_trace_lines)):
        method_fqn = new_trace_lines[j].split()[1].replace("/", ".") + f"{new_trace_lines[j].split()[2].split(')')[0]})"
        caller_fqn = new_trace_lines[j].split()[6].replace("/", ".")
        if isMethodFQNInLib(method_fqn, lib_prefix):
            new_arg_values = new_trace_lines[j].strip().split()[-3].replace("[", "").replace("]", "").split(",")
            new_ret = new_trace_lines[j].strip().split()[-1]
            for k in range(len(old_trace_lines)):
                if method_fqn == old_trace_lines[k].split()[1].replace("/", ".") + f"{old_trace_lines[k].split()[2].split(')')[0]})" and \
                        caller_fqn == old_trace_lines[k].split()[6].replace("/", "."):
                    old_arg_values = old_trace_lines[k].strip().split()[-3].replace("[", "").replace("]", "").split(",")
                    old_ret = old_trace_lines[k].strip().split()[-1]
                    if not value_equal(id, old_ret, new_ret):
                        api, index = method_fqn + old_trace_lines[k].split()[2].split(')')[-1], j
    return api, index


def findLibraryCallReturnNull(id, last_called_client_method, lib_prefix):
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        trace_lines = fr.readlines()
    api, index = "UNKNOWN", -1
    for i in range(len(trace_lines)):
        caller_fqn = trace_lines[i].split()[6].replace("/", ".")
        if trace_lines[i].split()[1].replace("/", ".").startswith(lib_prefix) and trace_lines[i].strip().split()[-1] == "null":
            if caller_fqn == last_called_client_method:
                api = trace_lines[i].split()[1].replace("/", ".") + trace_lines[i].split()[2]
                index = i
                break
    return api, index


def isMethodFQNInLib(method_fqn, lib_prefix):
    all_prefixes = set()
    for p in lib_prefix.split("#"):
        if p:
            all_prefixes.add(p)
    for p in all_prefixes:
        if method_fqn.startswith(p):
            return True
    return False

def arg_values_equal(id, old_arg_values, new_arg_values):
    if len(old_arg_values) != len(new_arg_values):
        return False
    for i in range(len(old_arg_values)):
        if not value_equal(id, old_arg_values[i], new_arg_values[i]):
            return False
    return True


def value_equal(id, old_value, new_value):
    if old_value == new_value:
        return True
    if old_value.endswith(".xml") and new_value.endswith(".xml"):
        with open(f"{XMLS_DIR}/{id}/{old_value}") as fr:
            old_xml_content = [l for l in fr.readlines() if l.startswith("<") or l.startswith("  <") or
                               l.startswith("    <")]
        with open(f"{XMLS_DIR}/{id}/{new_value}") as fr:
            new_xml_content = [l for l in fr.readlines() if l.startswith("<") or l.startswith("  <") or
                               l.startswith("    <")]
        if old_xml_content == new_xml_content:
            return True
        return False
    else:
        return False


def convertTrace(id, api, api_index):
    print('===> Converting Trace --- id', id)
    with open(KNOWLEDGE_CLIENTS_JSON_FILE, 'r') as fr:
        clients_info = json.load(fr)
    for ci in clients_info:
        if ci['id'] == id:
            client, sha, url, lib, old, new, client_prefix, lib_prefix, test, submodule, co_evolve_libs = \
                ci['client'], ci['sha'], ci['url'], ci['lib'], ci['old'], ci['new'], ci['client_prefix'], ci[
                    'lib_prefix'], ci['test'], ci['submodule'], ci['co_evolve_libs']
            break
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        trace_lines = fr.readlines()
    target_api_trace_line = trace_lines[api_index]
    method_type = trace_lines[api_index].split()[4]
    target_file = f"{TRACES_DIR}/{id}/knowledge.json"
    knowledge = collections.OrderedDict({})
    knowledge["id"] = id
    knowledge["API"] = api
    knowledge["type"] = method_type
    knowledge["versions"] = [old]
    knowledge["new_version"] = new
    knowledge["lib"] = lib
    knowledge["co_evolve_libs"] = co_evolve_libs
    knowledge["client"] = client
    knowledge["test"] = test
    param_types = extractParamTypes(api, method_type)
    knowledge["args_actual_types"], arg_values = findActualArgTypesFromTraceLine(target_api_trace_line, id, param_types)
    print("parameter types:", param_types)
    print("actual types:", knowledge["args_actual_types"])
    print("arg values:", arg_values)
    knowledge["args_context"] = extractArgsConext(id, api, param_types, knowledge["args_actual_types"], arg_values, api_index)
    knowledge["states"] = extractStates(id, param_types, knowledge["args_actual_types"], arg_values, api_index, knowledge["args_context"])
    postProcessCalleeTypes(knowledge)
    with open(target_file, 'w') as fw:
        json.dump(knowledge, fw, indent=2)

def extractParamTypes(api, method_type):
    desc = api.split("(")[-1].split(")")[0]
    param_types = extractParamTypesFromDesc(desc)
    if method_type not in ["static", "special"]:
        for i in range(len(param_types)):
            pt = param_types[i]
            param_types[i] = f"{pt.split('@')[0]}@{int(pt.split('@')[-1])+1}"
        param_types.insert(0, ".".join(api.split("(")[0].split(".")[:-1]) + "@0")  # this
    return param_types


def extractArgsConext(id, api, param_types, args_actual_types, arg_values, api_index):
    args_context = {}
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        trace_lines = fr.readlines()
    for pt in param_types:
        args_context[pt] = []
    for pt, at, av in zip(param_types, args_actual_types, arg_values):
        if at.endswith("[]"): 
            array_num_of_elems = countElemsInArray(id, av)
            if array_num_of_elems == 1:
                at = at[:-2]
        for i in reversed(range(0, api_index + 1)):
            method_fqn = trace_lines[i].split()[1].replace("/", ".") + trace_lines[i].split()[2]
            if method_fqn == api:
                continue
            class_fqn = ".".join(method_fqn.split("(")[0].split(".")[:-1])
            if class_fqn == at:
                args_context[pt].insert(0, method_fqn)
                if '.<init>(' in method_fqn or '.createFrom(' in method_fqn:
                    break
        args_context[pt].append("ACCEPT")
    return args_context


def extractStates(id, param_types, args_actual_types, arg_values, api_index, args_context):
    states = {}
    trace_file = f"{TRACES_DIR}/{id}/trace"
    with open(trace_file, 'r') as fr:
        trace_lines = fr.readlines()
    for pt in param_types:
        states[pt] = []
    for pt, at, av in zip(param_types, args_actual_types, arg_values):
        if at == "int":
            states[pt] = av
            continue
        elif at == "string":
            states[pt] = av
            continue
        for i in reversed(range(0, api_index + 1)):
            trace_line_param_types = extractParamTypes(trace_lines[i].strip().split()[1].replace("/", ".") + \
                                                       trace_lines[i].strip().split()[2], trace_lines[i].strip().split()[4])
            method_actual_arg_types, xml_names = findActualArgTypesFromTraceLine(trace_lines[i], id, trace_line_param_types)
            for mat, xml in zip(method_actual_arg_types, xml_names):
                if at == mat:
                    if ".".join(trace_lines[i].strip().split()[1].replace("/", ".").split(".")[:-1]) == at or i == api_index:
                        states[pt].insert(0, xml)
            if len(states[pt]) >= len(args_context[pt]) - 1:
                break
    return states


def extractParamTypesFromDesc(desc):
    param_types = []
    array_order_levels_map = collections.OrderedDict({})
    order = 0
    i = 0
    while i < len(desc):
        if desc[i] == "Z":
            param_types.append(f"BOOLEAN@{order}")
            order += 1
            i += 1
        elif desc[i] == "C":
            param_types.append(f"CHAR@{order}")
            order += 1
            i += 1
        elif desc[i] == "B":
            param_types.append(f"BYTE@{order}")
            order += 1
            i += 1
        elif desc[i] == "S":
            param_types.append(f"SHORT@{order}")
            order += 1
            i += 1
        elif desc[i] == "I":
            param_types.append(f"INT@{order}")
            order += 1
            i += 1
        elif desc[i] == "F":
            param_types.append(f"FLOAT@{order}")
            order += 1
            i += 1
        elif desc[i] == "J":
            param_types.append(f"LONG@{order}")
            order += 1
            i += 1
        elif desc[i] == "D":
            param_types.append(f"DOUBLE@{order}")
            order += 1
            i += 1
        elif desc[i] == "L":
            i += 1
            type_str = ""
            while desc[i] != ";":
                type_str += desc[i]
                i += 1
            i += 1
            param_types.append(f"{type_str.replace('/', '.')}@{order}")
            order += 1
        elif desc[i] == "[":
            levels = 0
            while desc[i] == "[":
                levels += 1
                i += 1
            array_order_levels_map[order] = levels
    for order in array_order_levels_map:
        levels = array_order_levels_map[order]
        for i in range(levels):
            if '@' in param_types[order]:
                param_types[order] = f"{param_types[order].split('@')[0]}[]@{param_types[order].split('@')[1]}"
            else:
                param_types[order] = f"{param_types[order]}[]"
    return param_types


def findActualArgTypesFromTraceLine(line, id, param_types):
    if line.split("ARGS: [")[-1].split("]")[0] == "":
        return [], []
    arg_actual_types = []
    arg_values = []
    actual_args = line.split("ARGS: [")[-1].split("]")[0].split(",")
    if len(param_types) > len(actual_args):  
        for i in range(len(param_types) - len(actual_args)):
            uuid_str = str(uuid.uuid4())
            with open(f"{XMLS_DIR}/{id}/{uuid_str}.xml", 'w') as fw:
                fw.write(f"<{param_types[i].split('@')[0]}>\n")
                fw.write("NOT_SERIALIZABLE_XSTREAM_PROBLEM\n")
                fw.write(f"</{param_types[i].split('@')[0]}>\n")
            actual_args.insert(i, f"{uuid_str}.xml")
    else:
        actual_args = actual_args[-len(param_types):]
    for item in actual_args:
        if item.endswith(".xml"):
            arg_actual_types.append(f"{XMLS_DIR}/{id}/{item}")
            arg_values.append(item)
        else:  
            if item.isdigit():
                arg_actual_types.append("int")
                arg_values.append(int(item))
            else:
                arg_actual_types.append("string")
                arg_values.append(item)
    for i in range(len(arg_actual_types)):
        aat = arg_actual_types[i]
        if aat.endswith(".xml"):
            with open(aat, "r") as fr:
                lines = fr.readlines()
                arg_type = lines[0].split("<")[-1].split(">")[0].split()[0]
                arg_type = arg_type.replace("_-", "$").replace('/', '')
                if arg_type.endswith("-array"):
                    elem_tags = [l.split("</")[-1].split(">")[0] for l in lines if l.startswith("  </")]
                    if len(set(elem_tags)) == 1:
                        elem_type = lines[1].split("<")[-1].split(">")[0]
                        arg_type = f"{elem_type}[]"
                    else:
                        arg_type = arg_type.replace("-array", "[]")
                arg_actual_types[i] = arg_type
    return arg_actual_types, arg_values


def countElemsInArray(id, xml):
    xml_file = f"{XMLS_DIR}/{id}/{xml}"
    with open(xml_file, 'r') as fr:
        lines = fr.readlines()
    return len([l for l in lines if l.startswith("  </")])


def postProcessCalleeTypes(knowledge):
    api = knowledge["API"]
    param_types = list(knowledge["args_context"].keys())
    if knowledge["type"] == "virtual":
        callee_actual_type = knowledge["args_actual_types"][0]
        knowledge["API"] = f"{callee_actual_type}.{api.split('.')[-1]}"
        args_context = {}
        for i in range(len(param_types)):
            if i == 0:
                args_context[f"{callee_actual_type}@0"] = knowledge["args_context"][param_types[0]]
            else:
                args_context[param_types[i]] = knowledge["args_context"][param_types[i]]
        knowledge["args_context"] = args_context
        states = {}
        for i in range(len(param_types)):
            if i == 0:
                states[f"{callee_actual_type}@0"] = knowledge["states"][param_types[0]]
            else:
                states[param_types[i]] = knowledge["states"][param_types[i]]
        knowledge["states"] = states


def mergeKnowledge():
    print('===> Merging Knowledge --- ')
    with open(KNOWLEDGE_CLIENTS_JSON_FILE, 'r') as fr:
        clients_info = json.load(fr)
    knowledge = []
    for ci in clients_info:
        id, client, sha, url, lib, old, new, client_prefix, lib_prefix, test, submodule, test_cmd, co_evolve_libs = \
            ci['id'], ci['client'], ci['sha'], ci['url'], ci['lib'], ci['old'], ci['new'], ci['client_prefix'], \
            ci['lib_prefix'], ci['test'], ci['submodule'], ci['test_cmd'], ci['co_evolve_libs']
        if not ci['id'].endswith("-1"):  
            continue
        print(f"{id},{client},{sha},{url},{lib},{old},{new},{client_prefix},{lib_prefix},{test},{submodule},{co_evolve_libs}")
        if not os.path.isfile(f"{TRACES_DIR}/{id}/knowledge.json"):
            continue
        with open(f"{TRACES_DIR}/{id}/knowledge.json", 'r') as fr:
            single_knowlege = json.load(fr)
        single_knowlege = merge(single_knowlege) 
        if single_knowlege not in knowledge:
            knowledge.append(single_knowlege)
    with open(KNOWLEDGE_JSON, 'w') as fw:
        json.dump(knowledge, fw, indent=2)


def merge(single_knowledge): 
    API = single_knowledge['API']
    if API == "org.objectweb.asm.MethodWriter.visitFrame(II[Ljava/lang/Object;I[Ljava/lang/Object;)V":
        single_knowledge['API'] = "org.objectweb.asm.MethodVisitor.visitFrame(II[Ljava/lang/Object;I[Ljava/lang/Object;)V"
    if API == "io.protostuff.runtime.RuntimeSchema.writeTo(Lio/protostuff/Output;Ljava/lang/Object;)V":
        single_knowledge['API'] = "io.protostuff.Schema.writeTo(Lio/protostuff/Output;Ljava/lang/Object;)V"
    if API == "org.apache.http.impl.client.CloseableHttpClient.execute(Lorg/apache/http/client/methods/HttpUriRequest;)Lorg/apache/http/HttpResponse;":
        single_knowledge['API'] = "org.apache.http.client.HttpClient.execute(Lorg/apache/http/client/methods/HttpUriRequest;)Lorg/apache/http/HttpResponse;"
    if API == "org.slf4j.helpers.NOPLogger.getName()Ljava/lang/String;":
        single_knowledge['API'] = "org.slf4j.Logger.getName()Ljava/lang/String;"
    return single_knowledge
