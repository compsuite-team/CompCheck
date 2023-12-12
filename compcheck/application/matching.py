
import os
import collections

from macros import CHECK_DOWNLOADS_DIR
from utils import findKnowledgeByKid
from utils import findCallSiteByCid


def matchKnowledgeWithOneAPICall(lines, kid, cid, strategy, threshold):
    k = findKnowledgeByKid(kid)
    knowledge_args_context = k['args_context']
    knowledge_args_actual_types = k['args_actual_types']
    matched_args = []
    num_of_args_in_knowledge = len(knowledge_args_context)
    cfg_args_actual_types = []
    cfg_args_context = []
    for i in range(len(lines)):
        if lines[i].startswith('[ARG TYPE]: '):
            cfg_arg_type = lines[i].strip().split()[-1]
            cfg_arg_actual_type = lines[i + 1].strip().split()[-1]
            cfg_arg_trace = lines[i + 2].strip().split(': [')[1].split(']')[0].split(', ')
            cfg_args_actual_types.append(cfg_arg_actual_type)
            cfg_args_context.append((cfg_arg_type, cfg_arg_trace))
    num_of_args_in_cfg = len(cfg_args_context)
    if num_of_args_in_knowledge != num_of_args_in_cfg:
        print(f"NUM OF ARGS MISMATCH! KNOWLEDGE: {num_of_args_in_knowledge}, CFG: {num_of_args_in_cfg}")
        exit(0)
    for i in range(num_of_args_in_knowledge):
        print('### Processing API ARG: ' + str(i) + ' ...')
        knowledge_arg_type = list(knowledge_args_context.items())[i][0]
        cfg_arg_type = cfg_args_context[i][0]
        if isDirectPassParamType(knowledge_arg_type):  # prim
            if matchTwoPrimTypes(kid, cid, knowledge_arg_type, cfg_arg_type, cfg_arg_actual_type, cfg_arg_trace, strategy):
                matched_args.append(knowledge_arg_type)
            continue
        knowledge_arg_trace = knowledge_args_context[knowledge_arg_type]
        cfg_arg_trace = cfg_args_context[i][1]
        knowledge_arg_actual_type = knowledge_args_actual_types[i]
        cfg_arg_actual_type = cfg_args_actual_types[i]
        if isDirectPassActualType(knowledge_arg_actual_type) and isDirectPassActualType(cfg_arg_actual_type):  # prim
            if matchTwoPrimTypes(kid, cid, knowledge_arg_type, cfg_arg_type, cfg_arg_actual_type, cfg_arg_trace, strategy):
                matched_args.append(knowledge_arg_type)
            continue
        types_match = matchTwoArgTypes(knowledge_arg_type, cfg_arg_type, knowledge_arg_actual_type, cfg_arg_actual_type, strategy)
        if not types_match:
            print('---- API ARG: ' + str(i) + ' TYPE NOT MATCH ...', knowledge_arg_actual_type, cfg_arg_actual_type)
            continue
        print('---- API ARG: ' + str(i) + ' TYPE MATCH!')
        print('KNOWLEDGE ARG TRACE: ' + str(knowledge_arg_trace))
        print('CFG ARG TRACE: ' + str(cfg_arg_trace))
        traces_match = matchTwoTraces(knowledge_arg_trace, cfg_arg_trace, strategy)
        if not traces_match:
            print('### API ARG TRACE: ' + str(i) + ' NOT MATCH ...')
            continue
        print('### API ARG TRACE: ' + str(i) + ' MATCH!')
        matched_args.append(cfg_arg_type + ' ' + ','.join(cfg_arg_trace))
    total_num_of_args = len(knowledge_args_context)
    matched_num_of_args = len(matched_args)
    if isCoEvolveLibsMatch(kid, cid):
        print('CO EVO SATISFIED')
        co_evolve_satisfied = True
    else:
        print('CO EVO *NOT* SATISFIED')
        co_evolve_satisfied = False
    if confidenceBeyondThreshold(co_evolve_satisfied, matched_num_of_args, total_num_of_args, strategy, threshold):
        return True, matched_args
    else:
        return False, matched_args



def isCoEvolveLibsMatch(kid, cid):
    k = findKnowledgeByKid(kid)
    c = findCallSiteByCid(cid)
    target_client = c['client']
    if not k['co_evolve_libs']:
        return True
    for dir_path, subpaths, files in os.walk(f"{CHECK_DOWNLOADS_DIR}/{target_client}"):
        for f in files:
            if f == 'pom.xml':
                if isCoEvolveLibesMatchOnePomFile(kid, dir_path + '/' + f):
                    return True
    return False


