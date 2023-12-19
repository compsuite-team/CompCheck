import json
import os
import subprocess as sub
import shutil
import re


from macros import PARAM_TRACE_JAR
from macros import CHECK_DOWNLOADS_DIR
from macros import MATCHING_DIR
from macros import CONTEXT_DIR
from macros import PARAM_TRANSFORM_TABLE_JSON
from macros import THRESHOLD
from macros import STRATEGY
from macros import ARG_OBJECT
from macros import API_SEARCH_JAR
from macros import EVOSUITE_JAR
from macros import GEN_TESTS_DIR
from macros import SEARCH_BUDGET
from macros import CHECK_TEST_LOGS_DIR
from macros import CALLER_SLICING_CALLSITES
from macros import REUSE_CALLSITES
from macros import REUSE_CALLER_JSON
from macros import MAKE_PUBLIC_CALLSITES
from macros import SHOULD_MATCH_CALLSITES
from macros import SHOULD_NOT_MATCH_CALLSITES
from macros import SEPERATE_FROM_INNER_CLASS_CALLSITES

from application.matching import matchKnowledgeWithOneAPICall
from application.slice import sliceCaller
from application.reuse import reuseCaller
from application.patch import makeCallerPublic
from utils import findCallSiteByCid
from utils import findKnowledgeByKid
from utils import findKnowledgeByAPI

strategies = ['most_strict', 'relax_prim', 'relax_poly', 'relax_prim_poly', 'most_strict_relax_coevo']
thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

def runCheck(cid):
    for s in strategies:
        for t in thresholds:
            runCheckOnOneCallSite(cid, s, t)


def runCheckOnOneCallSite(cid, strategy=STRATEGY, threshold=THRESHOLD):
    print('===> Checking Call Site --- id', cid, strategy, threshold)
    c = findCallSiteByCid(cid)
    api, client, sha, url, caller, line = c['API'], c['client'], c['sha'], c['url'], c['caller'], c['line']
    print(f"{api}, {client}, {sha}, {url}, {caller}, {line}")
    extractCallSiteContext(cid)
    if not os.path.isdir(MATCHING_DIR):
        os.makedirs(MATCHING_DIR)
    matching_info = {}
    if os.path.isfile(f"{MATCHING_DIR}/{strategy}-{threshold}.json"):
        with open(f"{MATCHING_DIR}/{strategy}-{threshold}.json", "r") as fr:
            matching_info = json.load(fr)
    matched, _, _ = matchCallSiteContext(cid, strategy, threshold)
    matching_info[cid] = matched
    with open(f"{MATCHING_DIR}/{strategy}-{threshold}.json", "w") as fw:
        json.dump(matching_info, fw, indent=2)
    if matched:
        revealIncompatibility(cid)


def extractCallSiteContext(cid):
    print('Extracting Call Site Context ---')
    c = findCallSiteByCid(cid)
    api, client, sha, url, caller, line = c['API'], c['client'], c['sha'], c['url'], c['caller'], c['line']
    context_output_dir = f"{CONTEXT_DIR}/{cid}"
    if not os.path.isdir(context_output_dir):
        os.makedirs(context_output_dir)
    cwd = os.getcwd()
    if os.path.isfile(f"{context_output_dir}/context.json"):
        return
    os.chdir(f"{CHECK_DOWNLOADS_DIR}/{client}")
    sub.run('git checkout .', shell=True)
    sub.run(f"git checkout {c['sha']}", shell=True)
    buildProject(cid)
    if "$" in caller:
        caller = caller.replace("$", "\\$")
    param_trace_cmd = f"java -jar {PARAM_TRACE_JAR} -f {CHECK_DOWNLOADS_DIR}/{client} -m \"<{api}>\" -o {context_output_dir}" + \
                      f" -c \"{caller}\" -l {line} -n context.json"
    print(param_trace_cmd)
    sub.run(param_trace_cmd, shell=True, stdout=open(os.devnull, "w"), stderr=sub.STDOUT)
    if os.path.isfile(f"{context_output_dir}/context.json"):
        print("Call site found")
    else:
        print("Call site not found")
        exit(0)
    os.chdir(cwd)
    convertContextJSONToCFG(cid)
    expandTypeTransformTable(cid)


