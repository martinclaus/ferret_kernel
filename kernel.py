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
import base64
import imghdr

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

        code = self._parse_code(code)

        if not code:
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}
        
        interrupted = False
        child_died = False        
        
        for cline in code:
            try:
                output = self.ferretwrapper.run_command(cline.strip(), timeout=None).strip()
            except KeyboardInterrupt:
                self.ferretwrapper.child.sendintr()
                interrupted = True
                self.ferretwrapper._expect_prompt()
                output = self.ferretwrapper.child.before.strip()
            except EOF:
                output = (self.ferretwrapper.child.before + 'Restarting Ferret').strip()
                child_died = True
                self._start_ferret()
            
            if not silent and output.strip():
                stream_content = {'name': 'stdout',
                                  'text': output}
                self.send_response(self.iopub_socket, 'stream', stream_content)
            if interrupted or child_died:
                break

        if self._has_active_window():
            self.handle_graphic_output()

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}
        
        if child_died:
            return {'status': 'abort', 'execution_count': self.execution_count}
        
        return {'status': 'ok',
                'execution_count': self.execution_count,
                'payload': [],
                'user_expressions': {},
               }

    def _parse_code(self, code):
        code_lines = code.split('\n')
        continuation_lines = []
        for line in code_lines:
            if not line:
                continue
            if not continuation_lines:
                continuation_lines.append(line)
                continue
            if continuation_lines[-1].rstrip().endswith('\\'):
                continuation_lines[-1] = (continuation_lines[-1].rstrip(" \\")
                                          + ' ' + line.lstrip())
            else:
                continuation_lines.append(line)
        return continuation_lines


    def _has_active_window(self):
        test_code = "show window"
        separator = '\r\n'
        output = self.ferretwrapper.run_command(test_code, timeout=None)
        output = output.split(separator)
        test_string = output[1].split()[0]
        try:
            # test_string is an integer
            int(test_string)
            return True
        except ValueError:
            # test_string is 'no'
            return False


    def handle_graphic_output(self):
        print_cmd = 'frame/file="{0}"'
        clear_window_cmd = "ca window/all"
        output = ''
        with self.tf_mgr as tmpfile:
            try:
                output += self.ferretwrapper.run_command(print_cmd.format(tmpfile),
                                                         timeout=None)
                with open(tmpfile, 'rb') as f:
                    image = f.read()
                image_type = imghdr.what(None, image)
                if image_type is None:
                    raise ValueError("Not a valid image: %s" % tmpfile)
                image_data = base64.b64encode(image).decode('ascii')
                content = {'data': {'image/{0}'.format(image_type): image_data},
                           'metadata': {}}
            except ValueError as e:
                message = {'name': 'stdout', 'text': str(e)}
                self.send_response(self.iopub_socket, 'stream', message)
            else:
                self.send_response(self.iopub_socket, 'display_data', content)
            finally:
                # delete all buffered windows
                output += self.ferretwrapper.run_command(clear_window_cmd)
        if output:
            message = {'name': 'stdout', 'text': output}
            self.send_response(self.iopub_socket, 'stream', output)


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
