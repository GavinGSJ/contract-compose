# 让测试能 import contract_compose（项目根目录加入 sys.path）
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
