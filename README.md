# CompCheck
CompCheck is an antomated upgrade compatibility checking framework which generates incompatibility-revealing tests based on previous examples. CompCheck first establishes an offline knowledge base of incompatibility issues by mining from open source projects and their upgrades. It then discovers incompatibilities for a specific client project, by searching for similar library usages in the knowledge base and generating tests to reveal the problems.

## Install 
You can clone the repository to your local environment. Here we provide our operating environment for reference (Java 1.8; Maven 3.6.3).
```bash
    git clone https://github.com/compsuite-team/compcheck
```

## Get Started
All knowledges with unique kid are saved in `knowledge.json` under knowledge folder. All callsites with unique cid are saved in `callsites.json` under check folder. 

Then you can use following commands to use CompCheck. (You need first get into compcheck folder and you will find `main.py` and relevant files).
### Discover
The knowledge discovery component consists of three main phases: module-level regression testing, knowledge extraction, and knowledge aggregation.
```bash
    python main.py --discover --id [kid]
```

### Check
The incompatibility discovery component leverages the knowledge base to check potential incompatibility issues in new target client projects. Check command will help you complete following 3 steps (knowledge matching, test generation, and test validation) automatically.
```bash
    python main.py --check --id [cid]
```


## Reference
If you would like to use CompCheck in your research, please cite our paper.
```
@article{zhu2023client,
  title={Client-Specific Upgrade Compatibility Checking via Knowledge-Guided Discovery},
  author={Zhu, Chenguang and Zhang, Mengshi and Wu, Xiuheng and Xu, Xiufeng and Li, Yi},
  journal={ACM Transactions on Software Engineering and Methodology},
  volume={32},
  number={4},
  pages={1--31},
  year={2023},
  publisher={ACM New York, NY, USA}
}
```