def convertContextJSONToCFG(cid):
    context_json = f"{CONTEXT_DIR}/{cid}/context.json"
    with open(context_json, 'r') as fr:
        context = json.load(fr)
    context = context[list(context.keys())[0]][0]
    arg_types, arg_actual_types, arg_cfgs = [], [], []
    for callee_param_type in context['calleeParamTypes']:
        arg_actual_types.append(callee_param_type)
    for param_type in context['calleeParamsContext']:
        arg_types.append(param_type.split('_@')[0])
        arg_cfgs.append(context['calleeParamsContext'][param_type])
    line_no = context['startLine']
    in_class = '.'.join(context['caller'].split('.')[:-1])
    in_method = context['caller'].split('.')[-1]
    output_lines = ''
    for i in range(len(arg_types)):
        output_lines += '===========================\n'
        output_lines += '[ARG TYPE]: ' + str(arg_types[i]) + '\n'
        output_lines += '[ARG ACTUAL TYPE]: ' + str(arg_actual_types[i])  + '\n'
        output_lines += '[ARG CFG]: [' + ', '.join(arg_cfgs[i]) + ']\n'
        output_lines += '===========================\n'
    output_lines += '[INFO]: Target API called in class ' + in_class + \
                    ', method ' + in_method + ', line ' + str(line_no) + '\n'
    with open(f"{CONTEXT_DIR}/{cid}/context.cfg", "w") as fw:
        fw.write(output_lines)


def expandTypeTransformTable(cid):
    type_transform_table = loadPrimTransformTable(cid)
    table_json = f"{CONTEXT_DIR}/{cid}/table.json"
    with open(table_json, "w") as fw:
        json.dump(type_transform_table, fw, indent=2)


def loadPrimTransformTable(cid):
    with open(PARAM_TRANSFORM_TABLE_JSON, 'r') as fr:
        prim_transform_table = json.load(fr)
    return prim_transform_table


def matchCallSiteContext(cid, strategy, threshold):
    print('Processing CFG file: ', cid)
    c = findCallSiteByCid(cid)
    call_site_api, target_client = c['API'], c['client']
    k = findKnowledgeByAPI(call_site_api)
    kid, knowledge_args_context, knowledge_api = k['id'], k['args_context'], k['API']
    with open(f"{CONTEXT_DIR}/{cid}/context.cfg", 'r') as fr:
        lines = fr.readlines()
    num_of_args = len(knowledge_args_context)
    matched_args = []
    for i in range(len(lines)):
        if lines[i].startswith('[INFO]: ') and ', line' in lines[i]:
            api_call = lines[i].strip().split(']: Target API called ')[-1]
            print('*** Processing API CALL SITE: ' + api_call + ' ...')
            args_lines = lines[i - 5 * num_of_args: i]
            print('[DEBUG] ARG LINES RANGE: ' + str(i - 5 * num_of_args) + '--' + str(i - 1))
            break
    is_api_match, matched_api_args = matchKnowledgeWithOneAPICall(args_lines, kid, cid, strategy, threshold)
    api_call_line = f"{target_client}: {knowledge_api}: {api_call}"
    matched_args += matched_api_args
    if is_api_match:
        print('*** API CALL SITE MATCH!')
        return True, api_call_line, matched_args
    else:
        print('*** API CALL SITE NOT MATCH ...')
        return False, api_call_line, matched_args


