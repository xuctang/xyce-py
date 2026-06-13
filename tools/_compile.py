import os


def compile_context_file(output_file="_llm_context.txt"):
    # Folders we DO NOT want the AI to read
    ignored_dirs = {'.venv', '__pycache__', '.git', 'cache', 'log', 'output', 'data'}

    # File types we actually care about
    included_extensions = {'.py', '.json'}

    context_text = ""

    for root, dirnames, filenames in os.walk('.'):
        # Tell os.walk to skip our ignored directories
        dirnames[:] = [dirname for dirname in dirnames if dirname not in ignored_dirs]

        for filename in filenames:
            extension = os.path.splitext(filename)[1]
            if extension not in included_extensions or filename == output_file or filename == "copy_context.py":
                continue

            file_path = os.path.join(root, filename)

            try:
                with open(file_path, 'r', encoding='utf-8') as source_file:
                    file_text = source_file.read()

                # Format it beautifully for the AI
                context_text += f"========== FILE: {file_path} ==========\n"
                context_text += file_text
                context_text += "\n\n"
            except Exception as exc:
                print(f"Skipped {file_path}: {exc}")

    # Write to a single output file
    with open(output_file, 'w', encoding='utf-8') as output_stream:
        output_stream.write(context_text)

    print(f"Successfully compiled {len(context_text)} characters into {output_file}!")

if __name__ == "__main__":
    compile_context_file()
