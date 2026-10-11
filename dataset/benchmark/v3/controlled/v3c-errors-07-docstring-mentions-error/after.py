import subprocess


def compile_assets(source_dir):
    """Build the assets.

    Raises subprocess.CalledProcessError when the build fails.
    """
    # subprocess.CalledProcessError is handled by the caller
    subprocess.run(["npm", "run", "build"], cwd=source_dir, check=True)
    return source_dir / "dist"
