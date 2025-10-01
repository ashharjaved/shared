import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def combine_all_files(root_dir, output_file):
    logging.info(f"Starting to combine files from {root_dir} into {output_file}")
    files_processed = 0
    
    # Auto-discover identity subfolders
    identity_root = os.path.join(root_dir, "identity")
    folders = [
        os.path.join(identity_root, sub)
        for sub in ["api", "application", "domain", "infrastructure"]
        if os.path.isdir(os.path.join(identity_root, sub))
    ]
    
    with open(output_file, "w", encoding="utf-8") as outfile:
        for folder_path in folders:
            logging.info(f"Processing folder: {folder_path}")
            
            for root, dirs, files in os.walk(folder_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]  # skip hidden
                for filename in sorted(files):
                    if filename.endswith(".py") and not filename.startswith("."):
                        file_path = os.path.join(root, filename)
                        relative_path = os.path.normpath(
                            os.path.join("src", os.path.relpath(file_path, root_dir))
                        )
                        
                        logging.info(f"Processing file: {file_path}")
                        
                        # Write header
                        outfile.write(f"\n\n### FILE: {relative_path}\n")
                        
                        try:
                            with open(file_path, "r", encoding="utf-8") as infile:
                                outfile.write(infile.read())
                                files_processed += 1
                        except Exception as e:
                            logging.error(f"Error reading file {file_path}: {str(e)}")
                            outfile.write(f"# ERROR reading file {relative_path}: {e}\n")
                        
                        # Footer
                        outfile.write("\n### END FILE\n")
                    else:
                        logging.debug(f"Skipping non-Python file: {filename}")
        
        if files_processed == 0:
            logging.warning("No Python files were processed. Output file may be empty.")
            outfile.write("# No Python files found.\n")
    
    logging.info(f"Finished processing. Total files processed: {files_processed}")


def combine_files(root_dir, output_dir):
    logging.info(f"Starting to combine files from {root_dir} into {output_dir}")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    #subfolders = ["api", "application", "domain", "infrastructure"]\
    subfolders = ["shared"]


    for sub in subfolders:
        folder_path = os.path.normpath(os.path.join(root_dir, sub))
        output_file = os.path.join(output_dir, f"{sub}.txt")
        files_processed = 0

        if not os.path.isdir(folder_path):
            logging.warning(f"Folder not found: {folder_path}")
            continue

        with open(output_file, "w", encoding="utf-8") as outfile:
            logging.info(f"Processing folder: {folder_path}")

            for root, dirs, files in os.walk(folder_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]  # skip hidden dirs
                for filename in sorted(files):
                    if filename.endswith(".py") and not filename.startswith("."):
                        file_path = os.path.join(root, filename)
                        relative_path = os.path.normpath(os.path.relpath(file_path, root_dir))

                        logging.info(f"Processing file: {file_path}")

                        # Write header
                        outfile.write(f"\n\n############## FILE PATH: {relative_path}###########################\n")

                        try:
                            with open(file_path, "r", encoding="utf-8") as infile:
                                outfile.write(infile.read())
                                files_processed += 1
                        except Exception as e:
                            logging.error(f"Error reading file {file_path}: {str(e)}")
                            outfile.write(f"# ERROR reading file {relative_path}: {e}\n")

                        outfile.write("\n##################### END CONTENT#################################\n")

            if files_processed == 0:
                logging.warning(f"No Python files found in {folder_path}")
                outfile.write("# No Python files found in this folder.\n")

        logging.info(f"Finished {sub}. Total files processed: {files_processed}")


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))  # folder where script lives
    combine_files(current_dir, os.path.join(current_dir, "combined_output"))