def revealIncompatibility(cid):
    print('=== Running incompatibility revealing: ', cid)
    if os.path.isdir(f"{GEN_TESTS_DIR}/{cid}"):
        shutil.rmtree(f"{GEN_TESTS_DIR}/{cid}")
    if os.path.isdir(f"{CHECK_TEST_LOGS_DIR}/{cid}"):
        shutil.rmtree(f"{CHECK_TEST_LOGS_DIR}/{cid}")
    c = findCallSiteByCid(cid)
    target_api = c['API']
    k = findKnowledgeByAPI(target_api)
    kid, lib, knowledge_api, new_version = k['id'], k['lib'], k['API'], k['new_version']
    print(kid, lib, knowledge_api, new_version)
    old_version = queryOldVersion(cid)
    print("Target client lib version:", old_version)
    print("Getting shared classes between versions")
    getSharedAndUnionEntitiesBetweenJarVersions(cid, lib, old_version, new_version)
    sliced, reused, new_method_fqn_desc = False, False, None
    if cid in SEPERATE_FROM_INNER_CLASS_CALLSITES:
        print("Need separate inner class out")
        separateInnerClassOut(cid)
        buildProject(cid)
    if cid in MAKE_PUBLIC_CALLSITES:
        print("Need make public")
        makeCallerPublic(cid)
        buildProject(cid)
    if cid in CALLER_SLICING_CALLSITES:
        print("Need caller slicing")
        sliced = True
        new_method_fqn_desc = sliceCaller(cid)
        buildProject(cid)
    if cid in REUSE_CALLSITES:
        print("Need reuse")
        reused = True
        new_method_fqn_desc = reuseCaller(cid)
        buildProject(cid)
    print('--- Running test generation: ', cid)
    test_gen_class_path = runEvoSuiteTestGenOnOneMethodInRepo(kid, cid, sliced, reused, new_method_fqn_desc)
    runGeneratedTests(kid, cid, test_gen_class_path, sliced, reused, new_method_fqn_desc)


def runEvoSuiteTestGenOnOneMethodInRepo(kid, cid, sliced, reused, new_method_fqn_desc):
    c = findCallSiteByCid(cid)
    client = c['client']
    cwd = os.getcwd()
    project_dir = f"{CHECK_DOWNLOADS_DIR}/{client}"
    k = findKnowledgeByKid(kid)
    lib, api, new_version, old_version = k['lib'], k['API'], k['new_version'], queryOldVersion(cid)
    target_method = c['caller']
    target_class = '.'.join(target_method.split('.')[:-1])
    if cid in SEPERATE_FROM_INNER_CLASS_CALLSITES:
        target_class = '.'.join(target_class.split('.')[:-1]) + "." + target_class.split("$")[-1]
    target_short_method = target_method.split('.')[-1]
    if reused or sliced:
        target_short_method = new_method_fqn_desc.split(".")[-1]
    if c['submodule'] != "N/A":
        project_dir += "/" + c['submodule']
    os.chdir(project_dir)
    client_class_path = f"{project_dir}/target/classes"
    if os.path.isdir(f"{project_dir}/target/test-classes"):
        client_class_path += f":{project_dir}/target/test-classes"
    if os.path.isdir('/tmp/jars'):
        shutil.rmtree('/tmp/jars')
    os.makedirs('/tmp/jars')
    os.chdir(project_dir)
    sub.run('mvn dependency:copy-dependencies', shell=True, stdout=open(os.devnull, 'w'), stderr=sub.STDOUT)
    for jar in os.listdir(project_dir + '/target/dependency'):
        if not jar.endswith('.jar'):
            continue
        if jar.startswith(lib.split(':')[1] + '-'):
            continue
        if jar.startswith('junit-'):
            continue
        shutil.copy(project_dir + '/target/dependency/' + jar, '/tmp/jars')
    print("Copied jars to /tmp/jars")
    client_class_path += '$(for i in $(ls /tmp/jars); do printf \':/tmp/jars/\'$i;done)'
    old_jar_path = locateJarInM2Dir(lib, old_version)
    client_class_path += ':' + EVOSUITE_JAR
    output_dir = f"{GEN_TESTS_DIR}/{cid}"
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    os.chdir(output_dir)
    evosuite_log_file = output_dir + '/testgen-log.txt'
    if c["client"] == "ea-async":
        old_jar_path = os.path.expanduser("~") + "/.m2/repository/org/ow2/asm/asm-debug-all/5.0.4/asm-debug-all-5.0.4.jar"
    if cid == "c6-2":
        test_gen_cmd = f"java -Xmx4g -jar {EVOSUITE_JAR} -projectCP {client_class_path}:{old_jar_path}" + \
                       f" -class com.ctrip.framework.apollo.build.MockInjector" + \
                       f" -Dsearch_budget={SEARCH_BUDGET} -Djar_entities_dir=\"{CONTEXT_DIR}/{cid}\""
    else:
        test_gen_cmd = f"java -Xmx4g -jar {EVOSUITE_JAR} -projectCP {client_class_path}:{old_jar_path}" + \
                       f" -class {target_class} -Dtarget_method=\"{target_short_method}\"" + \
                       f" -Dsearch_budget={SEARCH_BUDGET} -Djar_entities_dir=\"{CONTEXT_DIR}/{cid}\""
    print(test_gen_cmd)
    sub.run(test_gen_cmd, shell=True, stdout=open(evosuite_log_file, 'w'), stderr=sub.STDOUT)
    os.chdir(cwd)
    return client_class_path


