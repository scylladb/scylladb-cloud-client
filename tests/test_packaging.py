from pathlib import Path
import unittest


class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository_root = Path(__file__).resolve().parents[1]

    def test_package_version_is_read_from_version_file(self):
        pyproject = (self.repository_root / "pyproject.toml").read_text(encoding="utf-8")
        version = (self.repository_root / "VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(version, "26.5.1")
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertIn('version = {file = "VERSION"}', pyproject)
        self.assertNotIn('version = "0.1.0"', pyproject)

    def test_install_script_creates_scc_alias_symlink(self):
        install_script = (self.repository_root / "install.sh").read_text(encoding="utf-8")

        self.assertIn('BIN_ALIAS="${BIN_DIR}/scc"', install_script)
        self.assertIn('ln -sf "${VENV_DIR}/bin/scylladb-cloud-client" "${BIN_ALIAS}"', install_script)

    def test_uninstall_script_removes_scc_alias_symlink(self):
        uninstall_script = (self.repository_root / "uninstall.sh").read_text(encoding="utf-8")

        self.assertIn('BIN_ALIAS="${PREFIX}/bin/scc"', uninstall_script)
        self.assertIn('remove_symlink_if_present "${BIN_ALIAS}"', uninstall_script)


if __name__ == "__main__":
    unittest.main()
