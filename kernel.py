# -*- coding: utf-8 -*-
"""
Created on Tue Aug  2 10:04:02 2016

@author: mclaus
"""

from ipykernel.kernelbase import Kernel


class FerretKernel(Kernel):
    
    implementation = 'Ferret'
    implementation_version = '0.1'
    language = 'ferret'
    language_version = '6.8'
    language_info = {'mimetype': 'text/plain'}
    banner = "Ferret Kernel"
    
    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        if not silent:
            stream_content = {'name': 'stdout',
                              'text': code}
            self.send_response(self.iopub_socket, 'stream', stream_content)
        
        return {'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
               }

if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=FerretKernel)
