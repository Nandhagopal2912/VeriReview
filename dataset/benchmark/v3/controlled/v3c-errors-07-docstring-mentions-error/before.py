import subprocess


def compile_assets(source_dir):
    subprocess.run(["npm", "run", "build"], cwd=source_dir, check=True)
    return source_dir / "dist"
