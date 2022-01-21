import os
from pathlib import Path
import subprocess
import sys
from pprint import pprint as pp
from datetime import datetime
from random import randint
import zipfile
import shutil

ROOT_DIR = Path(__file__).parent.parent.absolute()
APP_DIR = os.path.join(ROOT_DIR, "app")
PACKAGE_DIR = os.path.join(ROOT_DIR, "packages")
REQUIREMENTS_FILE = os.path.join(ROOT_DIR, "requirements.txt")
TIME_STRING = datetime.utcnow().strftime("%Y-%m-%d %H-%M-%S")
PACKAGE_NAME = "MPE TWEETER"


def get_all_files(dir):
    filepaths = []
    for path in os.listdir(dir):
        fullpath = os.path.join(dir, path)
        if os.path.isfile(fullpath):
            filepaths.append(fullpath)
    return filepaths

def get_all_paths(dir):
    paths = []
    for path in os.listdir(dir):
        paths.append(os.path.join(dir, path))
    return paths

# Create packages directory if not exists already
if not os.path.exists(PACKAGE_DIR):
    os.mkdir(PACKAGE_DIR)

# Create the temporary directory to store pip installed modules
tmp_module_dir = os.path.join(PACKAGE_DIR, f"tmp_dir_{randint(10000, 99999)}")
os.mkdir(tmp_module_dir)

# Install pip modules from requirements file into tmp directory
subprocess.check_call([
    sys.executable, 
    "-m", "pip", "install", "-r", REQUIREMENTS_FILE, "--target", tmp_module_dir
    ])

# Create zipfile
zip_path = os.path.join(PACKAGE_DIR, f"{PACKAGE_NAME} {TIME_STRING}.zip")
z = zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED)

# Add app files
for app_file_path in get_all_files(APP_DIR):
    z.write(filename=app_file_path)

# Add 
for path in get_all_paths(tmp_module_dir):
    z.write(filename=path)

shutil.rmtree(tmp_module_dir)
z.close()




