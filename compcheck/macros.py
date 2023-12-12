import os

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__)) 
PROJECT_DIR = SCRIPT_DIR + '/..'

KNOWLEDGE_DIR = SCRIPT_DIR + '/../knowledge'
KNOWLEDGE_DOWNLOADS_DIR = KNOWLEDGE_DIR + '/_downloads'
TEST_LOGS_DIR = KNOWLEDGE_DIR + '/_test_logs'
AGENT_LOGS_DIR = KNOWLEDGE_DIR + '/_agent_logs'
TRACES_DIR = KNOWLEDGE_DIR + '/_traces'
XMLS_DIR = KNOWLEDGE_DIR + '/_xmls'

TRACEAGENT_JAR = SCRIPT_DIR + '/../traceagent/target/traceagent-1.0-SNAPSHOT.jar'
TRACE_BOUND = 10000

_DOWNLOADS_DIR = SCRIPT_DIR + '/../_downloads/'
KNOWLEDGE_CLIENTS_JSON_FILE = SCRIPT_DIR + '/../knowledge/knowledge_clients.json'

KNOWLEDGE_JSON = KNOWLEDGE_DIR + "/knowledge.json"
ARG_OBJECT = KNOWLEDGE_DIR + "/_arg_object_code/"
REUSE_CALLER_JSON = KNOWLEDGE_DIR + "/_arg_object_code/reused_caller.json"

CHECK_DIR = SCRIPT_DIR + '/../check'
CHECK_DOWNLOADS_DIR = CHECK_DIR + '/_downloads'
CALL_SITES_JSON = CHECK_DIR + '/callsites.json'

PARAM_TRACE_JAR = CHECK_DIR + '/javatools-paramtrace/target/paramtrace-1.0-SNAPSHOT-jar-with-dependencies.jar'
CALLER_SLICING_JAR = CHECK_DIR + '/callerslicing/target/callerslicing-1.0-SNAPSHOT-jar-with-dependencies.jar'
API_SEARCH_JAR = CHECK_DIR + "/api-search/target/api-search-1.0-SNAPSHOT.jar"
EVOSUITE_JAR = CHECK_DIR + "/evosuite-master-1.0.7-SNAPSHOT.jar"
THRESHOLD = 0.7
STRATEGY = "relax_prim_poly"

MATCHING_DIR = CHECK_DIR + "/matching"
CONTEXT_DIR = CHECK_DIR + '/context'
PARAM_TRANSFORM_TABLE_JSON = KNOWLEDGE_DIR + "/type_transform.json"
GEN_TESTS_DIR = CHECK_DIR + '/gen'
SEARCH_BUDGET = 60

CHECK_TEST_LOGS_DIR = CHECK_DIR + '/_test_logs'
SBST_GEN_TESTS_DIR = CHECK_DIR + '/sbst_gen'
SBST_TEST_LOGS_DIR = CHECK_DIR + '/_sbst_test_logs'

CALLER_SLICING_CALLSITES = ["c1-5",
                            "c4-2", "c4-3", "c4-5", "c4-6",
                            "c4-8", "c4-10", "c4-12", "c4-13", "c4-15", "c4-16", "c4-18", "c4-19", 
                            "c11-4", 
                            "c12-2", "c12-3", "c12-4",
                            "c13-19", "c13-20", "c13-21", "c13-22", "c13-23", "c13-24", "c13-25", "c13-26", 
                            "c17-1"]
TYPE_CONVERSION_CALL_SITES = ["c8-1", "c9-2", "c11-1", "c11-5"]
REUSE_CALLSITES = ["c1-12", "c1-16", "c1-18",
                   "c2-2", "c2-5", "c2-6",
                   "c3-1", "c3-4",
                   "c6-12",
                   "c8-1", "c8-2", "c8-3",
                   "c9-2", "c9-3", "c9-7", "c9-6", "c9-13",
                   "c10-3",
                   "c11-1", "c11-2", "c11-3", "c11-5",
                   "c12-9",
                   "c14-2", "c14-3", "c14-4", "c14-5", "c14-6",
                   "c15-1", "c15-2", "c15-3", "c15-4", "c15-5", "c15-6",
                   "c19-4", "c19-5",
                   "c23-5", "c23-6", "c23-7"]
MAKE_PUBLIC_CALLSITES = ["c1-17", "c3-4", "c4-1", "c4-4", "c4-7", "c4-9", "c4-11", "c4-14", "c4-17", "c6-3", "c9-1", "c9-10",
                         "c9-12", "c11-3", "c11-5", "c14-6", "c15-1", "c15-2"] 
SEPERATE_FROM_INNER_CLASS_CALLSITES = ["c9-2", "c9-3", "c14-2"]
SHOULD_MATCH_CALLSITES =[]
SHOULD_NOT_MATCH_CALLSITES = []
