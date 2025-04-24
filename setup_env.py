"""
Environment Setup Module
======================

This module automates the setup and maintenance of a Python virtual environment with all required
dependencies for the IsochroneMapsV2 project. It provides an interactive command-line interface
with step-by-step guidance through the environment configuration process.

Setup Process:
1. Create/recreate virtual environment (.venv)
2. Check and upgrade pip to latest version
3. Setup system certificates if needed for secure connections
4. Install or create requirements.txt file using pipreqs if not present
5. Install all required dependencies from requirements.txt
6. Validate dependencies for potential conflicts
7. Check for and update outdated packages

Functions:
    parse_args: Parse command line arguments with non-interactive option.
    get_user_confirmation: Get y/n confirmation from user with consistent handling.
    subprocess_error_handler: Handle errors from subprocess calls with informative messages.
    show_progress: Show a spinner animation while a process is running.
    setup_virtual_environment: Create new or update existing virtual environment.
    check_and_upgrade_pip: Check pip version and upgrade if requested.
    setup_system_certificates: Install system certificates if required for secure connections.
    handle_requirements_file: Create or verify requirements file, generating with pipreqs if needed.
    install_requirements: Install packages from requirements.txt file.
    validate_dependencies: Validate installed dependencies for conflicts or issues.
    parse_outdated_packages: Parse pip list --outdated output into a structured format.
    update_packages: Update specified packages or all outdated packages with user selection.
    check_outdated_dependencies: Check for and optionally update outdated dependencies.
    main: Main function to orchestrate the environment setup process.

Usage:
    Basic interactive setup:
    $ python setup_env.py

    Non-interactive setup with default options:
    $ python setup_env.py --non-interactive

    Run setup from an existing Python environment:
    $ python -m setup_env

Notes:
    - This script can be run repeatedly to maintain environment health
    - Requires Python 3.6+ to function correctly
    - Will create a virtual environment in .venv directory if not present
    - Logs all operations to logs/setup.log for debugging
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure basic logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

try:
    # Try to import with the project structure
    from src.utils.logging_utils import setup_logging
    from src.utils.retry_util import retry
except ImportError:
    # If we can't import yet (likely during initial setup), create minimal implementations
    def setup_logging(log_file_name=None, **kwargs):
        """Simple logging setup for when imports aren't available."""
        if log_file_name:
            try:
                log_dir = Path("logs")
                log_dir.mkdir(exist_ok=True)
                file_handler = logging.FileHandler(log_dir / log_file_name)
                file_handler.setFormatter(
                    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
                )
                logging.getLogger().addHandler(file_handler)
            except Exception as e:
                logging.error(f"Could not set up file logging: {e}")

    def retry(func, max_attempts=3, delay=1, backoff=2, error_handler=None):
        """Simple retry function for when imports aren't available."""
        attempt = 0
        while attempt < max_attempts:
            try:
                return func()
            except Exception as e:
                attempt += 1
                if error_handler:
                    error_handler(e, attempt - 1)
                if attempt == max_attempts:
                    raise
                time.sleep(delay)
                delay *= backoff


# Configure logging
setup_logging(log_file_name="setup.log")

# Define constants
VENV_DIR = Path(".venv")
REQUIREMENTS_FILE = Path("requirements.txt")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Set up Python environment")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompts (uses defaults)",
    )
    return parser.parse_args()


def get_user_confirmation(prompt, default="n", args=None):
    """Get y/n confirmation from user with consistent handling.

    Args:
        prompt: The question to ask the user
        default: Default response if in non-interactive mode
        args: Command line arguments

    Returns:
        bool: True if confirmed, False otherwise
    """
    if args and args.non_interactive:
        logging.info(f"Non-interactive mode: Using default '{default}' for: {prompt}")
        return default == "y"

    while True:
        user_input = input(f"{prompt} (y/n): ").strip().lower()
        if user_input in ("y", "n"):
            return user_input == "y"
        print("Invalid input. Please enter 'y' or 'n'.")


def subprocess_error_handler(error, attempt):
    """Handle errors from subprocess calls."""
    logging.error(f"Command failed (attempt {attempt+1}): {error}")
    if isinstance(error, subprocess.CalledProcessError) and error.output:
        logging.error(f"Command output: {error.output}")


def show_progress(process_name):
    """Show a simple spinner while a process is running.

    Args:
        process_name: Name of the running process

    Returns:
        function: Call this function to stop the spinner
    """
    spinner = ["|", "/", "-", "\\"]
    i = 0

    def spin():
        nonlocal i
        print(f"\r{process_name} {spinner[i]} ", end="", flush=True)
        i = (i + 1) % len(spinner)

    def stop():
        print("\r" + " " * (len(process_name) + 2), end="\r")

    import threading

    stop_event = threading.Event()

    def spin_thread():
        while not stop_event.is_set():
            spin()
            time.sleep(0.1)

    thread = threading.Thread(target=spin_thread)
    thread.daemon = True
    thread.start()

    return lambda: (stop_event.set(), stop())