def queryOldVersion(cid):
    c = findCallSiteByCid(cid)
    return c["version"]


def getSharedAndUnionEntitiesBetweenJarVersions(cid, lib, old_version, new_version):
    old_jar = locateJarInM2Dir(lib, old_version)
    new_jar = locateJarInM2Dir(lib, new_version)
    print("Comparing jars:", old_jar, new_jar)
    old_classes, old_methods, old_fields = getEntitiesInJar(old_jar)
    new_classes, new_methods, new_fields = getEntitiesInJar(new_jar)
    print("Retrieved jar entities")
    shared_classes = sorted([c for c in old_classes if c in new_classes])
    shared_methods = sorted([m for m in old_methods if m in new_methods])
    shared_fields = sorted([f for f in old_fields if f in new_fields])
    union_classes = sorted(list(set().union(old_classes, new_classes)))
    union_methods = sorted(list(set().union(old_methods, new_methods)))
    union_fields = sorted(list(set().union(old_fields, new_fields)))
    print("Computed shared and union entities")
    output_dir = f"{CONTEXT_DIR}/{cid}"
    with open(output_dir + '/versions.txt', 'w') as fw:
        fw.write(f"old: {old_version}\n")
        fw.write(f"new: {new_version}\n")
    with open(output_dir + '/shared_classes.txt', 'w') as fw:
        fw.write('\n'.join(shared_classes) + '\n')
    with open(output_dir + '/shared_methods.txt', 'w') as fw:
        fw.write('\n'.join(shared_methods) + '\n')
    with open(output_dir + '/shared_fields.txt', 'w') as fw:
        fw.write('\n'.join(shared_fields) + '\n')
    with open(output_dir + '/union_classes.txt', 'w') as fw:
        fw.write('\n'.join(union_classes) + '\n')
    with open(output_dir + '/union_methods.txt', 'w') as fw:
        fw.write('\n'.join(union_methods) + '\n')
    with open(output_dir + '/union_fields.txt', 'w') as fw:
        fw.write('\n'.join(union_fields) + '\n')
    return shared_classes, shared_methods, shared_fields, union_classes, union_methods, union_fields


def locateJarInM2Dir(lib, version):
    group_id = lib.split(':')[0]
    artifact_id = lib.split(':')[1]
    jar_path = f"{os.path.expanduser('~')}/.m2/repository/{group_id.replace('.', '/')}/{artifact_id}/{version}/{artifact_id}-{version}.jar"
    if not os.path.isfile(jar_path):
        print(lib + ' ' + version + ' JAR NOT IN .M2, DOWNLOADING ... ')
        cwd = os.getcwd()
        os.chdir(CONTEXT_DIR)
        download_cmd = f"mvn dependency:get -DremoteRepositories=http://insecure.repo1.maven.org/maven2/ " + \
                       f"-DgroupId={group_id} -DartifactId={artifact_id} -Dversion={version} -Dtransitive=false"
        print(download_cmd)
        sub.run(download_cmd, shell=True)
        os.chdir(cwd)
    return jar_path


