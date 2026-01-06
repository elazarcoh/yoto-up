#!/usr/bin/env python3
"""
Cross-Platform Docker Builder & Verifier for ARM64
Builds a Dockerized FastAPI application for linux/arm64 on x86 hosts
with automated verification via emulation.
"""

import argparse
import base64
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration for the builder."""

    image_name: str = "yoto-web-server"
    skip_test: bool = False
    clean: bool = False
    builder_name: str = "rpi_builder"
    container_name: str = "rpi_test"
    test_port: int = 8000
    health_check_timeout: int = 30
    health_check_retries: int = 5
    dockerfile_path: str = "Dockerfile"


class DockerCommandError(Exception):
    """Raised when a Docker command fails."""

    pass


class EnvironmentChecker:
    """Checks the host environment for cross-platform build capability."""

    def __init__(self, config: Config):
        self.config = config

    def check_docker_installed(self) -> bool:
        """Verify Docker is installed and accessible."""
        logger.info("Checking if Docker is installed...")
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info(f"✓ Docker found: {result.stdout.strip()}")
                return True
            logger.error("✗ Docker version check failed")
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.error("✗ Docker is not installed or not in PATH")
            return False

    def check_docker_daemon(self) -> bool:
        """Verify Docker daemon is running."""
        logger.info("Checking if Docker daemon is running...")
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info("✓ Docker daemon is running")
                return True
            logger.error("✗ Docker daemon is not responding")
            return False
        except subprocess.TimeoutExpired:
            logger.error("✗ Docker daemon check timed out")
            return False

    def check_buildx(self) -> bool:
        """Verify docker buildx is available."""
        logger.info("Checking if docker buildx is available...")
        try:
            result = subprocess.run(
                ["docker", "buildx", "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info(f"✓ Buildx found: {result.stdout.strip()}")
                return True
            logger.error("✗ Docker buildx is not available")
            return False
        except FileNotFoundError:
            logger.error("✗ Docker buildx is not installed")
            return False

    def setup_qemu_emulation(self) -> bool:
        """Setup QEMU emulation for ARM64 binaries."""
        logger.info("Setting up QEMU emulation for multi-platform support...")
        try:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--privileged",
                    "--rm",
                    "tonistiigi/binfmt",
                    "--install",
                    "all",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                logger.info("✓ QEMU emulation setup complete")
                return True
            logger.error("✗ QEMU emulation setup failed")
            logger.debug(f"Error output: {result.stderr}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("✗ QEMU setup timed out")
            return False

    def check_or_create_builder(self) -> bool:
        """Check if multi-arch builder exists, create if needed."""
        logger.info(f"Checking for builder instance '{self.config.builder_name}'...")

        # List existing builders
        try:
            result = subprocess.run(
                ["docker", "buildx", "ls"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                if self.config.builder_name in result.stdout:
                    logger.info(f"✓ Builder '{self.config.builder_name}' already exists")
                    return True

                logger.info(f"Creating new builder '{self.config.builder_name}'...")
                create_result = subprocess.run(
                    ["docker", "buildx", "create", "--name", self.config.builder_name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if create_result.returncode != 0:
                    logger.error(f"✗ Failed to create builder: {create_result.stderr}")
                    return False

                logger.info("Bootstrapping builder...")
                bootstrap_result = subprocess.run(
                    ["docker", "buildx", "inspect", "--bootstrap"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if bootstrap_result.returncode == 0:
                    logger.info(f"✓ Builder '{self.config.builder_name}' created and bootstrapped")
                    return True
                logger.error("✗ Failed to bootstrap builder")
                return False

        except subprocess.TimeoutExpired as e:
            logger.error(f"✗ Builder check timed out: {e}")
            return False

    def check_dockerfile(self) -> bool:
        """Verify Dockerfile exists."""
        logger.info(f"Checking for Dockerfile at '{self.config.dockerfile_path}'...")
        dockerfile = Path(self.config.dockerfile_path)
        if dockerfile.exists():
            logger.info("✓ Dockerfile found")
            return True
        logger.error(f"✗ Dockerfile not found at {self.config.dockerfile_path}")
        return False

    def run_all_checks(self) -> bool:
        """Run all environment checks."""
        logger.info("=" * 60)
        logger.info("Phase 1: Environment Readiness Check")
        logger.info("=" * 60)

        checks = [
            ("Docker Installation", self.check_docker_installed),
            ("Docker Daemon", self.check_docker_daemon),
            ("Docker Buildx", self.check_buildx),
            ("QEMU Emulation", self.setup_qemu_emulation),
            ("Multi-Arch Builder", self.check_or_create_builder),
            ("Dockerfile", self.check_dockerfile),
        ]

        all_passed = True
        for check_name, check_func in checks:
            try:
                if not check_func():
                    all_passed = False
                    logger.warning(f"✗ {check_name} check failed")
            except Exception as e:
                all_passed = False
                logger.error(f"✗ {check_name} check error: {e}")

        logger.info("=" * 60)
        if all_passed:
            logger.info("✓ All environment checks passed!")
        else:
            logger.error("✗ Some environment checks failed. See above for details.")
        logger.info("=" * 60)

        return all_passed


class DockerBuilder:
    """Handles the Docker build process."""

    def __init__(self, config: Config):
        self.config = config

    def build_image(self) -> bool:
        """Build the Docker image for ARM64."""
        logger.info("=" * 60)
        logger.info("Phase 2: Building Docker Image for linux/arm64")
        logger.info("=" * 60)

        image_tag = f"{self.config.image_name}:rpi"
        logger.info(f"Building image: {image_tag}")
        logger.warning(
            "⚠ Note: ARM64 builds on x86 are significantly slower (up to 5x) due to emulation."
        )

        try:
            # Extract directory from dockerfile path (handle both / and \ separators)
            dockerfile_dir = str(Path(self.config.dockerfile_path).parent)
            if not dockerfile_dir or dockerfile_dir == ".":
                dockerfile_dir = "."

            cmd = [
                "docker",
                "buildx",
                "build",
                "--platform",
                "linux/arm64",
                "-t",
                image_tag,
                "--load",
                "--pull",
                dockerfile_dir,
            ]

            logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                timeout=600,  # 10 minutes
                check=False,
            )

            if result.returncode == 0:
                logger.info(f"✓ Successfully built image: {image_tag}")
                return True

            logger.error(f"✗ Build failed with exit code {result.returncode}")

            # Provide troubleshooting hints
            logger.info("\nTroubleshooting hints:")
            logger.info("  • Exec Format Error: Ensure QEMU is properly installed")
            logger.info("  • Missing Wheels: Add gcc/build-essential to Dockerfile")
            logger.info("  • Slow Build: This is normal for ARM64 emulation on x86")
            return False

        except subprocess.TimeoutExpired:
            logger.error("✗ Build timed out after 10 minutes")
            return False
        except Exception as e:
            logger.error(f"✗ Build error: {e}")
            return False

    def image_exists(self) -> bool:
        """Check if the built image exists locally."""
        image_tag = f"{self.config.image_name}:rpi"
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", image_tag],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking image: {e}")
            return False


class DockerVerifier:
    """Handles verification of the built image via emulation."""

    def __init__(self, config: Config):
        self.config = config
        self.image_tag = f"{self.config.image_name}:rpi"

    def cleanup_container(self) -> None:
        """Stop and remove the test container if it exists."""
        logger.info(f"Cleaning up container '{self.config.container_name}'...")
        try:
            subprocess.run(
                ["docker", "stop", self.config.container_name],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["docker", "rm", self.config.container_name],
                capture_output=True,
                timeout=10,
            )
            logger.info("✓ Container cleaned up")
        except Exception as e:
            logger.debug(f"Container cleanup note: {e}")

    def start_container(self) -> bool:
        """Start the container with the built image."""
        logger.info(f"Starting container '{self.config.container_name}'...")
        self.cleanup_container()

        try:
            # Generate a valid Fernet encryption key for the app
            # The app requires a base64-encoded 32-byte key
            test_encryption_key = base64.urlsafe_b64encode(os.urandom(32)).decode()

            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                self.config.container_name,
                "--platform",
                "linux/arm64",
                "-p",
                f"{self.config.test_port}:{self.config.test_port}",
                "-e",
                f"SESSION_ENCRYPTION_KEY={test_encryption_key}",
                self.image_tag,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(f"✓ Container started: {result.stdout.strip()[:12]}...")
                time.sleep(2)  # Wait for service to start
                return True

            logger.error(f"✗ Failed to start container: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("✗ Container startup timed out")
            return False

    def verify_architecture(self) -> bool:
        """Verify the container is running ARM64."""
        logger.info("Verifying container architecture...")
        try:
            result = subprocess.run(
                ["docker", "exec", self.config.container_name, "uname", "-m"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                arch = result.stdout.strip()
                if arch == "aarch64":
                    logger.info(f"✓ Container architecture verified: {arch}")
                    return True
                logger.error(f"✗ Unexpected architecture: {arch} (expected aarch64)")
                return False

            logger.error("✗ Failed to check architecture")
            return False

        except subprocess.TimeoutExpired:
            logger.error("✗ Architecture check timed out")
            return False

    def health_check(self) -> bool:
        """Perform health check on the FastAPI service using docker exec."""
        logger.info("Performing FastAPI health check...")
        retries = self.config.health_check_retries
        timeout = self.config.health_check_timeout

        for attempt in range(retries):
            try:
                logger.debug(f"Health check attempt {attempt + 1}/{retries}...")
                # Use docker exec with Python to check the health endpoint
                # This avoids Docker Desktop networking issues on Windows
                cmd = (
                    'python -c "import urllib.request; '
                    f"r = urllib.request.urlopen('http://localhost:{self.config.test_port}/health'); "
                    'print(r.status)"'
                )
                result = subprocess.run(
                    ["docker", "exec", self.config.container_name, "sh", "-c", cmd],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                # Check if we got a 200 status
                if "200" in result.stdout:
                    logger.info("✓ FastAPI health check passed (HTTP 200)")
                    return True
                else:
                    logger.debug(f"  Attempt {attempt + 1}: Response - {result.stdout.strip()}")
                    time.sleep(2)

            except subprocess.TimeoutExpired:
                logger.debug(f"  Attempt {attempt + 1}: Health check timed out, retrying...")
                time.sleep(2)
            except Exception as e:
                logger.debug(f"  Attempt {attempt + 1}: Error - {e}")
                time.sleep(2)

        logger.error(f"✗ Health check failed after {retries} attempts")
        logger.info(
            f"Troubleshooting: Check container logs with: docker logs {self.config.container_name}"
        )
        return False

    def run_verification(self) -> bool:
        """Run all verification steps."""
        logger.info("=" * 60)
        logger.info("Phase 3: Automated Verification (Smoke Test)")
        logger.info("=" * 60)

        if not self.start_container():
            return False

        if not self.verify_architecture():
            self.cleanup_container()
            return False

        if not self.health_check():
            self.cleanup_container()
            return False

        logger.info("=" * 60)
        logger.info("✓ All verification checks passed!")
        logger.info("=" * 60)

        return True


class BuilderManager:
    """Manages the builder lifecycle."""

    def __init__(self, config: Config):
        self.config = config

    def cleanup_builder(self) -> bool:
        """Remove the builder instance."""
        logger.info(f"Cleaning up builder '{self.config.builder_name}'...")
        try:
            result = subprocess.run(
                ["docker", "buildx", "rm", self.config.builder_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(f"✓ Builder '{self.config.builder_name}' removed")
                return True

            logger.error(f"✗ Failed to remove builder: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("✗ Builder cleanup timed out")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build Dockerized FastAPI for ARM64 with automated verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --image-name my-app
  %(prog)s --skip-test
  %(prog)s --clean
  %(prog)s --image-name my-app --skip-test --clean
        """,
    )

    parser.add_argument(
        "--image-name",
        default="yoto-web-server",
        help="Docker image name (default: yoto-web-server)",
    )
    parser.add_argument(
        "--skip-test",
        action="store_true",
        help="Build only, skip verification test",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove builder instance after completion",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for health check (default: 8000)",
    )
    parser.add_argument(
        "--dockerfile",
        default="Dockerfile",
        help="Path to Dockerfile (default: Dockerfile)",
    )

    args = parser.parse_args()

    # Create config
    config = Config(
        image_name=args.image_name,
        skip_test=args.skip_test,
        clean=args.clean,
        test_port=args.port,
        dockerfile_path=args.dockerfile,
    )

    logger.info("=" * 60)
    logger.info("Cross-Platform Docker Builder & Verifier")
    logger.info(f"Target Image: {config.image_name}:rpi")
    logger.info("Platform: linux/arm64")
    logger.info("=" * 60)

    # Phase 1: Environment check
    checker = EnvironmentChecker(config)
    if not checker.run_all_checks():
        logger.error("Environment check failed. Aborting.")
        return 1

    # Phase 2: Build
    builder = DockerBuilder(config)
    if not builder.build_image():
        logger.error("Build failed. Aborting.")
        return 1

    # Phase 3: Verification (optional)
    if not config.skip_test:
        if not builder.image_exists():
            logger.error("Built image not found. Aborting verification.")
            return 1

        verifier = DockerVerifier(config)
        if not verifier.run_verification():
            logger.error("Verification failed.")
            if config.clean:
                BuilderManager(config).cleanup_builder()
            return 1

        verifier.cleanup_container()

    # Cleanup
    if config.clean:
        BuilderManager(config).cleanup_builder()

    logger.info("=" * 60)
    logger.info("✓ Build process completed successfully!")
    logger.info("=" * 60)
    logger.info("\nTo run the image:")
    logger.info(f"  docker run -p 8000:8000 {config.image_name}:rpi")
    logger.info("\nTo push to a registry:")
    logger.info(f"  docker tag {config.image_name}:rpi <registry>/<image>:rpi")
    logger.info("  docker push <registry>/<image>:rpi")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
