import os
import shutil


def get_highest_nonEmpty_folder(entry:str, originalFile:str, childEmpty:bool=False) -> str:
    if os.path.exists(entry):
        #print(f"Path {entry} exists")
        path, _, _ = entry.rpartition("/")
        for root, dirs, files in os.walk(path):
            #print(f"{root} is the root")
            if files:
                #print(f"The folder {root} has files: {str(files)}")
                if len(files) > 1:
                    if originalFile in files:
                        return entry
                    else:
                        return root
                elif len(files) == 1 and files[0] == originalFile:
                    root = get_highest_nonEmpty_folder(root, originalFile, True)
                    return root
                else:
                    return root
            elif dirs:
                if len(dirs) > 1:
                    return root
                else:
                    # if has dir which is empty
                    if childEmpty:
                        return get_highest_nonEmpty_folder(root, originalFile, True)
                    else:
                        return get_highest_nonEmpty_folder(root, originalFile)
    else:
        print("Path does not exist. Try again")


def remove_old_SPASE_JSON(path:str):
    *_, fileName = path.rpartition("/")
    highest_nonEmpty_folder = get_highest_nonEmpty_folder(path, fileName)
    #print("The highest nonEmpty folder is " + highest_nonEmpty_folder)
    # not only file in folder -- just remove file
    if highest_nonEmpty_folder.endswith('.json'):
        print(f"Deleting {highest_nonEmpty_folder}")
        os.remove(highest_nonEmpty_folder)
    # only file in folder, delete up to highest empty folder in path
    else:
        *_, highest_empty_folder = path.partition(f"{highest_nonEmpty_folder}/")
        #print("The highest empty folder is " + highest_empty_folder)
        highest_empty_folder, _, _ = highest_empty_folder.partition('/')
        #print("The highest empty folder is " + highest_empty_folder)
        highest_empty_folder = highest_nonEmpty_folder + '/' + highest_empty_folder
        print(f"Deleting {highest_empty_folder}, which is an otherwise empty parent folder" + \
                " of the provided file")
        try:
            shutil.rmtree(highest_empty_folder)
            print("Directory and its contents removed successfully.")
        except OSError as e:
            print(f"Error removing directory: {e}")
