"""CI selection and the required gate must fail closed without running every suite."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase
from scripts.ci_changes import select_checks,changed_paths,verify_results


class CISelectionTests(TestCase):
    def test_documentation_only(self):
        self.assertEqual(select_checks(['README.md','docs/rules-reference.md']),{'python':False,'ui':False})

    def test_frontend_and_ui_runner_only(self):
        for path in ('app/static/app.js','app/static/index.html','app/static/styles.css','tests/ui_rookie_reveal.cjs','scripts/run-ui-tests.cjs'):
            with self.subTest(path=path):
                self.assertEqual(select_checks([path,'docs/note.md']),{'python':False,'ui':True})

    def test_shared_backend_dependencies_and_unknown_files(self):
        for path in ('app/league.py','app/schedule_balance.py','tests/simple_offseason_fixtures.py','tests/test_ci_changes.py','requirements.txt','package-lock.json','.python-version','.github/workflows/tests.yml','scripts/ci_changes.py','unknown-file'):
            with self.subTest(path=path):
                self.assertEqual(select_checks([path]),{'python':True,'ui':True})
        self.assertEqual(select_checks(['app/static/app.js','app/main.py']),{'python':True,'ui':True})

    def test_manual_main_and_empty_diff_run_everything(self):
        self.assertEqual(select_checks(['README.md'],force_full=True),{'python':True,'ui':True})
        self.assertEqual(select_checks([]),{'python':True,'ui':True})

    def test_required_gate_success_and_intentional_skips(self):
        verify_results({'python':'false','ui':'true'},{'python':'skipped','ui':'success'},'success')
        verify_results({'python':'false','ui':'false'},{'python':'skipped','ui':'skipped'},'success')
        verify_results({'python':'true','ui':'true'},{'python':'success','ui':'success'},'success')

    def test_required_gate_rejects_failures_cancellations_and_unexpected_skips(self):
        for status in ('failure','cancelled','skipped',''):
            with self.subTest(status=status),self.assertRaises(ValueError):
                verify_results({'python':'true','ui':'true'},{'python':status,'ui':'success'},'success')
        for status in ('failure','cancelled','skipped',''):
            with self.subTest(detection=status),self.assertRaises(ValueError):
                verify_results({'python':'false','ui':'false'},{'python':'skipped','ui':'skipped'},status)
        with self.assertRaises(ValueError):
            verify_results({'python':'','ui':'true'},{'python':'skipped','ui':'success'},'success')

    def test_real_diff_includes_deleted_and_renamed_source_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
            git('init','-q');(root/'app').mkdir();(root/'docs').mkdir()
            (root/'app/main.py').write_text('original\n');(root/'docs/note.md').write_text('notes\n')
            git('add','.');git('-c','user.name=CI Tests','-c','user.email=ci-tests@example.invalid','commit','-qm','base')
            base=git('rev-parse','HEAD')
            (root/'app/main.py').rename(root/'docs/renamed.md');(root/'docs/note.md').unlink()
            git('add','-A');git('-c','user.name=CI Tests','-c','user.email=ci-tests@example.invalid','commit','-qm','rename and deletion')
            head=git('rev-parse','HEAD')
            git('checkout','-q','-b','base-advance',base)
            (root/'requirements.txt').write_text('unrelated base-only change\n')
            git('add','.');git('-c','user.name=CI Tests','-c','user.email=ci-tests@example.invalid','commit','-qm','advance base')
            paths=changed_paths(git('rev-parse','HEAD'),head,cwd=root)
            self.assertCountEqual(paths,['app/main.py','docs/renamed.md','docs/note.md'])
            self.assertEqual(select_checks(paths),{'python':True,'ui':True})
            with self.assertRaises(subprocess.CalledProcessError):changed_paths('invalid-ref','HEAD',cwd=root)

    def test_output_protocol_and_final_gate_exit_status(self):
        script=Path(__file__).resolve().parents[1]/'scripts/ci_changes.py'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'output'
            subprocess.run([sys.executable,str(script),'select','--force-full'],env={**os.environ,'GITHUB_OUTPUT':str(output)},check=True,capture_output=True)
            self.assertEqual(output.read_text(),'python=true\nui=true\n')
        env={**os.environ,'CHANGES_RESULT':'success','PYTHON_SELECTED':'true','UI_SELECTED':'false','PYTHON_RESULT':'failure','UI_RESULT':'skipped'}
        result=subprocess.run([sys.executable,str(script),'verify'],env=env,capture_output=True)
        self.assertNotEqual(result.returncode,0)
