#!/usr/bin/env python3
import sys
import os
import importlib.util

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVICE_PATH = os.path.join(PROJECT_ROOT, "app", "services", "atomspace_service.py")

def report(task, success, detail=""):
    status = "PASS" if success else "FAIL"
    print(f"[{status}] {task}")
    if detail:
        print(f"       {detail}")

def verify_atomspace():
    print("Hyperon Integration Verification\n")

    try:
        spec = importlib.util.spec_from_file_location("atomspace_service", SERVICE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        service = module.atomspace_service
        report("Service Module Integrity", True)
    except Exception as e:
        report("Service Module Integrity", False, str(e))
        return

    #verify engine
    try:
        results = service.execute_script("!(+ 40 2)")
        if results == [['42']]:
            report("Engine Execution (Math)", True, "Computed 42 correctly.")
        else:
            report("Engine Execution (Math)", False, f"Unexpected result: {results}")
            
        service.execute_script("(Identity Socrates)")
        check = service.execute_script("!(match &self (Identity Socrates) Socrates)")
        if check == [['Socrates']]:
            report("Engine State Retention", True, "Successfully stored and retrieved an atom.")
        else:
            report("Engine State Retention", False, f"Retained: {check}")

    except ImportError:
        report("Engine Execution", False, "Module 'hyperon' not found. Please run within the Docker container.")
    except Exception as e:
        report("Engine Execution", False, str(e))

if __name__ == "__main__":
    verify_atomspace()
