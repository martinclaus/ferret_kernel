# -*- coding: utf-8 -*-
"""
Created on Tue Aug  2 10:04:02 2016

@author: mclaus
"""

from ipykernel.kernelbase import Kernel
from pexpect import replwrap, EOF
from tempfile import mkdtemp, mkstemp
from shutil import rmtree
from os import remove

__version__ = '0.1'

def ferret_wrapper(command="pyferret -nojnl -nodisplay -server", orig_prompt=u'yes?'):
    ''' Start a ferret shell and retrun a :class:`REPLWrapper` object. '''
    return replwrap.REPLWrapper(command, orig_prompt=orig_prompt,
                                prompt_change=None)


class FerretKernel(Kernel):
    
    implementation = 'Ferret'
    implementation_version = __version__
    language = 'ferret'
    language_version = '6.8'
    language_info = {'name': language,
                     'mimetype': 'text/plain'}
    banner = "Ferret Kernel"

    
    def __init__(self, **kwargs):
        super(FerretKernel, self).__init__(**kwargs)
        self._start_ferret()
        self.tf_mgr = TempFileManager(".png")

    
    def _start_ferret(self):
        self.ferretwrapper = ferret_wrapper()

    
    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        '''Execute the code send to the kernel '''

        if not code.strip():
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}
        
        interrupted = False
        child_died = False        
        
        try:
            output = self.ferretwrapper.run_command(code.strip(), timeout=None)
        except KeyboardInterrupt:
            self.ferretwrapper.child.sendintr()
            interrupted = True
            self.ferretwrapper._expect_prompt()
            output = self.ferretwrapper.child.before
        except EOF:
            output = self.ferretwrapper.child.before + 'Restarting Ferret'
            child_died = True
            self._start_ferret()
        
        if not silent:
            stream_content = {'name': 'stdout',
                              'text': output}
            self.send_response(self.iopub_socket, 'stream', stream_content)

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}
        
        if child_died:
            return {'status': 'abort', 'execution_count': self.execution_count}
        
        return {'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
               }

    def do_shutdown(self, restart):
        del(self.tf_mgr)

#    def do_complete(self, code, cursor_pos):
#        ''' Code completion '''
#        # Not implemented yet
#        super(Kernel, self).do_complete(code, cursor_pos)


class TempFileManager(object):

    def __init__(self, suffix):
        if suffix.startswith("."):
            self.suffix = suffix
        else:
            self.suffix = "." + suffix
        self.tmp_dir = mkdtemp(prefix='ferret_kernel')
        self.tmp_file_stack = []
    
    def __enter__(self):
        tfhandle, tmpfile = mkstemp(dir=self.tmp_dir, suffix=self.suffix)
        tfhandle.close()
        self.tmp_file_stack.append(tmpfile)
        return tmpfile
    
    def __exit__(self, *args):
        tmpfile = self.tmp_file_stack.pop()
        remove(tmpfile)
        
    def __del__(self):
        rmtree(self.tmp_dir)
        self.tmp_file_stack = []


if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=FerretKernel)
