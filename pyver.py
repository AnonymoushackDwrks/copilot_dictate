import subprocess
import sys

def get_packages(py_args):
    try:
        # Run pip list using the arguments provided
        result = subprocess.run(py_args + ['-m', 'pip', 'list'], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')[2:] # Skip headers
        
        packages = set()
        for line in lines:
            if line.strip():
                # Extract just the package name (the first word) and make it lowercase
                pkg_name = line.split()[0].lower()
                packages.add(pkg_name)
        return packages
    except Exception as e:
        print(f"Error running {py_args}: {e}")
        return set()

# Set up clean lists for Windows execution
cmd1 = ['py', '-3.11']
cmd2 = ['py', '-3.14']

pkgs_311 = get_packages(cmd1)
pkgs_314 = get_packages(cmd2)

common = pkgs_311.intersection(pkgs_314)
only_311 = pkgs_311 - pkgs_314
only_314 = pkgs_314 - pkgs_311

print("=== SUMMARY ===")
print(f"Total in 3.11: {len(pkgs_311)}")
print(f"Total in 3.14: {len(pkgs_314)}")
print(f"\nCommon Packages ({len(common)}):\n{sorted(list(common))}")
print(f"\nUnique to 3.11 ({len(only_311)}):\n{sorted(list(only_311))}")
print(f"\nUnique to 3.14 ({len(only_314)}):\n{sorted(list(only_314))}")
