"""Run with: python -m unittest discover -s tests -v

Uses real wx and worker/CLI code, with model inference replaced by a small fake.
No wx.App, model downloads, or GPU are needed.
"""
import contextlib
import io
import logging
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import wx

from gui import cli, worker


class CliEventTests(unittest.TestCase):
    def test_cli_success_error_and_cancel_without_wx_app(self):
        self.assertIsNone(wx.GetApp())
        for outcome in ('success', 'error', 'cancel', 'stop'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as root:
                root = Path(root)
                audio = root / 'song.wav'
                sf.write(audio, np.zeros((800, 2)), 8000)
                second_audio = root / 'second-song.wav'
                sf.write(second_audio, np.zeros((800, 2)), 8000)
                (root / 'test.ckpt').touch()
                model_manager = type('Manager', (), {
                    'models_dir': str(root), 'downloadable_models': {},
                    'downloadable_aliases': {}, 'downloadable_models_by_file': {},
                    '_ready_event': threading.Event(),
                })()
                model_manager._ready_event.set()
                contexts = []

                class FakePatches:
                    def __init__(self, model_dir, parent, log):
                        contexts.append(parent)
                    def apply(self, separator):
                        pass
                    def restore(self):
                        pass

                class FakeSeparator:
                    def __init__(self, **kwargs):
                        self.output_dir = kwargs['output_dir']
                        self.model_instance = None
                        # Exercises GuiLogHandler, which used wx.CallAfter.
                        logging.getLogger('audio_separator').info('fake model initialized')
                    def load_model(self, **kwargs):
                        # Match audio-separator's cached model: its writer keeps
                        # the original directory unless the caller updates it.
                        if self.model_instance is None:
                            self.model_instance = SimpleNamespace(output_dir=self.output_dir)
                    def separate(self, path):
                        import sys
                        sys.stderr.write('50%| fake inference\n')
                        if outcome == 'error':
                            raise RuntimeError('deliberate inference failure')
                        if outcome == 'cancel':
                            raise KeyboardInterrupt()
                        if outcome == 'stop':
                            threading.current_thread().stop()
                            return []
                        name = Path(path).stem + '_(Vocals).wav'
                        sf.write(Path(self.model_instance.output_dir) / name, np.zeros((800, 2)), 8000)
                        return [name]

                def no_gui(*args, **kwargs):
                    raise AssertionError('CLI dispatched a GUI event')

                output = io.StringIO()
                logger = logging.getLogger('audio_separator')
                handlers, level = logger.handlers[:], logger.level
                try:
                    with patch.object(cli, 'ModelManager', return_value=model_manager), \
                         patch.object(worker, 'Separator', FakeSeparator), \
                         patch('gui.audio_patches.AudioPatches', FakePatches), \
                         patch.object(worker, 'cleanup_dead_sessions'), \
                         patch.object(worker.subprocess, 'run', side_effect=OSError('conversion unavailable in unit test')), \
                         patch.object(wx, 'PostEvent', side_effect=no_gui), \
                         patch.object(wx, 'CallAfter', side_effect=no_gui), \
                         patch.object(worker, 'LogEvent'), \
                         patch.object(worker, 'ProgressEvent'), \
                         patch.object(worker, 'DoneEvent'), \
                         contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                        inputs = [str(audio), str(second_audio)] if outcome == 'success' else [str(audio)]
                        code = cli.run_cli(['-i', *inputs, '-m', 'test.ckpt',
                                            '-o', str(root / 'out'), '--bit-depth', '32'])
                    self.assertEqual(code, 0 if outcome == 'success' else 1)
                    self.assertEqual(len(contexts), 1)
                    self.assertIs(contexts[0].model_manager, model_manager)
                    self.assertIn('fake model initialized', output.getvalue())
                    self.assertIn('Progress: 50%', output.getvalue())
                    if outcome == 'success':
                        self.assertIn('Generated 2 stem files', output.getvalue())
                        for song in ('song', 'second-song'):
                            self.assertEqual(len(list((root / 'out' / song).glob('*.wav'))), 1)
                    elif outcome == 'error':
                        self.assertIn('deliberate inference failure', output.getvalue())
                    else:
                        self.assertNotIn('[SUCCESS]', output.getvalue())
                finally:
                    logger.handlers = handlers
                    logger.setLevel(level)

    def test_gui_worker_retains_parent_as_model_context_and_event_recipient(self):
        parent = object()
        instance = worker.SeparationThread(parent, [], '.', 'model.ckpt')
        self.assertIs(instance.model_context, parent)
        with patch.object(wx, 'PostEvent') as post, \
             patch.object(worker, 'LogEvent'), patch.object(worker, 'ProgressEvent'):
            instance.post_log('message')
            instance.post_progress(50)
        self.assertEqual(post.call_count, 2)
        self.assertTrue(all(call.args[0] is parent for call in post.call_args_list))


if __name__ == '__main__':
    unittest.main()
