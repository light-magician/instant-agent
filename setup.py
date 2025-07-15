"""
Setup script that copies .env file during installation.
"""
import shutil
from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop


class PostInstallCommand(install):
    """Post-installation command that copies .env file."""
    def run(self):
        install.run(self)
        self.copy_env_file()
    
    def copy_env_file(self):
        source_env = Path.cwd() / ".env"
        if source_env.exists():
            try:
                # Find site-packages directory
                site_packages = Path(self.install_lib)
                target_env = site_packages / ".env"
                
                print(f"📋 Copying .env from {source_env} to {target_env}")
                shutil.copy2(source_env, target_env)
                print("✅ .env file copied to global installation")
            except Exception as e:
                print(f"⚠️  Could not copy .env: {e}")


class PostDevelopCommand(develop):
    """Post-development installation command."""
    def run(self):
        develop.run(self)


setup(
    name="instant-agent", 
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'instant-agent=agent.cli:main',
        ],
    },
    cmdclass={
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
    },
)