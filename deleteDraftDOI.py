import requests
import os
import getpass
from pathlib import Path
from removeSPASE_JSON import remove_old_SPASE_JSON

def delete_draft(doi:str, ResourceID:str) -> None:
    """Deletes the DataCite metadata draft record for the given DOI.
    
    :param doi: The unique doi identifier (not including https://doi.org/)
    :param ResourceID: The SPASE ResourceID for the associated DOI.
    """
    # obtain DataCite login credentials
    user = getpass.getpass("Enter DataCite username: ")
    password = getpass.getpass("Enter DataCite password: ")

    # format ResourceID properly if needed
    if 'spase://' in ResourceID:
        ResourceID = ResourceID.replace("spase://", "")

    # send request via DataCite REST API to delete draft
    url = f"https://api.datacite.org/dois/{doi}"
    response = requests.delete(url, auth=(user, password))
    if response.raise_for_status() is None:
        print(f"Successfully deleted DataCite draft metadata record for {doi}")
    else:
        print(response.text)
    
    # remove draft json from SPASE_JSONs
    try:
        remove_old_SPASE_JSON(f"{str(Path.cwd())}/SPASE_JSONs/{ResourceID}.json")
    except FileNotFoundError:
        print("Could not delete draft JSON in SPASE_JSONs. " \
        "Check ResourceID provided and try again or delete manually.")

# allow calls from the command line
if __name__ == "__main__":
    from sys import argv

    if len(argv) == 1:
        cwd = str(Path.cwd()).replace("\\", "/")
        print(help(delete_draft))
        print()
        print(
            "Rerun the script again, passing the DOI of the draft DataCite metadata record " \
            "you wish to delete, followed by its associated SPASE ResourceID"
        )
        print()
    else:
        if len(argv)==2 and argv[1]=='--help':
            print(help(delete_draft))
        else:
            if 'doi.org/' in str(argv[1]):
                print("Retry, but only provide the unique doi identifier string (what is after doi.org/).")
            else:
                if "\\" in str(argv[2]):
                    argv[2] = argv[2].replace("\\", "/")
                delete_draft(argv[1], argv[2])