def setup_virtual_environment(args):
    """Create or update the virtual environment.

    Args:
        args: Command line arguments

    Returns:
        Path: Path to the pip executable
    """
    logging.info("Step 1: Setting up virtual environment")
    pip_path = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "pip"

    try:
        if VENV_DIR.exists():
            logging.info("Virtual environment already exists.")
            if get_user_confirmation(
                "Do you want to delete the existing environment and recreate it?",
                default="n",
                args=args,
            ):
                logging.info("Deleting existing virtual environment...")
                shutil.rmtree(VENV_DIR)
                logging.info("Creating new virtual environment...")
                progress = show_progress("Creating virtual environment")
                subprocess.run(
                    [sys.executable, "-m", "venv", str(VENV_DIR)], check=True
                )
                progress()
                logging.info("Virtual environment created successfully.")
            else:
                logging.info("Using existing virtual environment.")
        else:
            logging.info(
                "Virtual environment not found. Creating virtual environment..."
            )
            progress = show_progress("Creating virtual environment")
            subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
            progress()
            logging.info("Virtual environment created successfully.")
    except Exception as e:
        logging.exception(f"Error managing virtual environment: {e}")
        sys.exit(1)

    return pip_path


def check_and_upgrade_pip(pip_path, args):
    """Check pip version and upgrade if requested.

    Args:
        pip_path: Path to pip executable
        args: Command line arguments
    """
    logging.info("Step 2: Checking and upgrading pip")

    try:
        logging.info("Checking pip version...")
        result = subprocess.run(
            [str(pip_path), "--version"], check=True, capture_output=True, text=True
        )
        logging.info(f"pip version: {result.stdout.strip()}")

        if get_user_confirmation(
            "Do you want to upgrade pip to the latest version?", default="y", args=args
        ):
            progress = show_progress("Upgrading pip")
            retry(
                lambda: subprocess.run(
                    [str(pip_path), "install", "--upgrade", "pip"], check=True
                ),
                error_handler=subprocess_error_handler,
            )
            progress()
            logging.info("pip upgraded successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error checking or upgrading pip: {e}")
        sys.exit(1)


def setup_system_certificates(pip_path, args):
    """Install system certificates if needed.

    Args:
        pip_path: Path to pip executable
        args: Command line arguments
    """
    logging.info("Step 3: Setting up system certificates")

    if get_user_confirmation(
        "Do you need to trust system certificates?", default="n", args=args
    ):
        logging.info("Installing pip_system_certs...")
        try:
            progress = show_progress("Installing system certificates")
            retry(
                lambda: subprocess.run(
                    [
                        str(pip_path),
                        "install",
                        "--trusted-host",
                        "files.pythonhosted.org",
                        "pip_system_certs",
                    ],
                    check=True,
                ),
                error_handler=subprocess_error_handler,
            )
            progress()
            logging.info("pip_system_certs installed successfully.")
        except Exception as e:
            logging.error(f"Error installing pip_system_certs: {e}")
            sys.exit(1)
    else:
        logging.info("User chose not to trust system certificates.")


