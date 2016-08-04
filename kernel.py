# -*- coding: utf-8 -*-
"""
Created on Tue Aug  2 10:04:02 2016

@author: mclaus
"""

from ipykernel.kernelbase import Kernel
from IPython.display import Image
import IPython.core.formatters as formatters
from pexpect import replwrap, EOF
from tempfile import mkdtemp, mkstemp
from shutil import rmtree
from os import remove 
import base64
import re

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

    CMD_CLEAR_WIN = "cancel window/all"
    CMD_FRAME = 'frame/file="{0}"'
    CMD_NEW_WIN = 'set window/new'

    ferret_error_idents = ["\*\*ERROR:", "\*\*TMAP ERR:", "BUFF EMPTY"]
    
    FERRET_ERROR = re.compile(
        "(" + ")|(".join(["^[ ]*" + err_ident for err_ident in ferret_error_idents]) + ")"
    )

    def __init__(self, **kwargs):
        super(FerretKernel, self).__init__(**kwargs)
        self._start_ferret()
        self.tf_mgr = TempFileManager(".png")
        self.formatter = formatters.DisplayFormatter()

    
    def _start_ferret(self):
        self.ferretwrapper = ferret_wrapper()

    
    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        '''Execute the code send to the kernel '''

        unkown_err = False
        interrupted = False
        child_died = False
        
        err_output = []

        try:

            code = self._parse_code(code)

            self.ferretwrapper.run_command(self.CMD_NEW_WIN)
        
            for c_line in code:
                out = self.ferretwrapper.run_command(c_line.strip(),
                                                     timeout=None)
                if not silent and out:
                    self.display(out)
            
            self.handle_graphic_output()
            self.ferretwrapper.run_command(self.CMD_CLEAR_WIN)

        except KeyboardInterrupt:
            self.ferretwrapper.child.sendintr()
            interrupted = True
            self.ferretwrapper._expect_prompt()
            err_output.append(self.ferretwrapper.child.before.strip())
            err_output.append("KeyboardInterrupt")

        except EOF:
            err_output.append(self.ferretwrapper.child.before.strip())
            err_output.append('Ferret died! Restarting Ferret')
            child_died = True
            self._start_ferret()

        except Exception as err:
            unkown_err = True
            err_output.append(str(err))

        finally:
            if not silent and err_output:
                self.display("\n".join(err_output), stream="stderr")
    
        execute_reply = {}
        execute_reply[u'status'] = u'ok'

        if interrupted:
            execute_reply[u'status'] = u'abort'
        elif child_died:
            execute_reply.update({
                u'status': u'error',
                u'ename': "Kernel died",
                u'evalue': str(EOF),
                u'traceback': [] 
            })
        elif unkown_err:
            execute_reply.update({
                u'status': u'error',
                u'ename': type(err).__name__,
                u'evalue': str(err),
                u'traceback': [] 
            })
        else:
            execute_reply[u'execution_count'] = self.execution_count
            execute_reply[u'user_expressions'] = {}
        
        return execute_reply


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


    def handle_graphic_output(self):
        with self.tf_mgr as tmpfile:
            try:
                self.ferretwrapper.run_command(self.CMD_FRAME.format(tmpfile),
                                               timeout=None)
                try:
                    im = Image(filename=tmpfile)
                except IOError:
                    pass
                else:
                    self.display(im)
                    
            except Exception as e:
                self.display(str(e), 'stderr')


    def display(self, data, stream='stdout'):

        if type(data) in (str, unicode):
            self.send_string(data, stream)

        # images and other objects
        else:
            self.send_display_data(data)


    def format_data(self, data):
        try:
            if not data.strip():
                return {'data': {}, 'metadata': {}}
        except AttributeError:
            pass
        repre, metadata = self.formatter.format(data)

        for mimetype, value in repre.items():
            # serialize binary objects like images
            if isinstance(value, bytes):
                repre[mimetype] = base64.encodestring(value).decode('utf-8')
            else:
                try:
                    repre[mimetype] = str(value).strip()
                except:
                    repre[mimetype] = repr(value)

        return {'data': repre, 'metadata': metadata}
        

    def send_string(self, message, stream='stdout'):
        message = message.strip()

        if not message:
            return

        if not message.endswith('\n'):
            message += '\n'

        if self.FERRET_ERROR.match(message):
            stream = 'stderr'
        
        self.send_response(self.iopub_socket, 'stream',
                           {'name': stream, 'text': str(message)})


    def send_display_data(self, data):
        self.send_response(self.iopub_socket, 'display_data',
                           self.format_data(data))


    def do_shutdown(self, restart):
        del(self.tf_mgr)


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
        try:
            remove(tmpfile)
        except OSError:
            pass
        
    def __del__(self):
        rmtree(self.tmp_dir)
        self.tmp_file_stack = []


if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=FerretKernel)
