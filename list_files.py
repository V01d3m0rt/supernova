import os

directory_path = "/Users/nikhil/public-workspace/supernova"

files_and_dirs = [item for item in os.listdir(directory_path) if os.path.isdir(os.path.join(directory_path, item)) or os.path.isfile(os.path.join(directory_path, item))]
saved_output_file = "output.txt"
with open(saved_output_file, "w") as f:
    for item in files_and_dirs:
        f.write("{}
".format(item))
print(f"Script executed and output saved to {saved_output_file}".format(saved_output_file))