def handle_requirements_file(pip_path, args):
    """Create or verify requirements file.

    Args:
        pip_path: Path to pip executable
        args: Command line arguments
    """
    logging.info("Step 4: Handling requirements file")

    if not REQUIREMENTS_FILE.exists():
        logging.warning(f"Requirements file '{REQUIREMENTS_FILE}' not found.")
        if get_user_confirmation(
            "Do you want to create a new requirements file using pipreqs?",
            default="y",
            args=args,
        ):
            logging.info("Installing pipreqs...")
            progress = show_progress("Installing pipreqs")
            retry(
                lambda: subprocess.run(
                    [str(pip_path), "install", "pipreqs"], check=True
                ),
                error_handler=subprocess_error_handler,
            )
            progress()

            # Verify pipreqs installation
            pipreqs_path = (
                VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "pipreqs"
            )
            if not pipreqs_path.exists():
                logging.error(
                    "pipreqs is not installed or not found in the virtual environment."
                )
                sys.exit(1)

            logging.info("Generating requirements.txt using pipreqs...")
            progress = show_progress("Generating requirements.txt")
            retry(
                lambda: subprocess.run(
                    [
                        str(pipreqs_path),
                        ".",
                        "--ignore",
                        ".venv",
                        "--force",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                ),
                error_handler=subprocess_error_handler,
            )
            progress()

            if not REQUIREMENTS_FILE.exists() or REQUIREMENTS_FILE.stat().st_size == 0:
                logging.error("Failed to generate a valid requirements.txt file.")
                sys.exit(1)
            logging.info("Requirements file created successfully.")
        else:
            logging.info("Exiting setup - requirements file is required.")
            sys.exit(1)
    else:
        logging.info(f"Using existing requirements file: {REQUIREMENTS_FILE}")


def install_requirements(pip_path):
    """Install packages from requirements file.

    Args:
        pip_path: Path to pip executable
    """
    logging.info("Step 5: Installing requirements")
    progress = show_progress("Installing requirements")

    retry(
        lambda: subprocess.run(
            [str(pip_path), "install", "-r", str(REQUIREMENTS_FILE)], check=True
        ),
        error_handler=subprocess_error_handler,
    )

    progress()
    logging.info("Requirements installed successfully.")


def validate_dependencies(pip_path):
    """Validate installed dependencies.

    Args:
        pip_path: Path to pip executable
    """
    logging.info("Step 6: Validating installed dependencies")

    try:
        progress = show_progress("Validating dependencies")
        subprocess.run([str(pip_path), "check"], check=True)
        progress()
        logging.info("Dependency validation complete.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Dependency validation failed: {e}")
        sys.exit(1)


def parse_outdated_packages(output_text):
    """Parse pip list --outdated output into a structured format.

    Args:
        output_text: Output from pip list --outdated

    Returns:
        list: List of dictionaries containing package information
    """
    lines = output_text.strip().split("\n")
    if len(lines) <= 2:  # Header only, no packages
        return []

    packages = []
    # Skip header lines (Package, Version, etc.)
    for line in lines[2:]:
        parts = line.split()
        if len(parts) >= 3:
            packages.append({"name": parts[0], "current": parts[1], "latest": parts[2]})
    return packages


def update_packages(pip_path, packages, all_packages=False, args=None):
    """Update specified packages or all outdated packages.

    Args:
        pip_path: Path to pip executable
        packages: List of package dictionaries
        all_packages: Whether to update all packages at once
        args: Command line arguments
    """
    if not packages:
        return

    if all_packages or (args and args.non_interactive):
        logging.info("Updating all outdated packages...")
        progress = show_progress("Updating all packages")
        retry(
            lambda: subprocess.run(
                [str(pip_path), "install", "--upgrade", "-r", str(REQUIREMENTS_FILE)],
                check=True,
            ),
            error_handler=subprocess_error_handler,
        )
        progress()
        logging.info("All dependencies updated successfully.")
    else:
        # Let user select packages to update
        print(
            "\nSelect packages to update (comma-separated numbers, 'all', or 'none'):"
        )
        for i, pkg in enumerate(packages):
            print(f"[{i+1}] {pkg['name']}: {pkg['current']} → {pkg['latest']}")

        selection = input("\nPackages to update: ").strip().lower()

        if selection == "none":
            logging.info("No packages selected for update.")
            return
        elif selection == "all":
            to_update = [pkg["name"] for pkg in packages]
        else:
            try:
                indices = [
                    int(i.strip()) - 1 for i in selection.split(",") if i.strip()
                ]
                to_update = [
                    packages[i]["name"] for i in indices if 0 <= i < len(packages)
                ]
            except ValueError:
                logging.error("Invalid selection. No packages will be updated.")
                return

        if to_update:
            logging.info(f"Updating selected packages: {', '.join(to_update)}")
            progress = show_progress("Updating selected packages")
            retry(
                lambda: subprocess.run(
                    [str(pip_path), "install", "--upgrade"] + to_update, check=True
                ),
                error_handler=subprocess_error_handler,
            )
            progress()
            logging.info("Selected packages updated successfully.")
        else:
            logging.info("No valid packages selected for update.")


def check_outdated_dependencies(pip_path, args):
    """Check for and optionally update outdated dependencies.

    Args:
        pip_path: Path to pip executable
        args: Command line arguments
    """
    logging.info("Step 7: Checking for outdated dependencies")

    try:
        progress = show_progress("Checking outdated packages")
        result = subprocess.run(
            [str(pip_path), "list", "--outdated", "--format=columns"],
            check=True,
            capture_output=True,
            text=True,
        )
        progress()

        if result.stdout.strip():
            logging.info("Outdated dependencies found:")
            logging.info(result.stdout.strip())

            outdated_packages = parse_outdated_packages(result.stdout)

            if get_user_confirmation(
                "Do you want to update outdated dependencies?", default="y", args=args
            ):
                if args and args.non_interactive:
                    update_packages(
                        pip_path, outdated_packages, all_packages=True, args=args
                    )
                else:
                    selective_update = get_user_confirmation(
                        "Would you like to select specific packages to update?",
                        default="n",
                        args=args,
                    )
                    update_packages(
                        pip_path,
                        outdated_packages,
                        all_packages=not selective_update,
                        args=args,
                    )
        else:
            logging.info("All dependencies are up-to-date.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error checking for outdated dependencies: {e}")
        sys.exit(1)


def main():
    """Main function to orchestrate the environment setup process."""
    args = parse_args()

    logging.info("Starting environment setup...")

    # Execute steps sequentially
    pip_path = setup_virtual_environment(args)
    check_and_upgrade_pip(pip_path, args)
    setup_system_certificates(pip_path, args)
    handle_requirements_file(pip_path, args)
    install_requirements(pip_path)
    validate_dependencies(pip_path)
    check_outdated_dependencies(pip_path, args)

    logging.info("Setup complete!")


if __name__ == "__main__":
    main()
