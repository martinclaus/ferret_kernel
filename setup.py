from setuptools import setup

setup(
      name='ferret_kernel',
      version='0.1.0',
      description='Ferret kernel for Jupyter',
      author='Martin Claus',
      packages=['ferret_kernel'],
      install_requires = [
          'pexpect >= 3.3',
          'jupyter_client',
          'IPython',
          'ipykernel',
      ],
)
