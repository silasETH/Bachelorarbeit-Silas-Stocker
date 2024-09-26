import re
import openai
import subprocess
import os
import psutil

def extract_java_code(text: str) -> str:
    match = re.search(r'```java(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return None
    
def run_command(command):
    timeout = 30

    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, error = process.communicate(timeout=timeout)
    
    except subprocess.TimeoutExpired:
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
        
        output = None
        error = f"Process timed out after {timeout} seconds."

    except:
        output = None
        error = "Process failed"
    
    return output, error

    
def test_java_code(class_name: str, code: str, verbose: bool = False) -> tuple[float, str]:
    file_name = f"{class_name}.java"

    test_class_name = f"Grading{class_name}Test"
    test_file_name = f"{test_class_name}.java"

    try:
        with open(file_name, "w") as file:
            file.write(code)

        compile_command = f"javac -cp junit-platform-console-standalone-1.11.0.jar -d out {file_name} {test_file_name}"

        if verbose:
            print(compile_command)

        compile_result, compile_error = run_command(compile_command)

        if (compile_result == None or compile_error != ""):
            raise Exception(f"Failed to compile: {compile_error}")

        if verbose:
            print(compile_result, compile_error)

        test_command = f"java -jar junit-platform-console-standalone-1.11.0.jar execute --class-path out --scan-classpath --disable-ansi-colors --include-classname {test_class_name}"
        
        if verbose:
            print(test_command)
        
        test_result, test_error = run_command(test_command)

        if (test_result == None or test_error != ""):
            raise Exception(f"Failed to test: {test_error}")

        if verbose:
            print(test_result, test_error)

        tests_passed = int(re.search(r'\[\s+(\d+)\s+tests successful\s+\]', test_result).group(1))
        tests_found = int(re.search(r'\[\s+(\d+)\s+tests found\s+\]', test_result).group(1))

        result = f"{tests_passed} / {tests_found}"
        score =  tests_passed / tests_found
    except Exception as e: 
        result = e
        score = 0

    if os.path.exists(file_name):
        os.remove(file_name)

    return (score, result)
    
def generate_message(client: openai, version: str, seed: int, task_description: str, template: str) -> tuple[str, str, str, str]:
    system = '''Du bist ein Programmierassistent für Java. 
    Du erhälst einen exakten Aufgabentext für eine schwierige Aufgabe des Fachs "Einführung in die Programmierung" und ein dazugehöriges Codingtemplate. 
    Weiter erhältst du Anweisungen, die du unbedingt beachten sollst. Die Bereiche haben jeweils die Überschrift "Aufgabentext", "Template" oder "Anweisung" und sind mit """ markiert.
    Deine Aufgabe ist es den fehlenden Code zu vervollständigen und alle Klassen so auszugeben, dass sie zusammen in ein File mit dem Namen der Public Klasse interpretiert werden können. 
    Stelle sicher, dass der Code wirklich kompiliert. Falls du Klassen aus Java.util.* benötigst, musst du diese importieren. Entferne am Schluss alle Imports und schreibe sie an den Anfang.'''

    prompt = f'''Aufgabentext: """
    {task_description}
    """
    Template: """
    {template}
    """'''

    completion = client.chat.completions.create(
        model=version,
        seed=seed,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
    )
    
    return (completion.choices[0].message.content, completion.system_fingerprint, system, prompt)