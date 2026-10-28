import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_environment import configure_runtime


class RuntimeStorageTests(unittest.TestCase):
    def test_blas_threads_are_limited_even_without_storage_configuration(self):
        with patch.dict(os.environ, {"CINESCENE_CPU_THREADS": "2"}, clear=True), patch("runtime_environment.load_dotenv"):
            configure_runtime()
            for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
                self.assertEqual(os.environ[name], "2")

    def test_model_gpu_and_upload_caches_stay_under_storage_root(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"CINESCENE_STORAGE_ROOT": folder}, clear=True), \
                 patch("runtime_environment.load_dotenv"), patch.object(tempfile, "tempdir", tempfile.tempdir):
                configure_runtime()
                cache = Path(folder) / "cache"
                for name in ("HF_HOME", "HF_HUB_CACHE", "PIP_CACHE_DIR", "TORCH_HOME",
                             "TORCH_EXTENSIONS_DIR", "TORCHINDUCTOR_CACHE_DIR", "CUDA_CACHE_PATH",
                             "TRITON_CACHE_DIR", "XDG_CACHE_HOME", "TEMP", "TMP"):
                    path = Path(os.environ[name])
                    self.assertTrue(path.is_dir(), name)
                    self.assertTrue(path == cache or cache in path.parents, name)
                self.assertEqual(tempfile.tempdir, str(cache / "tmp"))

    def test_explicit_cache_preferences_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            custom = str(Path(folder) / "custom-torch-cache")
            with patch.dict(os.environ, {"CINESCENE_STORAGE_ROOT": folder, "TORCH_HOME": custom}, clear=True), \
                 patch("runtime_environment.load_dotenv"), patch.object(tempfile, "tempdir", tempfile.tempdir):
                configure_runtime()
                self.assertEqual(os.environ["TORCH_HOME"], custom)