def getEntitiesInJar(jar_path):
    search_cmd = f"java -jar {API_SEARCH_JAR} -scan -lib {jar_path}"
    print(search_cmd)
    try:
        p = sub.Popen(search_cmd, shell=True, stdout=sub.PIPE, stderr=sub.PIPE)
        p.wait(timeout=20)
    except:
        pass
    print ('jar scan done')
    output_lines = [l.decode("utf-8") for l in p.stdout.readlines()]
    classes, methods, fields = [], [], []
    for i in range(len(output_lines)):
        if output_lines[i].startswith('[CLASS] '):
            classes.append(output_lines[i].strip().split()[-1])
        if output_lines[i].startswith('[METHOD] '):
            methods.append(output_lines[i].strip().split()[-1])
        if output_lines[i].startswith('[FIELD] '):
            fields.append(output_lines[i].strip().split()[-1])
    return classes, methods, fields


def runGeneratedTests(kid, cid, test_gen_class_path, sliced, reused, new_method_fqn_desc):
    c = findCallSiteByCid(cid)
    k = findKnowledgeByKid(kid)
    lib, api, new_version, old_version = k['lib'], k['API'], k['new_version'], queryOldVersion(cid)
    target_method = c['caller']
    target_class = '.'.join(target_method.split('.')[:-1])
    if cid in SEPERATE_FROM_INNER_CLASS_CALLSITES:
        target_class = '.'.join(target_class.split('.')[:-1]) + "." + target_class.split("$")[-1]
    if cid == "c6-2":
        target_class = "com.ctrip.framework.apollo.build.MockInjector"
    if reused or sliced:
        target_method = new_method_fqn_desc
    test_class_path = f"{GEN_TESTS_DIR}/{cid}/evosuite-tests"
    old_jar_path = locateJarInM2Dir(lib, old_version)
    if c["client"] == "ea-async":
        old_jar_path = os.path.expanduser("~") + "/.m2/repository/org/ow2/asm/asm-debug-all/5.0.4/asm-debug-all-5.0.4.jar"
    output_dir = f"{CHECK_TEST_LOGS_DIR}/{cid}"
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    os.chdir(output_dir)
    for dir_path, subpaths, files in os.walk(test_class_path, False):
        for f in files:
            if f.endswith('_scaffolding.java'):
                sub.run(f"javac -cp {test_class_path}:{test_gen_class_path}:{old_jar_path} {dir_path}/{f}", shell=True)
                print(f"javac -cp {test_class_path}:{test_gen_class_path}:{old_jar_path} {dir_path}/{f}")
        for f in files:
            if f.endswith('_ESTest.java'):
                if reused:
                    modify(cid, api)
                removeTimeout(cid, f"{dir_path}/{f}")
                extendObjects(f"{dir_path}/{f}", target_method)
                addOurCustomChecks(f"{dir_path}/{f}", target_method)
                sub.run(f"javac -cp {test_class_path}:{test_gen_class_path}:{old_jar_path} {dir_path}/{f}", shell=True)
                print(f"javac -cp {test_class_path}:{test_gen_class_path}:{old_jar_path} {dir_path}/{f}")
    print("Compiled generated tests")
    test_class = target_class.split('$')[0] + '_ESTest'
    test_log = f"{output_dir}/old.log"
    old_jar_path = locateJarInM2Dir(lib, old_version)
    if c["client"] == "ea-async":
        old_jar_path = os.path.expanduser("~") + "/.m2/repository/org/ow2/asm/asm-debug-all/5.0.4/asm-debug-all-5.0.4.jar"
    test_cmd = f"java -cp {test_class_path}:{old_jar_path}:{test_gen_class_path} org.junit.runner.JUnitCore {test_class}"
    if c["client"] == "mockserver":
        if cid == "c23-4":
            test_cmd = "timeout 30 " + test_cmd
        else:
            test_cmd = "timeout 30 " + test_cmd
    print('OLD TEST CMD: ' + getTestCmdFullClassPath(test_cmd))
    sub.run(test_cmd, shell=True, stdout=open(test_log, 'w'), stderr=sub.STDOUT)
    prependTestCommandToLog(test_log, f"OLD TEST CMD: {getTestCmdFullClassPath(test_cmd)}\n")
    test_class = target_class.split('$')[0] + '_ESTest'
    test_log = f"{output_dir}/new.log"
    new_jar_path = locateJarInM2Dir(lib, new_version)
    if c["client"] == "ea-async":
        new_jar_path = os.path.expanduser("~") + "/.m2/repository/org/ow2/asm/asm/7.2/asm-7.2.jar:" + \
                       os.path.expanduser("~") + "/.m2/repository/org/ow2/asm/asm-tree/7.2/asm-tree-7.2.jar:" + \
                       os.path.expanduser("~") + "/.m2/repository/org/ow2/asm/asm-analysis/7.2/asm-analysis-7.2.jar"
    test_cmd = f"java -cp {test_class_path}:{new_jar_path}:{test_gen_class_path} org.junit.runner.JUnitCore {test_class}"
    if c["client"] == "mockserver":
        if cid == "c23-4":
            test_cmd = "timeout 30 " + test_cmd
        else:
            test_cmd = "timeout 30 " + test_cmd
    print('NEW TEST CMD: ' + getTestCmdFullClassPath(test_cmd))
    sub.run(test_cmd, shell=True, stdout=open(test_log, 'w'), stderr=sub.STDOUT)
    prependTestCommandToLog(test_log, f"NEW TEST CMD: {getTestCmdFullClassPath(test_cmd)}\n")

    resetClient(cid)


