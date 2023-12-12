import argparse
import sys

from discovery.discovery import runKnowledgeDiscovery
from discovery.discovery import runKnowledgeDiscoveryOnOneTest
from discovery.discovery import mergeKnowledge
from application.check import runCheck
from application.check import runCheckOnOneCallSite
from application.score import computePrecisionAndRecallOneConfig
from application.score import genNumbersTexFile, genTableTexFile

def parseArgs(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--discover', help='Discover Knowledge', action='store_true', required=False)
    parser.add_argument('--merge', help='Discover Knowledge', action='store_true', required=False)
    parser.add_argument('--check', help='Apply Knowledge to Check', action='store_true', required=False)
    parser.add_argument('--score', help='Compute Scores', action='store_true', required=False)
    parser.add_argument('--id', help='The Subject ID', required=False)
    parser.add_argument('--client', help='The Client Project Dir', required=False)
    parser.add_argument('--lib', help='The Library', required=False)
    parser.add_argument('--test', help='The failing test', required=False)
    parser.add_argument('--strategy', help='Strategy', required=False)
    parser.add_argument('--threshold', help='Threshold', required=False)
    if len(argv) == 0:
        parser.print_help()
        exit(1)
    opts = parser.parse_args(argv)
    return opts

if __name__ == '__main__':
    opts = parseArgs(sys.argv[1:])
    if opts.discover:
        if opts.id:
            runKnowledgeDiscoveryOnOneTest(opts.id)
        else:
            runKnowledgeDiscovery()
        exit(0)
    if opts.merge:
        mergeKnowledge()
        exit(0)
    if opts.check:
        if opts.id:
            runCheckOnOneCallSite(opts.id)
        exit(0)
    if opts.score:
        genNumbersTexFile()
        genTableTexFile()
        exit(0)
