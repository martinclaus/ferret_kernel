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

    CMD_CLEAR_WIN = "cancel window/all"
    CMD_FRAME = 'frame/file="{0}"'
    CMD_NEW_WIN = 'set window/new'

    def __init__(self, **kwargs):
        super(FerretKernel, self).__init__(**kwargs)
        self._start_ferret()
        self.tf_mgr = TempFileManager(".png")

    
    def _start_ferret(self):
        self.ferretwrapper = ferret_wrapper()

    
    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        '''Execute the code send to the kernel '''

        reply_content = {}
        unkown_err = False
        interrupted = False
        child_died = False

        code = self._parse_code(code)

        try:
            self.ferretwrapper.run_command(self.CMD_NEW_WIN)        
        
            for c_line in code:
                output = self.ferretwrapper.run_command(c_line.strip(), timeout=None).strip()
            
                if not silent and output.strip():
                    self.send_string(message=output)
                output = ''

            self.handle_graphic_output()
            self.ferretwrapper.run_command(self.CMD_CLEAR_WIN)

        except KeyboardInterrupt:
            self.ferretwrapper.child.sendintr()
            interrupted = True
            self.ferretwrapper._expect_prompt()
            output = self.ferretwrapper.child.before.strip()
        except EOF:
            output = (self.ferretwrapper.child.before
                      + 'Ferret died! Restarting Ferret').strip()
            child_died = True
            self._start_ferret()
        except Exception as err:
            unkown_err = True

        if not silent and output.strip():
            self.send_string(message=output)

        reply_content[u'status'] = u'ok'

        if interrupted:
            reply_content[u'status'] = u'abort'

        if child_died:
            reply_content[u'status'] = u'error'

        if unkown_err:
            reply_content[u'status'] = u'error'
            reply_content.update({
                u'ename': type(err).__name__,
                u'evalue': str(err) 
            })
        reply_content[u'execution_count'] = self.execution_count
        reply_content[u'user_expressions'] = {}
        reply_content[u'payload'] = []
        
        return reply_content


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
        output = ''
        with self.tf_mgr as tmpfile:
            try:
                output += self.ferretwrapper.run_command(self.CMD_FRAME.format(tmpfile),
                                                         timeout=None)
                with open(tmpfile, 'rb') as f:
                    image = f.read()
                image_type = imghdr.what(None, image)
                if image_type is None:
                    raise ValueError("Not a valid image: %s" % tmpfile)
                image_data = base64.b64encode(image).decode('ascii')
            except ValueError as e:
                self.send_string(str(e))
            except IOError:
                self.send_string('')
            else:
                self.send_display_data('image/{0}'.format(image_type), image_data)
        if output:
            self.send_string(output)


    def send_string(self, message, pipe='stdout'):
        self.send_response(self.iopub_socket, 'stream',
                           {'name': pipe, 'text': str(message)})


    def send_display_data(self, img_type, img_data, metadata=None):
        if metadata is None:
            metadata = {}
        self.send_response(self.iopub_socket, 'display_data',
                           {'data': {img_type: img_data},
                           'metadata': metadata})


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
