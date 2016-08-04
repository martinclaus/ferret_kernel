# -*- coding: utf-8 -*-
"""
Created on Thu Aug  4 12:02:55 2016

@author: mclaus
"""

from __future__ import print_function

import json
import os
import sys
import getopt

from jupyter_client.kernelspec import KernelSpecManager
from IPython.utils.tempdir import TemporaryDirectory
from . import FerretKernel

kernel_json = {
    "argv": ["python", "-m", "ferret_kernel",
          "-f", "{connection_file}"], 
    "display_name": "Ferret Kernel", 
    "language": "Ferret",
    "env": {}
}


def install_my_kernel_spec(user=True, prefix=None):
    with TemporaryDirectory() as td:
        os.chmod(td, 0o755) # Starts off as 700, not user readable
        with open(os.path.join(td, 'kernel.json'), 'w') as f:
            json.dump(kernel_json, f, sort_keys=True)

        print('Installing ferret kernel spec')
        KernelSpecManager().install_kernel_spec(td, 'ferret_kernel', user=user,
                                                replace=True, prefix=prefix)


def main(argv=[]):
    prefix = None
    user = True

    opts, _ = getopt.getopt(argv[1:], '', ['user', 'prefix=', 'ferret_command=',
                                           'image_extension='])
    for k, v in opts:
        if k == '--user':
            user = True
        elif k == '--prefix':
            prefix = v
            user = False
        elif k == '--ferret_command':
            kernel_json['env'][FerretKernel.FERRET_COMMAD_KEY] = v
        elif k == '--image_extension':
            kernel_json['env'][FerretKernel.IMAGE_EXTENSION_KEY] = v

    install_my_kernel_spec(user=user, prefix=prefix)

if __name__ == '__main__':
    main(argv=sys.argv)
