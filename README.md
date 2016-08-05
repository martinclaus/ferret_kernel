# Jupyter kernel for [Ferret][ferret]

This is a simple iPython wrapper kernel for [pyferret][pyferret] which allows running
ferret inside [Jupyter][jupyter] frontends, including the Jupyter notebook.


## Installation

PyFerret is obviously an dependency for the kernel, so please [install][pyferret_install] it if neccessary

Clone the repository and install the package:

```shell
git clone https://github.com/martinclaus/ferret_kernel.git
cd ferret_kernel
python setup.py install
```

Install the kernel in your jupyter installation
```shell
python -m ferret_kernel.install
```

Possible options are:
```
    --user: install kernel in user space (default)

    --prefix=<PREFIX>: install kernel under PREFIX/share/jupyter/kernels

    --ferret_command=<pyferret>: path to the pyferret executable.

    --image_extension=<.png>: file extension used for graphical output.
```

## Usage

Start jupyter console or qtconsole using

```shell
jupyter console --kernel ferret_kernel
# or
jupyter qtconsole --kernel ferret_kernel
```

To use the kernel in a Jupyter notebook (which is what it is actually written for),
start your notebook server and create a new notebook, selecting "ferret_kernel"
as your kernel.

[ferret]: http://ferret.pmel.noaa.gov/Ferret/home
[pyferret]: http://ferret.pmel.noaa.gov/Ferret/documentation/pyferret
[pyferret_install]: http://ferret.pmel.noaa.gov/Ferret/documentation/pyferret/build-install/
[jupyter]: http://jupyter.org