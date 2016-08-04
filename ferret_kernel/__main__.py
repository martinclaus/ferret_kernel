# -*- coding: utf-8 -*-
"""
Created on Wed Aug  3 09:29:46 2016

@author: mclaus
"""
from ipykernel.kernelapp import IPKernelApp
from .kernel import FerretKernel

IPKernelApp.launch_instance(kernel_class=FerretKernel)