def removeTimeout(cid, test_java_file):
    c = findCallSiteByCid(cid)
    if c['client'] == "mockserver":
        return
    with open(test_java_file, 'r') as fr:
        lines = fr.readlines()
    for i in range(len(lines)):
        if lines[i].strip().startswith("@Test(timeout = "):
            lines[i] = lines[i].split("(")[0] + "\n"
    with open(test_java_file, 'w') as fw:
        fw.write("".join(lines))


def extendObjects(test_java_file, target_method):
    with open(test_java_file, 'r') as fr:
        lines = fr.readlines()
    for i in range(len(lines)):
        if lines[i].strip().startswith("import "):
            import_end_line = i
    for i in range(len(lines)):
        if lines[i].strip().startswith("public class"):
            class_name = lines[i].split("public class ")[-1].split(" extends ")[0].split("_ESTest")[0]
    for i in range(len(lines)):
        if lines[i].strip().startswith("ArrayList<Field> ") and lines[i].strip().endswith(" = new ArrayList<Field>();"):
            lines[i] = lines[i].replace(" = new ArrayList<Field>();", " = new ArrayList<Field>(Arrays.asList(" + \
                                        class_name + ".class.getDeclaredFields()));")
            lines = lines[:import_end_line + 1] + ["import java.util.Arrays;\n"] + lines[import_end_line + 1:]
        if lines[i].strip().startswith("NotWrapSchema ") and " = new NotWrapSchema(" in lines[i]:
            v = lines[i].split(" = new NotWrapSchema(")[0].split("NotWrapSchema ")[-1]
            lines[i] = f"NotWrapSchema {v} = (NotWrapSchema) new ScopedProtobufSchemaManager(Thread.currentThread().getContextClassLoader()).getOrCreateSchema(NotWrapSchema.class);\n"
            lines = lines[:import_end_line + 1] + ["import org.apache.servicecomb.codec.protobuf.utils.ScopedProtobufSchemaManager;\n"] + lines[import_end_line + 1:]
    with open(test_java_file, 'w') as fw:
        fw.write("".join(lines))

def addOurCustomChecks(test_java_file, target_method):
    target_method_short = target_method.split('.')[-1].split('(')[0]
    with open(test_java_file, 'r') as fr:
        lines = fr.readlines()
    output_lines = []
    old_has_exception = False
    for i in range(len(lines)):
        output_lines.append(lines[i])
        if ' = ' in lines[i] and '.' + target_method_short + '(' in lines[i]:
            obj = lines[i].split(' = ')[0].split()[-1]
            check_line = '      ' + \
                'System.out.println(\"CompCheck: assert toString: \" + ' + \
                obj + '.toString());\n'
            output_lines.append(check_line)
    for i in range(len(lines)):
        if '// Undeclared exception!' in lines[i]:
            old_has_exception = True
    if old_has_exception:
        output_lines = []
        for i in range(len(lines)):
            output_lines.append(lines[i])
            if '} catch(' in lines[i]:
                old_message = lines[i+2].split('//')[-1].strip()
                if 'For input string: ' in old_message:
                    continue
                if 'Cannot parse date' in old_message:
                    continue
                if 'json can not be null or empty' in old_message:
                    continue
                if '}' == old_message:
                    continue
                if 'expected:<OK (200)' in old_message:
                    continue
                if 'no message in exception' in old_message:
                    continue
                check_line = '      ' + \
                    'if (!e.getMessage().startsWith(\"' + old_message + \
                    '\")) {fail("CompCheck: Exception Message Changed! | Used to be ' + old_message + \
                    ' | But now is " + e);}'
                output_lines.append(check_line)
    with open(test_java_file, 'w') as fw:
        fw.write(''.join(output_lines))

