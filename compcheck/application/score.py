
import os
import json
from macros import PROJECT_DIR
from macros import MATCHING_DIR

strategies = ['most_strict', 'relax_poly', 'relax_prim', 'relax_prim_poly', 'most_strict_relax_coevo']
thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

def computePrecisionAndRecallAllConfigs():
    for s in strategies:
        for t in thresholds:
            computePrecisionAndRecallOneConfig(s, t)

def computePrecisionAndRecallOneConfig(strategy, threshold):
    with open(f"{MATCHING_DIR}/manual.json", "r") as fr:
        manual_labels = json.load(fr)
    with open(f"{MATCHING_DIR}/{strategy}-{threshold}.json", "r") as fr:
        config_labels = json.load(fr)
    total = len(manual_labels)
    tp, tn, fp, fn = 0, 0, 0, 0
    for cid in manual_labels:
        if manual_labels[cid]:
            if config_labels[cid]:
                tp += 1
            else:
                fn += 1
        else:
            if config_labels[cid]:
                fp += 1
            else:
                tn += 1
    precision = round(tp / (tp + fp), 2)
    recall = round(tp / (tp + fn), 2)
    f1 = round(2 * precision * recall / (precision + recall), 3)
    print(strategy, threshold, f"Precision = {precision}", f"Recall = {recall}", f"F1 = {f1}")
    return precision, recall, f1


def genNumbersTexFile():
    global_f1_max = 0
    f1_dict = {}
    for t in thresholds:
        f1_dict[t] = []
        for s in strategies:
            precision, recall, f1 = computePrecisionAndRecallOneConfig(s, t)
            f1_dict[t].append(f1)
            if f1 > global_f1_max:
                global_f1_max = f1
    lines = ""
    for s in strategies:
        for t in thresholds:
            precision, recall, f1 = computePrecisionAndRecallOneConfig(s, t)
            lines += "\\DefMacro{ArgNumCoEvo-"f"{s.replace('_', '-')}"f"{str(t).replace('.', '-')}""OverallPrecision}{"f"{'{:.2f}'.format(precision)}""}\n"
            lines += "\\DefMacro{ArgNumCoEvo-"f"{s.replace('_', '-')}"f"{str(t).replace('.', '-')}""OverallRecall}{"f"{'{:.2f}'.format(recall)}""}\n"
            if f1 == global_f1_max:
                lines += "\\DefMacro{ArgNumCoEvo-"f"{s.replace('_', '-')}"f"{str(t).replace('.', '-')}""OverallF1}{\\cellhlglobal{"f"{'{:.3f}'.format(f1)}""}}\n"
            elif f1 == max(f1_dict[t]):
                lines += "\\DefMacro{ArgNumCoEvo-"f"{s.replace('_', '-')}"f"{str(t).replace('.', '-')}""OverallF1}{\\cellhl{"f"{'{:.3f}'.format(f1)}""}}\n"
            else:
                lines += "\\DefMacro{ArgNumCoEvo-"f"{s.replace('_', '-')}"f"{str(t).replace('.', '-')}""OverallF1}{"f"{'{:.3f}'.format(f1)}""}\n"
    with open(f"{PROJECT_DIR}/../paper-compat/tables/confidence-precision-recall-numbers.tex", "w") as fw:
        fw.write(lines)


def genTableTexFile():
    table_lines = ""
    table_lines += "\\begin{tabular}{crrrrrrrrrrrrrrr}\n"
    table_lines += "\\toprule\n"
    table_lines += "\\multirow{2}{4em}{Confidence Threshold} & \\multicolumn{3}{c}{\\Sstrict } & \\multicolumn{3}{c}{\\Spoly }" + \
                   " & \\multicolumn{3}{c}{\\Sprim } & \\multicolumn{3}{c}{\\Spolyprim } & \\multicolumn{3}{c}{\\Scoevo} \\\\\n"
    table_lines += "\\cmidrule(lr){2-4}\n"
    table_lines += "\\cmidrule(lr){5-7}\n"
    table_lines += "\\cmidrule(lr){8-10}\n"
    table_lines += "\\cmidrule(lr){11-13}\n"
    table_lines += "\\cmidrule(lr){14-16}\n"
    table_lines += "& PR & RC & F$_1$  & PR & RC & F$_1$ & PR & RC & F$_1$ & PR & RC & F$_1$ & PR & RC & F$_1$ \\\\ \midrule\n"
    for t in thresholds:
        table_lines += str(t)
        for s in strategies:
            table_lines += ' & \\UseMacro{ArgNumCoEvo-' + \
                s.replace('_', '-') + str(t).replace('.', '-') + \
                'OverallPrecision}'
            table_lines += ' & \\UseMacro{ArgNumCoEvo-' + \
                s.replace('_', '-') + str(t).replace('.', '-') + \
                'OverallRecall}'
            table_lines += ' & \\UseMacro{ArgNumCoEvo-' + \
                s.replace('_', '-') + str(t).replace('.', '-') + \
                'OverallF1}'
        table_lines += ' \\\\\n'
    table_lines += '\\bottomrule\n'
    table_lines += '\\end{tabular}\n'
    with open(f"{PROJECT_DIR}/../paper-compat/tables/new-confidence-precision-recall-table.tex", "w") as fw:
        fw.write(table_lines)
