#!/usr/bin/env python3
import os
import random
import requests
import json
import datetime

import pygit2
import shutil
from pathlib import Path

# import grade submit function
import sys
sys.path.append('/usr/share/codio/assessments')
from lib.grade import send_grade

# Get the students' github username and name of repository
try:
    credentials_folder = "/home/codio/workspace/student_credentials"
    with open(credentials_folder, "r") as f:
        github_username, DIR = f.readlines()
        github_username, DIR = github_username.strip(), DIR.strip()
except Exception as e:
    print( "Error: could not open credentials folder" )
    print( f"Make sure the folder \"{credentials_folder}\" exists" )
    sys.exit(1)

path_string = f'/home/codio/workspace/.guides/{DIR}'
    
# Clear any existing directory (clone_repository will fail otherwise)
dir_path = Path(path_string)
try:
    if dir_path.exists():
        shutil.rmtree(dir_path)
except OSError as e:
    print("Error when removing directory: %s : %s" % (dir_path, e.strerror))

key_dir = "/home/codio/workspace/ssh_keys"
key_file = "id_mcit582"

if not Path(f"{key_dir}/{key_file}").is_file() or not Path(f"{key_dir}/{key_file}.pub").is_file():
    print( f"Error can't find SSH keys!" )
    print( f"Make sure \"{key_dir}/{key_file}\" and \"{key_dir}/{key_file}.pub\" exist" )
    sys.exit(1)

try:
    # import student code using pygit2
    keypair = pygit2.Keypair("git", f"{key_dir}/{key_file}.pub", f"{key_dir}/{key_file}", "")
    callbacks = pygit2.RemoteCallbacks(credentials=keypair)
    print(f'Cloning from: git@github.com:{github_username}/{DIR}.git')
    pygit2.clone_repository(f"git@github.com:{github_username}/{DIR}.git", path_string,
                            callbacks=callbacks)
    sys.path.append(path_string)
except:
    print("Failed to clone the repository.")
    sys.exit()

""" End of repo cloning """
    
try:
    from validate import validate
except ImportError:
    print('Unable to import validation script')
    raise ImportError('Unable to import validation script')

score = validate(path_string)



