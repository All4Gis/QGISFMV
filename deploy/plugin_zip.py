# coding: utf-8
# Create QGIS Plugin Zip
from configparser import ConfigParser
import shutil
import sys
import zipfile
import os
import platform

windows = platform.system() == "Windows"

directory = os.path.realpath(__file__)

basePath = os.path.join(directory, os.path.realpath("../code"))
print("basePath : " + basePath)
os.chdir(basePath)

with open("metadata.txt") as mf:
    cp = ConfigParser()
    cp.read_file(mf)
    internal_name = cp.get("general", "internal_name")
    VERSION = cp.get("general", "version")

destPath = os.path.join(
    directory, os.path.realpath("../deploy/Output/" + internal_name)
)
print("destPath : " + destPath)


def copyProjectStructure():
    """ Copy structure project """
    print("Copying structure")
    try:
        if os.path.exists(destPath):
            shutil.rmtree(destPath)

        if windows:
            os.system(
                'robocopy %s %s /E /V /XD ".settings" "sql" "__pycache__" "tests" "ui" ".git" /XF *.bat *.sh *.pro *.ts .gitignore *.docx *.bak *.yml *.pyc *.ps1 *.project *.pydevproject'
                % (basePath, destPath)
            )
        else:
            basePath_linux = os.path.join(directory, os.path.realpath("../code/*"))
            exclude = os.path.join(os.path.dirname(directory), "exclude-file.txt")
            cmd = 'rsync -avi --progress --exclude-from="{}" {} {}'.format(
                exclude, basePath_linux, destPath
            )
            os.system(cmd)

    except Exception as e:
        print("An error occurred when copying the project structure : " + str(e))
        sys.exit(1)


def createZipFile(folder_path, output_path):
    print("Creating zip")
    parent_folder = os.path.dirname(folder_path)

    # Retrieve the paths of the folder contents.
    contents = os.walk(folder_path)
    print("folder_path : " + folder_path)
    try:
        zip_file = zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED)
        for root, folders, files in contents:
            # Include all subfolders, including empty ones.
            for folder_name in folders:
                absolute_path = os.path.join(root, folder_name)
                if windows:
                    relative_path = absolute_path.replace(parent_folder + "\\", "")
                else:
                    relative_path = absolute_path.replace(parent_folder + "/", "")
                zip_file.write(absolute_path, relative_path)
            for file_name in files:
                absolute_path = os.path.join(root, file_name)
                if windows:
                    relative_path = absolute_path.replace(parent_folder + "\\", "")
                else:
                    relative_path = absolute_path.replace(parent_folder + "/", "")
                zip_file.write(absolute_path, relative_path)
        print("'%s' created successfully." % (output_path))
    except IOError as message:
        print(message)
        sys.exit(1)
    except OSError as message:
        print(message)
        sys.exit(1)
    except zipfile.BadZipfile as message:
        print(message)
        sys.exit(1)
    finally:
        zip_file.close()

        if os.path.exists(destPath):
            shutil.rmtree(destPath)


if __name__ == "__main__":
    copyProjectStructure()
    createZipFile(destPath, destPath + "_" + VERSION + ".zip")
