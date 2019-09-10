# coding: utf-8
from configparser import ConfigParser
import os
import shutil
import sys
import zipfile

directory = os.path.realpath(__file__)
internal_name = "QGIS_FMV"
basePath = os.path.join(directory, os.path.realpath('..\\code'))
os.chdir(basePath)

with open('metadata.txt') as mf:
    cp = ConfigParser()
    cp.read_file(mf)
    VERSION = cp.get('general', 'version')


destPath = os.path.join(directory, os.path.realpath("..\\deploy\\Output\\" + internal_name))

def copyProjectStructure():
    print ("Copying structure")
    try:
        if (os.path.exists(destPath)):
            shutil.rmtree(destPath)

        os.system('robocopy %s %s /E /V /XD ".settings" "sql" "tests" "ui" ".git" /XF *.bat *.pro *.ts .gitignore *.docx *.bak *.yml *.pyc *.ps1 *.project *.pydevproject' % (basePath, destPath))

    except:
        print ("Se ha producido un error al copiar la estructura del proyecto")
        sys.exit(1)

def createZipFile(folder_path, output_path):
    print ("Creating zip")
    parent_folder = os.path.dirname(folder_path)

    # Retrieve the paths of the folder contents.
    contents = os.walk(folder_path)
    try:
        zip_file = zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED)
        for root, folders, files in contents:
            # Include all subfolders, including empty ones.
            for folder_name in folders:
                absolute_path = os.path.join(root, folder_name)
                relative_path = absolute_path.replace(parent_folder + '\\',
                                                      '')
                zip_file.write(absolute_path, relative_path)
            for file_name in files:
                absolute_path = os.path.join(root, file_name)
                relative_path = absolute_path.replace(parent_folder + '\\',
                                                      '')
                zip_file.write(absolute_path, relative_path)
        print ("'%s' created successfully." % (output_path))
    except IOError as message:
        print (message)
        sys.exit(1)
    except OSError as message:
        print (message)
        sys.exit(1)
    except zipfile.BadZipfile as message:
        print (message)
        sys.exit(1)
    finally:
        zip_file.close()

        if (os.path.exists(destPath)):
            shutil.rmtree(destPath)
            
if __name__ == "__main__":    
    copyProjectStructure()
    createZipFile(destPath, destPath + "_" + VERSION + ".zip")
