# -*- coding: utf-8 -*-
"""
Created on Tue Aug  2 10:04:02 2016

@author: mclaus
"""

from __future__ import print_function

from ipykernel.kernelbase import Kernel
from IPython.display import Image
import IPython.core.formatters as formatters
from pexpect import replwrap, EOF
from tempfile import mkdtemp, mkstemp
from shutil import rmtree
import os
import base64
import re

__version__ = '0.1.0'


def ferret_wrapper(command="pyferret", args="-nojnl -nodisplay -server",
                   orig_prompt=u'yes?'):
    '''
    Start a pyferret shell and retrun a :class:`REPLWrapper` object.
    '''
    return replwrap.REPLWrapper(" ".join((command, args)),
                                orig_prompt=orig_prompt, prompt_change=None)


class FerretKernel(Kernel):
    '''
    Ferret language kernel for the jupyter notebook server.
    '''
    
    implementation = 'Ferret'
    implementation_version = __version__
    language = 'ferret'
    language_version = '6.8'
    language_info = {'name': language,
                     'mimetype': 'text/plain'}
    banner = "Ferret Kernel"

    FERRET_COMMAD_KEY = "FER_COMMAND"
    DEFAULT_FERRET_COMMAND = "pyferret"
    
    IMAGE_EXTENSION_KEY = "FER_IMGEXT"
    DEFAULT_IMAGE_EXTENSION = ".png"

    CMD_CLEAR_WIN = "cancel window/all"
    CMD_FRAME = 'frame/file="{0}"'
    CMD_NEW_WIN = 'set window/new'

    ferret_error_idents = ["\*\*ERROR:", "\*\*TMAP ERR:", "BUFF EMPTY"]
    
    FERRET_ERROR = re.compile(
        "(" + ")|(".join(["^[ ]*" + err_ident for err_ident in ferret_error_idents]) + ")"
    )

    def __init__(self, **kwargs):
        '''
        Starts pyferret, creates a tempfile manager and formatter.
        
        Useful environmental variables:
            FER_COMMAND: Path to the pyferret executable. (Default: pyferret)
            FER_IMGEXT:  File format to use for graphical ouput. (Default: .png)
            
        The environmental variables can also be set in the `env` dictionary
        in the kernel.json file. 
        '''
        
        super(FerretKernel, self).__init__(**kwargs)

        # Start ferret
        command = os.environ.get(self.FERRET_COMMAD_KEY,
                                 self.DEFAULT_FERRET_COMMAND)
        self.ferretwrapper = ferret_wrapper(command)

        # get tempfile manager
        img_ext = os.environ.get(self.IMAGE_EXTENSION_KEY,
                                 self.DEFAULT_IMAGE_EXTENSION)
        self.tf_mgr = TempFileManager(img_ext)
        
        # get formatter for rich display
        self.formatter = formatters.DisplayFormatter()

    
    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        '''
        Execute the code send to the kernel line by line in the pyferret shell.
        '''

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
        '''
        Split cell code into lines but concatenate multi-line statements.
        '''
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
        '''
        Run frame command and send image data to frontend.
        '''
        with self.tf_mgr as tmpfile:
            try:
                self.ferretwrapper.run_command(self.CMD_FRAME.format(tmpfile),
                                               timeout=None)
                try:
                    im = Image(filename=tmpfile)
                # No image produced by cell
                except IOError:
                    pass
                else:
                    self.display(im)
                    
            except Exception as e:
                self.display(str(e), 'stderr')


    def display(self, data, stream='stdout'):
        '''
        Send data to frondend.
        '''

        if type(data) in (str, unicode):
            self.send_string(data, stream)

        # images and other objects
        else:
            self.send_display_data(data)


    def format_data(self, data):
        '''
        Serialize data, which can be any python object or type, and return
        a dictionary ready to be send as a `display_data` reply.
        See [Messaging in Jupyter](http://jupyter-client.readthedocs.io/en/latest/messaging.html#display-data)
        '''
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
        '''
        Send text `message` to the frontend using stream `stream`.
        
        If `message` contains no non-blank characters, nothing is send.
        If `message` matches on of the Ferret error message patterns
        (`self.ferret_error_idents`), the stream will be changed to `'stderr'`.
        '''
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
        '''
        Send display_data response.
        '''
        self.send_response(self.iopub_socket, 'display_data',
                           self.format_data(data))


    def do_shutdown(self, restart):
        '''
        Clean-up actions.
        '''
        del(self.tf_mgr)


class TempFileManager(object):
    '''
    Context manager class to handle temporary files for graphical output.
    '''

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
            os.remove(tmpfile)
        except OSError:
            pass
        
    def __del__(self):
        rmtree(self.tmp_dir)
        self.tmp_file_stack = []