def prependTestCommandToLog(log, test_cmd):
    with open(log, 'r') as fr:
        lines = fr.readlines()
    lines.insert(0, test_cmd)
    with open(log, 'w') as fw:
        fw.write(''.join(lines))


def getTestCmdFullClassPath(test_cmd):
    p = sub.Popen('echo $(for i in $(ls /tmp/jars); do printf \':/tmp/jars/\'$i;done)', shell=True, stdout=sub.PIPE, stderr=sub.STDOUT)
    p.wait()
    full_cp = p.stdout.readline().decode('UTF-8').strip()
    test_cmd_full = re.sub('\$\(.*done\)', full_cp, test_cmd)
    return test_cmd_full


def separateInnerClassOut(cid):
    c = findCallSiteByCid(cid)
    for f in os.listdir(f"{CONTEXT_DIR}/{cid}"):
        if f.endswith(".java"):
            with open(f"{CONTEXT_DIR}/{cid}/{f}", 'r') as fr:
                lines = fr.readlines()
                for i in range(len(lines)):
                    if lines[i].strip().startswith("// path = "):
                        target_path = lines[i].strip().split(" = ")[-1]
                        break
            shutil.copyfile(f"{CONTEXT_DIR}/{cid}/{f}", f"{CHECK_DOWNLOADS_DIR}/{c['client']}/{target_path}")


def buildProject(cid):
    c = findCallSiteByCid(cid)
    cwd = os.getcwd()
    os.chdir(f"{CHECK_DOWNLOADS_DIR}/{c['client']}")
    if os.path.isfile(f"{CONTEXT_DIR}/{cid}/patch"):
        sub.run(f"git apply {CONTEXT_DIR}/{cid}/patch", shell=True, stdout=open(os.devnull, 'w'), stderr=sub.STDOUT)
    if c['submodule'] != "N/A" and "upiter" not in c['submodule']:
        os.chdir(f"{CHECK_DOWNLOADS_DIR}/{c['client']}/{c['submodule']}")
    build_log = f"/tmp/{cid}.build"
    sub.run('mvn install -DskipTests -fn -Denforcer.skip -Dgpg.skip -Drat.skip -Dcheckstyle.skip -Danimal.sniffer.skip', shell=True,
            stdout=open(build_log, 'w'), stderr=sub.STDOUT)
    os.chdir(cwd)


