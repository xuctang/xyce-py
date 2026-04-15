import os

def llm_compile(output_file="_llm_context.txt"):
    # Folders we DO NOT want the AI to read
    ignore_dirs = {'.venv', '__pycache__', '.git', 'cache', 'log', 'output', 'data'}
    
    # File types we actually care about
    allowed_exts = {'.py', '.json'}
    
    compiled_text = ""

    for root, dirs, files in os.walk('.'):
        # Tell os.walk to skip our ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext not in allowed_exts or file == output_file or file == "copy_context.py":
                continue
                
            filepath = os.path.join(root, file)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Format it beautifully for the AI
                compiled_text += f"========== FILE: {filepath} ==========\n"
                compiled_text += content
                compiled_text += "\n\n"
            except Exception as e:
                print(f"Skipped {filepath}: {e}")

    # Write to a single output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(compiled_text)
        
    print(f"Successfully compiled {len(compiled_text)} characters into {output_file}!")

if __name__ == "__main__":
    llm_compile()