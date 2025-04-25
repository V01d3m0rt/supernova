import os

def list_files_and_folders(directory):
    print(f"Contents of {directory}:")
    for entry in os.listdir(directory):
        print(entry)

if __name__ == "__main__":
    directory = input("Enter the directory path to list contents: ")
    list_files_and_folders(directory)