def modify(cid, api):
    with open(REUSE_CALLER_JSON, 'r') as frcj:
        reused_context = json.load(frcj)
    
    object_definition = []
    args = []
    for rc in reused_context:
        if rc["id"] == cid:
            for key in rc["args"]:    
                if "arg_0" not in key:
                    args.append(key.split("_")[-1])
                object_definition += rc["args"][key]

    context_json = CONTEXT_DIR + '/' + cid + '/context.json'
    with open(context_json, 'r') as f:
        context = json.load(f)
    caller = context[api][0]["caller"]
    caller_class_name = caller.split('.')[-2]
    caller_method_name = caller.split('.')[-1].split('(')[0]
    target_method = caller_class_name + '.' + caller_method_name
    rindex = caller.rindex('.')
    part_caller = caller[0: rindex].replace('.', '/')
    if '$' in part_caller:
        dot_rindex = part_caller.rindex('/')
        short_caller = part_caller[: dot_rindex + 1] + part_caller[dot_rindex + 1:].split("$")[-1]
        test_java_file = short_caller + '_ESTest.java'
    else:
        test_java_file = part_caller + '_ESTest.java'
    estest_path = GEN_TESTS_DIR + '/' + cid + '/evosuite-tests/' + test_java_file
    with open(estest_path, 'r') as fr:
        test_java_lines = fr.readlines()

    if ".<init>" in target_method:
        target_method = target_method.replace(".<init>", "")
        method = target_method.split(".")[-1]
        matching_token = "new " + method + "()"    
    else:
        method = target_method.split(".")[-1]
        matching_token = "." + method + "("

    
    package_index = 0
    x_index = []
    space_num = 0
    for i in range(len(test_java_lines)):
        if 'package' in test_java_lines[i]:
            package_index = i + 1
        if matching_token in test_java_lines[i]:
            x_index.append(i)

            while test_java_lines[i][space_num] == ' ':
                space_num += 1

    if cid == "c23-5":
        temp_index = []
        for list in split_array(x_index):
            temp_index.append(list[0])
        x_index = temp_index

    extra_reused = ["c19-4", "c19-5"]
    if cid in extra_reused:
        reused_dir = f"{ARG_OBJECT}/reused/{cid}/reused_arg.java"
        with open(reused_dir, 'r') as frdr:
            object_definition = frdr.readlines()
    insert_object_definition = []
    for line in object_definition:
        if cid == "c1-18":
            if "Boo" in line:
                line = line.replace("Boo", "KryoSerializer.Boo")
        if cid == "c10-3":
            if "TestMap" in line:
                line = line.replace("TestMap", "NotWrapSchema.TestMap")
        if cid == "c6-12":
            if "parentModule" in line:
                line = line.replace("this.parentModule", "Module parentModule")
        if cid == "c9-2" or cid == "c9-3":
            if "Base64.decodeBase64" in line:
                continue
        insert_object_definition.append(" " * space_num + line + '\n')

    for index in x_index[::-1]:
        if cid == "c11-3":
            start = test_java_lines[index].rindex("(") + 1
            end = test_java_lines[index].rindex(")")
            origin = test_java_lines[index][start: end]
        else:
            start = test_java_lines[index].index("(") + 1
            end = test_java_lines[index].rindex(")")
            origin = test_java_lines[index][start: end]
        if origin.strip() == "":
            insert_args = ", ".join(args)
        else:
            origin_args = origin.strip().split(", ")
            insert_args = ", ".join(origin_args + args)
        test_java_lines[index] = test_java_lines[index][:start] + insert_args + test_java_lines[index][end:]
        test_java_lines[index:index] = insert_object_definition

    reused_lines, desc, args, imports_lines, deps_lines = readReuseResultFromReusedCaller(cid)

    if len(deps_lines):
        addExtraDeps(cid, deps_lines)
    if len(imports_lines):
        addExtraImports(cid, imports_lines)

    for line in imports_lines[::-1]:
        test_java_lines.insert(package_index, line)

    with open(estest_path, 'w') as fw:
        for line in test_java_lines:
            fw.write(line)

def split_array(nums):
    result = []
    temp = [nums[0]]
    for i in range(1, len(nums)):
        if nums[i] - nums[i-1] > 1:
            result.append(temp)
            temp = [nums[i]]
        else:
            temp.append(nums[i])
    result.append(temp)
    return result

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
    return lines, desc, args, imports_lines, deps_lines

    
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





def addExtraDepsInPom(deps_lines, pom_file):
    fr = open(pom_file, 'r')
    lines = fr.readlines()
    fr.close()


    for i in range(len(lines)):
        if ("</dependencies>") in lines[i]:
            lines = lines[:i] + deps_lines + ['\n'] + lines[i:]

    fw = open("./pom.xml", 'w')
    fw.write(''.join(lines))
    fw.close()


def resetClient(cid):
    c = findCallSiteByCid(cid)
    cwd = os.getcwd()
    os.chdir(f"{CHECK_DOWNLOADS_DIR}/{c['client']}")
    if c['submodule'] != "N/A":
        os.chdir(f"{CHECK_DOWNLOADS_DIR}/{c['client']}/{c['submodule']}")
    sub.run('git checkout .', shell=True)
    os.chdir(cwd)