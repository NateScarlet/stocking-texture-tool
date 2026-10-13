"""Development only: the tool with the preset file dialogs answered from a folder, for the README pictures. 导出… writes
<folder>\\<suggested name>; 导入… reads the first .json in <folder>.

    python preset_files_shot.py <folder> <file to open> <port>
"""
import glob
import os
import sys

root, first, port = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.getcwd())
os.makedirs(root, exist_ok=True)
from stocking import server  # noqa: E402

server._ask_preset_save = lambda suggested: os.path.join(root, os.path.basename(suggested))
server._ask_preset_open = lambda: next(iter(sorted(glob.glob(os.path.join(root, '*.json')))), None)
sys.argv = ['stocking', first, '--port', port, '--no-window', '--stay', '--isolated']
from stocking.__main__ import main  # noqa: E402

main()