def isCoEvolveLibesMatchOnePomFile(kid, pom_file):
    k = findKnowledgeByKid(kid)
    knowledge_co_evolve_libs = k['co_evolve_libs']
    match_dict = collections.OrderedDict({})
    with open(pom_file, 'r') as fr:
        lines = fr.readlines()
    for lib in knowledge_co_evolve_libs:
        match_dict[lib] = False
    for lib in knowledge_co_evolve_libs:
        for i in range(len(lines)):
            if '<groupId>' + lib.split(':')[0] + '</groupId>' in lines[i]:
                if '<artifactId>' + lib.split(':')[1] + '</artifactId>' in lines[i + 1]:
                    match_dict[lib] = True
    for lib in knowledge_co_evolve_libs:
        if not match_dict[lib]:
            return False
    return True


def isDirectPassParamType(arg_type):
    direct_pass_types = ['INT@', 'STRING@', 'CLASS@', 'BYTE[]@,' 'java.lang.String@', 'java.lang.Class@']
    for t in direct_pass_types:
        if arg_type.startswith(t):
            return True
    return False


def isDirectPassActualType(arg_type):
    direct_pass_types = ['int', 'java.lang.String', 'java.lang.Class', 'byte[]', 'java.lang.String[]',
                         'null', 'string', 'java-class', 'long']
    for t in direct_pass_types:
        if arg_type.startswith(t) or arg_type.endswith(t):
            return True
    return False


def confidenceBeyondThreshold(co_evolve_satisfied, matched_num_of_args, total_num_of_args, strategy, threshold):
    is_co_evolve_item = 1 if co_evolve_satisfied else 0
    if strategy == 'most_strict_relax_coevo':
        confidence = float(matched_num_of_args) / total_num_of_args
    else:
        confidence = (float(matched_num_of_args) / total_num_of_args) * 0.5 + is_co_evolve_item * 0.5
    print('CONFIDENCE: ' + str(confidence))
    print('THRESHOLD: ' + str(threshold))
    if confidence >= threshold:
        return True
    return False


def matchTwoPrimTypes(kid, cid, knowledge_arg_type, cfg_arg_type, cfg_arg_actual_type, cfg_arg_trace, strategy):
    k = findKnowledgeByKid(kid)
    if 'prim' in strategy:
        return True
    else:
        if 'FROM_ARG' in cfg_arg_trace:
            return True
        else:
            if k['API'] == 'org.objectweb.asm.MethodVisitor.visitFrame(II[Ljava/lang/Object;I[Ljava/lang/Object;)V':
                return True
    return False

def matchTwoArgTypes(knowledge_arg_type, cfg_arg_type, knowledge_arg_actual_type, cfg_arg_actual_type, strategy):
    if knowledge_arg_type == cfg_arg_type or knowledge_arg_type.split('@')[0] == cfg_arg_type:
        obj_inherit = True
    elif knowledge_arg_type.split('@')[0] == "org.objectweb.asm.MethodWriter" and cfg_arg_type == "org.objectweb.asm.MethodVisitor":
        obj_inherit = True
    else:
        obj_inherit = False
    if knowledge_arg_actual_type == cfg_arg_actual_type: 
        obj_same_type = True
    elif knowledge_arg_actual_type == "java.io.ByteArrayInputStream" and cfg_arg_actual_type == "java.io.InputStream":  
        obj_same_type = True
    else:
        obj_same_type = False
    if 'poly' in strategy:
        return obj_inherit
    return obj_same_type


def matchTwoTraces(knowledge_arg_trace, cfg_arg_trace, strategy):
    if cfg_arg_trace == ['ACCEPT']:
        return False
    if cfg_arg_trace[0] in ['FROM_EXTERNAL_API', 'FROM_FIELD']:
        return False
    if 'FROM_ARG' in cfg_arg_trace:
        if listSuffixMatch(cfg_arg_trace[1:], knowledge_arg_trace, strategy):
            return True
    else:
        if listFullMatch(knowledge_arg_trace, cfg_arg_trace, strategy):
            return True
    return False


def listSuffixMatch(small, big, strategy):
    for i in range(len(big) - len(small) + 1):
        for j in range(len(small)):
            cfg_method = small[j]
            knowledge_method = big[i + j]
            if not matchTwoMethodCalls(cfg_method, knowledge_method, strategy):
                break
        else:
            return True
    return False


def listFullMatch(knowledge_trace, cfg_trace, strategy):
    if len(knowledge_trace) != len(cfg_trace):
        return False
    for i in range(len(cfg_trace)):
        cfg_method = cfg_trace[i]
        knowledge_method = knowledge_trace[i]
        if not matchTwoMethodCalls(cfg_method, knowledge_method, strategy):
            return False
    return True


def matchTwoMethodCalls(cfg_method, knowledge_method, strategy):
    if cfg_method == 'ACCEPT' or knowledge_method == 'ACCEPT':
        return True if cfg_method == knowledge_method else False
    cfg_short_method_name = cfg_method.split('(')[0].split('.')[-1]
    knowledge_short_method_name = knowledge_method.split('(')[0].split('.')[-1]
    if 'poly' in strategy:
        if cfg_short_method_name == knowledge_short_method_name:
            return True
    return True if cfg_method == knowledge_method else False

